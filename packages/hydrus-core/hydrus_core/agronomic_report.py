"""
Advanced Agronomic Report Generator:
Supports:
1. Operational Mode:
   - 'planejamento': Proactive simulation (E se... / Vou realizar)
   - 'ocorrencia': Reactive diagnostic (Já realizei no campo)
2. Multi-nutrient support: N (Nitrogênio), K (Potássio), P (Fósforo), Ca (Cálcio), Mg (Magnésio), S (Enxofre).
3. Dose sanity check with crop-specific agronomic thresholds (trava agronômica).
4. Osmotic stress / EC estimate for the soil solution at peak concentration.
"""

from hydrus_core.hydrus_solver import SimulationResults
from hydrus_core.soil_physics import SoilParameters
from hydrus_core.crop import CropParameters

# ─────────────────────────────────────────────────────────────────────────────
# Limites agronômicos máximos por nutriente (dose elementar em kg/ha).
# Baseados em: Embrapa, IAC Boletim 100, CFSEMG, Sousa & Lobato (2004).
# Doses ACIMA desses valores são agronomicamente incomuns e ativam o alerta.
# NOTA: Ca=2000 (não 500): Ca como nutriente em adubo raramente passa de 150-200
# kg/ha, mas corretivos (calcário/gesso) aplicam 500-2000 kg/ha de Ca; o teto
# alto evita falso-positivo quando o usuário simula calagem/gessagem.
# ─────────────────────────────────────────────────────────────────────────────
AGRONOMIC_MAX_DOSE: dict = {
    "N":  400.0,   # Nitrogênio: máx ~300-400 kg/ha mesmo em cafeeiros (Malavolta, 2006)
    "K":  600.0,   # Potássio: culturas exigentes chegam a 500 kg/ha K2O ≈ 415 K; usamos 600 para elemento puro
    "P":  300.0,   # Fósforo: doses de P2O5 chegam a 400+, mas P elementar ≈ 175 kg/ha; usamos 300 como teto
    "Ca": 2000.0,  # Cálcio: 2000 p/ não barrar corretivo/gesso (calagem/gessagem 500-2000); como adubo o usual é ≤150-200 kg/ha
    "Mg": 200.0,   # Magnésio elementar
    "S":  250.0,   # Enxofre
}

# Concentração da solução do solo acima da qual ocorre estresse osmótico (g/L = mg/cm³)
# Equivalente a CE ≈ 4 dS/m (limiar geral de toxicidade para culturas moderadamente sensíveis)
# Ref: Maas & Hoffman (1977); Ayers & Westcot – FAO 29 (1985)
OSMOTIC_STRESS_CONC_MG_CM3 = 2.0   # ≈ 2 g/L → CE ≈ 4 dS/m

# Fator de conversão concentração (mg/cm³) → CE estimada (dS/m)  [empírico: CE ≈ conc_total / 0.64]
CE_FACTOR = 0.64  # g/L por dS/m


# Limites de referência por EVENTO ÚNICO de aplicação (referência para descrição física)
MAX_SINGLE_EVENT_DOSE: dict = {
    "N": 140.0,
    "K": 100.0,
    "P": 80.0,
    "S": 60.0,
    "Ca": 150.0,
    "Mg": 60.0,
}

# Limiares dinâmicos de lixiviação por elemento (% tolerada)
NUTRIENT_RISK_THRESHOLDS: dict = {
    "N": {"low": 10.0, "mod": 25.0},  # Ânion móvel: > 25% é desastre agronômico
    "S": {"low": 10.0, "mod": 25.0},
    "K": {"low": 8.0,  "mod": 20.0},  # Cátion da CTC: > 20% é crítico
    "Ca": {"low": 8.0, "mod": 20.0},
    "Mg": {"low": 8.0, "mod": 20.0},
    "P": {"low": 2.0,  "mod": 5.0},   # Fósforo: > 5% indica anomalia extrema de macroporos
}


def _severity_from_pct_peak(pct: float, peak_cm=None, root_cm=None, thresholds: dict = None) -> int:
    """Mecanismo único: severidade = max(regra-por-%, regra-por-pico). 0=EXCELENTE,1=MODERADO,2=CRITICO.
    Pico: >0.75*raiz rebaixa 1 nível (nunca EXCELENTE); >1.0*raiz piso MODERADO; >1.5*raiz ou >raiz+30 piso CRITICO."""
    th = thresholds or {"low": 10.0, "mod": 25.0}
    try:
        low = float(th.get("low", 10.0))
        mod = float(th.get("mod", 25.0))
    except (TypeError, ValueError, AttributeError):
        low, mod = 10.0, 25.0
    try:
        p = float(pct or 0.0)
    except (TypeError, ValueError):
        p = 0.0
    if p <= low:
        sev = 0
    elif p <= mod:
        sev = 1
    else:
        sev = 2
    try:
        root = float(root_cm) if root_cm is not None else 0.0
        peak = float(peak_cm) if peak_cm is not None else 0.0
    except (TypeError, ValueError):
        return sev
    if root <= 0 or peak <= 0:
        return sev
    if peak > 0.75 * root:
        sev = min(2, sev + 1)
        sev = max(sev, 1)
    if peak > 1.0 * root:
        sev = max(sev, 1)
    if peak > 1.5 * root or peak > root + 30.0:
        sev = 2
    return sev

def _fmt_peak(peak_cm) -> str:
    """Formata pico: indefinido se NaN/None, senão X.X cm. Sem recomendação, só descrição."""
    try:
        import math
        v = float(peak_cm)
        if v is None or math.isnan(v):
            return "indefinido"
        return f"{v:.1f} cm"
    except (TypeError, ValueError):
        return "indefinido"

def _mass_totals(results, dose_total: float, primary_sym: str) -> dict:
    """Balanço real multissoluto: soma por soluto (kg), nunca % primário × dose total.
    retained já exclui uptaken: retained=min(exato, 100-pct-upt) → soma nunca >100."""
    nr = getattr(results, "nutrient_results", None) or {}
    is_multi = len(nr) > 1
    if is_multi:
        tot_dose = sum(float(d.get("dose_kg_ha", 0.0) or 0.0) for d in nr.values())
        if tot_dose <= 0:
            tot_dose = float(dose_total or 0.0)
        tot_lost = sum(float(d.get("leached_kg_ha", 0.0) or 0.0) for d in nr.values())
        tot_ret = sum(float(d.get("retained_kg_ha", 0.0) or 0.0) for d in nr.values())
        tot_upt = sum(float(d.get("uptaken_kg_ha", 0.0) or 0.0) for d in nr.values())
        pct = (tot_lost / tot_dose * 100.0) if tot_dose > 0 else 0.0
        ret = (tot_ret / tot_dose * 100.0) if tot_dose > 0 else 0.0
        upt = (tot_upt / tot_dose * 100.0) if tot_dose > 0 else 0.0
        ret = min(ret, max(0.0, 100.0 - pct - upt))
        return {"is_multi": True, "total_dose": tot_dose, "pct": pct, "retained_pct": ret,
                "uptaken_pct": upt, "lost_kg": tot_lost, "retained_kg": tot_ret, "uptaken_kg": tot_upt}
    d = nr.get(primary_sym, {}) if nr else {}
    pct = float(d.get("leaching_ratio_pct", results.leaching_ratio_pct))
    upt = float(d.get("uptaken_pct", float(getattr(results, "uptaken_pct", 0.0) or 0.0)))
    ret_exact = float(d.get("retained_root_pct", max(0.0, 100.0 - pct - upt)))
    ret = min(ret_exact, max(0.0, 100.0 - pct - upt))
    td = float(d.get("dose_kg_ha", dose_total))
    return {"is_multi": False, "total_dose": td, "pct": pct, "retained_pct": ret,
            "uptaken_pct": upt, "lost_kg": td * pct / 100.0, "retained_kg": td * ret / 100.0,
            "uptaken_kg": td * upt / 100.0}


def _risk_banner(results, primary_sym: str, fallback_pct: float, root_depth_cm=None, peak_cm=None) -> tuple:
    """Banner pelo pior soluto: severidade = max(regra-por-%, regra-por-pico), thresholds por elemento."""
    nr = getattr(results, "nutrient_results", None) or {}
    # Sem massa aplicada: não classificar o vazio — descrição neutra
    try:
        _tot_dose = sum(float((_d or {}).get("dose_kg_ha", 0.0) or 0.0) for _d in nr.values())
    except (TypeError, ValueError):
        _tot_dose = 0.0
    if _tot_dose <= 1e-9:
        return ("⚪ [SEM MASSA APLICADA]", "Sem massa aplicada a classificar", primary_sym, fallback_pct)
    _root = root_depth_cm if root_depth_cm is not None else float(getattr(results, "target_depth_cm", 30.0) or 30.0)
    if len(nr) > 1:
        worst_sym, worst_sev = primary_sym, -1
        worst_pct = fallback_pct
        for sym, d in nr.items():
            th_s = NUTRIENT_RISK_THRESHOLDS.get(sym, {"low": 10.0, "mod": 25.0})
            _pct = float(d.get("leaching_ratio_pct", 0.0) or 0.0)
            _pk = float(d.get("peak_depth_cm", getattr(results, "peak_depth_cm", 0.0)) or 0.0)
            sev = _severity_from_pct_peak(_pct, _pk, _root, th_s)
            if sev > worst_sev:
                worst_sev, worst_sym, worst_pct = sev, sym, _pct
        th = NUTRIENT_RISK_THRESHOLDS.get(worst_sym, {"low": 10.0, "mod": 25.0})
        pct_w = float(nr[worst_sym].get("leaching_ratio_pct", fallback_pct) or 0.0)
        sev_w = _severity_from_pct_peak(pct_w, float(nr[worst_sym].get("peak_depth_cm", getattr(results, "peak_depth_cm", 0.0)) or 0.0), _root, th)
        if sev_w <= 0:
            return ("[MOBILIDADE BAIXA]", f"Fração além da camada ≤ {th['low']:.0f}%", worst_sym, pct_w)
        elif sev_w <= 1:
            return ("[MOBILIDADE MODERADA]", f"Fração além da camada {th['low']:.0f}% a {th['mod']:.0f}% — pior soluto: {worst_sym} ({pct_w:.1f}%)", worst_sym, pct_w)
        return ("[MOBILIDADE ALTA]", f"Fração além da camada > {th['mod']:.0f}% — pior soluto: {worst_sym} ({pct_w:.1f}%)", worst_sym, pct_w)
    th = NUTRIENT_RISK_THRESHOLDS.get(primary_sym, {"low": 10.0, "mod": 25.0})
    _pk0 = peak_cm if peak_cm is not None else float(getattr(results, "peak_depth_cm", 0.0) or 0.0)
    sev0 = _severity_from_pct_peak(fallback_pct, _pk0, _root, th)
    if sev0 <= 0:
        return ("[MOBILIDADE BAIXA]", f"Fração além da camada ≤ {th['low']:.0f}%", primary_sym, fallback_pct)
    elif sev0 <= 1:
        return ("[MOBILIDADE MODERADA]", f"Fração além da camada {th['low']:.0f}% a {th['mod']:.0f}%", primary_sym, fallback_pct)
    return ("[MOBILIDADE ALTA]", f"Fração além da camada > {th['mod']:.0f}%", primary_sym, fallback_pct)


def _column_risk_banner(results, primary_sym: str, fallback_pct: float, target_depth_cm: float) -> tuple:
    nr = getattr(results, "nutrient_results", None) or {}
    try:
        _tot_dose_c = sum(float((_d or {}).get("dose_kg_ha", 0.0) or 0.0) for _d in nr.values())
    except (TypeError, ValueError):
        _tot_dose_c = 0.0
    if _tot_dose_c <= 1e-9:
        return ("⚪ [SEM MASSA APLICADA]", "Sem massa aplicada a classificar", primary_sym, fallback_pct)
    if len(nr) > 1:
        worst_sym, worst_sev = primary_sym, -1
        for sym, d in nr.items():
            th_s = NUTRIENT_RISK_THRESHOLDS.get(sym, {"low": 10.0, "mod": 25.0})
            _pct = float(d.get("leaching_ratio_pct", 0.0) or 0.0)
            _pk = float(d.get("peak_depth_cm", getattr(results, "peak_depth_cm", 0.0)) or 0.0)
            sev = _severity_from_pct_peak(_pct, _pk, target_depth_cm, th_s)
            if sev > worst_sev:
                worst_sev, worst_sym = sev, sym
        th = NUTRIENT_RISK_THRESHOLDS.get(worst_sym, {"low": 10.0, "mod": 25.0})
        pct_w = float(nr[worst_sym].get("leaching_ratio_pct", fallback_pct) or 0.0)
        pk_w = float(nr[worst_sym].get("peak_depth_cm", getattr(results, "peak_depth_cm", 0.0)) or 0.0)
        sev_w = _severity_from_pct_peak(pct_w, pk_w, target_depth_cm, th)
        if sev_w <= 0:
            return ("[MOBILIDADE BAIXA]", f"Fração além de {target_depth_cm:.0f} cm ≤ {th['low']:.0f}%", worst_sym, pct_w)
        elif sev_w <= 1:
            return ("[MOBILIDADE MODERADA]", f"Fração além de {target_depth_cm:.0f} cm {th['low']:.0f}% a {th['mod']:.0f}% — pior soluto: {worst_sym} ({pct_w:.1f}%)", worst_sym, pct_w)
        return ("[MOBILIDADE ALTA]", f"Fração além de {target_depth_cm:.0f} cm > {th['mod']:.0f}% — pior soluto: {worst_sym} ({pct_w:.1f}%)", worst_sym, pct_w)
    th = NUTRIENT_RISK_THRESHOLDS.get(primary_sym, {"low": 10.0, "mod": 25.0})
    _pk0 = float(getattr(results, "peak_depth_cm", 0.0) or 0.0)
    try:
        _nr0 = (getattr(results, "nutrient_results", {}) or {}).get(primary_sym, {})
        if _nr0 and _nr0.get("peak_depth_cm") is not None:
            _pk0 = float(_nr0.get("peak_depth_cm") or 0.0)
    except (TypeError, ValueError):
        pass
    sev0 = _severity_from_pct_peak(fallback_pct, _pk0, target_depth_cm, th)
    if sev0 <= 0:
        return ("[MOBILIDADE BAIXA]", f"Fração além de {target_depth_cm:.0f} cm ≤ {th['low']:.0f}%", primary_sym, fallback_pct)
    elif sev0 <= 1:
        return ("[MOBILIDADE MODERADA]", f"Fração além de {target_depth_cm:.0f} cm {th['low']:.0f}% a {th['mod']:.0f}%", primary_sym, fallback_pct)
    return ("[MOBILIDADE ALTA]", f"Fração além de {target_depth_cm:.0f} cm > {th['mod']:.0f}%", primary_sym, fallback_pct)


def _kd_eff_display(n_data: dict, nominal_kd: float) -> tuple[float, bool]:
    """Kd efetivo usado no transporte (com competição Ca/Langmuir) vs nominal.

    Retorna (kd_eff_medio, difere). kd_eff pode ser escalar ou vetor por nó;
    usa a média quando vetor. (L10)"""
    try:
        ke = n_data.get("kd_eff", nominal_kd) if isinstance(n_data, dict) else nominal_kd
        import numpy as _np
        if ke is None:
            return float(nominal_kd), False
        if isinstance(ke, (list, tuple)) or (hasattr(ke, "__len__") and not isinstance(ke, (float, int))):
            try:
                ke = float(_np.mean(_np.asarray(ke, dtype=float)))
            except Exception:
                ke = float(nominal_kd)
        else:
            try:
                import numpy as _np2
                if _np2.ndim(ke):
                    ke = float(_np2.mean(_np2.asarray(ke, dtype=float)))
                else:
                    ke = float(ke)
            except Exception:
                ke = float(ke)
        differs = abs(ke - float(nominal_kd)) > 0.0005
        return ke, differs
    except (TypeError, ValueError):
        return float(nominal_kd), False


P_UNIT_NOTE = (
    "> ℹ️ **Nota de unidade (P):** o perfil C(z) plota **P total no solo "
    "(dissolvido + adsorvido, mg P/cm³)**; as curvas C(t)/BTC e os perfis nos dias "
    "de leitura mostram **P dissolvido na solução (mg/L)**. Não comparar valores "
    "absolutos entre os dois sem converter pela retenção (R/Kd)."
)

# Espécies químicas representadas por cada soluto (modelo sem transformações).
SOLUTE_SPECIES = {
    "N": "NO₃⁻ (nitrato)", "K": "K⁺", "S": "SO₄²⁻ (sulfato)",
    "Ca": "Ca²⁺", "Mg": "Mg²⁺", "P": "H₂PO₄⁻ (fosfato)",
}

SCOPE_NOTE = (
    "> ℹ️ **Escopo e limites:** cada soluto representa uma **espécie química fixa** "
    "(N como NO₃⁻, K como K⁺, S como SO₄²⁻); o modelo **não simula transformações químicas** "
    "entre espécies. Kd de **referência bibliográfica** para a textura do solo, ajustáveis — "
    "**não calibrados experimentalmente** para este talhão. Absorção **passiva** "
    "(proporcional à transpiração, sem teto nutricional): potencial máximo de captura, "
    "não previsão garantida. Uso recomendado: **comparação entre manejos/cenários**."
)


def _dose_sanity(
    dose: float,
    nutrient_symbol: str,
    nutrient_name: str,
) -> tuple[bool, str]:
    """
    Retorna (is_problematic: bool, alert_text: str).
    Diferencia teto de safra de teto por evento único.
    """
    single_limit = MAX_SINGLE_EVENT_DOSE.get(nutrient_symbol, 150.0)
    cycle_limit = AGRONOMIC_MAX_DOSE.get(nutrient_symbol, 9999.0)

    if dose > cycle_limit:
        return (
            True,
            (
                f"> 🚨 **ALERTA AGRONÔMICO — Dose Extrema fora do Padrão Agronômico:** "
                f"A dose de **{dose:,.0f} kg/ha** de {nutrient_name} ({nutrient_symbol}) "
                f"supera o teto de safra ({cycle_limit:.0f} kg/ha). "
                f"Verifique se o valor foi inserido como elemento puro (não adubo bruto comercial)."
            ),
        )
    elif dose > single_limit:
        return (
            True,
            (
                f"> ⚠️ **DESCRIÇÃO FÍSICA — Dose acima da referência por evento:** "
                f"A dose de **{dose:,.0f} kg/ha** de {nutrient_name} em aplicação única "
                f"está acima do valor de referência por entrada (**{single_limit:.0f} kg/ha**). "
                f"Descrição física: concentração estimada elevada na camada de aplicação."
            ),
        )
    return False, ""


def _osmotic_stress_check(
    dose_kg_ha: float,
    soil: SoilParameters,
    root_z_cm: float,
    nutrient_name: str,
    nutrient_symbol: str,
    retained_pct: float,
    active_depth_cm: float = 0.0,
) -> tuple[bool, str]:
    """
    Calcula o estresse osmótico diluído na camada de aplicação real (L3):
    espessura = pm_bottom - pm_top quando informada (sulco/custom), senão
    fallback 0-10 cm. CE ≈ conc_total / 0.64.
    """
    # Camada de dissolução real: placement (pm_top..pm_bottom); fallback 0-10 cm
    try:
        _ad = float(active_depth_cm or 0.0)
    except (TypeError, ValueError):
        _ad = 0.0
    if _ad > 0.05:
        active_depth_cm = min(max(_ad, 1.0), max(root_z_cm, 1.0))
    else:
        active_depth_cm = min(root_z_cm, 10.0)
    _lbl = f"0–{active_depth_cm:.0f} CM" if _ad <= 0.05 else f"{active_depth_cm:.0f} CM (camada de aplicação)"
    dose_retained_kg_ha = dose_kg_ha * (retained_pct / 100.0)
    dose_retained_mg_cm2 = dose_retained_kg_ha * 0.01

    # Umidade operacional (~80% da saturação no pico do evento)
    pore_vol_cm = (soil.theta_s * 0.8) * active_depth_cm
    if pore_vol_cm <= 0:
        return False, ""

    c_soil = dose_retained_mg_cm2 / pore_vol_cm
    ce_est = c_soil / CE_FACTOR

    if c_soil > OSMOTIC_STRESS_CONC_MG_CM3:
        return (
            True,
            (
                f"> ⚠️ **DESCRIÇÃO FÍSICA — Concentração na camada {_lbl}:** Concentração estimada = "
                f"**{c_soil:.2f} g/L** (Condutividade Elétrica estimada CE ≈ **{ce_est:.1f} dS/m**, diluída na camada de aplicação). "
                f"Valores de CE acima de 4 dS/m reduzem o potencial hídrico do solo."
            ),
        )
    return False, ""


def generate_advanced_report(
    results: SimulationResults,
    soil: SoilParameters,
    crop: CropParameters,
    rain_mm: float,
    fertilizer_dose_kg_ha: float,
    nutrient_symbol: str = "N",
    nutrient_name: str = "Nitrogênio",
    mode: str = "planejamento",  # 'planejamento' ou 'ocorrencia'
    kd_used: float = 0.0,
    kd_citation: str = "Literatura",
    release_type: str = "immediate",
    release_days: float = 60.0,
    active_depth_cm: float = 0.0,
) -> str:
    _bal = _mass_totals(results, fertilizer_dose_kg_ha, nutrient_symbol)
    pct = _bal["pct"]
    retained_pct = _bal["retained_pct"]
    uptaken_pct = _bal["uptaken_pct"]
    peak = results.peak_depth_cm
    has_crop = crop is not None
    root_z = float(crop.root_depth_cm) if has_crop else float(getattr(results, "target_depth_cm", 30.0) or 30.0)
    is_controlled = release_type in ["controlled", "liberacao_controlada"]
    _nr = getattr(results, "nutrient_results", {}) or {}
    _is_multi_rep = len(_nr) > 1

    # ── 1. Trava Agronômica de Dose — POR SOLUTO (L2) ─────────────────────────
    # Multi-soluto: avalia cada dose individual; nunca o total no primário.
    _dose_alerts: list[str] = []
    if _is_multi_rep:
        for _s, _d in _nr.items():
            _dd = float(_d.get("dose_kg_ha", 0.0) or 0.0)
            _nm = str(_d.get("name", _s))
            _f, _a = _dose_sanity(_dd, _s, _nm)
            if _f:
                _dose_alerts.append(_a)
        dose_flag = len(_dose_alerts) > 0
        dose_alert = "\n".join(_dose_alerts)
    else:
        _prim_dose = float((_nr.get(nutrient_symbol, {}) or {}).get("dose_kg_ha", fertilizer_dose_kg_ha) or fertilizer_dose_kg_ha)
        dose_flag, dose_alert = _dose_sanity(_prim_dose, nutrient_symbol, nutrient_name)

    # ── 2. Alerta de Estresse Osmótico — POR SOLUTO, diluído na camada real (L2/L3)
    _osm_alerts: list[str] = []
    if _is_multi_rep:
        for _s, _d in _nr.items():
            _dd = float(_d.get("dose_kg_ha", 0.0) or 0.0)
            _nm = str(_d.get("name", _s))
            _rr = float(_d.get("retained_root_pct", 0.0) or 0.0)
            _fo, _ao = _osmotic_stress_check(_dd, soil, root_z, _nm, _s, _rr, active_depth_cm=active_depth_cm)
            if _fo:
                _osm_alerts.append(_ao)
        osmotic_flag = len(_osm_alerts) > 0
        osmotic_alert = "\n".join(_osm_alerts)
    else:
        _prim_dose2 = float((_nr.get(nutrient_symbol, {}) or {}).get("dose_kg_ha", fertilizer_dose_kg_ha) or fertilizer_dose_kg_ha)
        _prim_ret = float((_nr.get(nutrient_symbol, {}) or {}).get("retained_root_pct", retained_pct) or retained_pct)
        osmotic_flag, osmotic_alert = _osmotic_stress_check(
            _prim_dose2, soil, root_z, nutrient_name, nutrient_symbol, _prim_ret,
            active_depth_cm=active_depth_cm,
        )

    # ── 3. Soluto de referência p/ Kd efetivo e nota P (sem classificação) ──────
    _, _, _w_sym, _w_pct = _risk_banner(results, nutrient_symbol, pct, root_depth_cm=root_z, peak_cm=peak)

    # ── 4. Balanço Físico de Massa (soma por soluto; retained exclui uptaken) ──
    lost_kg_ha = _bal["lost_kg"]
    retained_kg_ha = _bal["retained_kg"]
    uptaken_kg_ha = _bal["uptaken_kg"]
    fertilizer_dose_kg_ha = _bal["total_dose"] if _bal["is_multi"] else fertilizer_dose_kg_ha

    # ── 5. Descrição física neutra por nutriente (sem recomendação, sem classificação) ───
    # Apenas balanço de massa; nenhuma sentença de alto/baixo/moderado/severo.
    tech_tip = (
        f"Retenção de {retained_pct:.1f}% na camada avaliada "
        f"e deslocamento de {pct:.1f}% além da camada."
    )

    # ── 6. Descrição física do cenário (sem recomendação, sem classificação) ──────
    _dose_lbl = f"{fertilizer_dose_kg_ha:,.0f} kg/ha do conjunto de solutos" if _bal["is_multi"] else f"{fertilizer_dose_kg_ha:,.0f} kg/ha de {nutrient_name}"
    _nut_lbl = "conjunto de solutos" if _bal["is_multi"] else nutrient_name
    if dose_flag:
        plan_diag = (
            f"A dose planejada de {_dose_lbl} apresenta concentração elevada nos primeiros centímetros. "
            f"Retenção estimada de {retained_pct:.1f}% na camada avaliada."
        )
        plan_rec = f"Descrição física: dose acima da referência. {tech_tip}"
    else:
        plan_diag = (
            f"Simulação sob chuva de {rain_mm:.0f} mm no {soil.name}: "
            f"retenção de {retained_pct:.1f}% na camada avaliada ({root_z:.0f} cm) "
            f"e deslocamento de {pct:.1f}% além da camada "
            f"({lost_kg_ha:.1f} kg/ha de {_nut_lbl})."
        )
        plan_rec = f"Descrição física: {tech_tip}"
    # Sem massa: não classificar o vazio — frase neutra única com hidrologia
    try:
        _tot_mass_chk = float(_bal.get("total_dose", fertilizer_dose_kg_ha) or 0.0)
    except (TypeError, ValueError):
        _tot_mass_chk = 0.0
    if _tot_mass_chk <= 1e-9:
        try:
            _d_mm = float(getattr(results, "q_bottom_cum_cm", 0.0) or 0.0) * 10.0
            _ro_mm = float(getattr(results, "runoff_cum_cm", 0.0) or 0.0) * 10.0
        except (TypeError, ValueError):
            _d_mm, _ro_mm = 0.0, 0.0
        plan_diag = (
            f"Ensaio sem massa aplicada (0 kg/ha): sem pico, sem retenção e sem lixiviação a classificar; "
            f"hidrologia: P={rain_mm:.0f}mm, D={_d_mm:.1f}mm, RO={_ro_mm:.1f}mm."
        )
        plan_rec = "Descrição física neutra: apenas balanço hídrico acima, sem soluto a descrever."

    # ── 7. Bloco de Tecnologia de Liberação ───────────────────────────────────
    tech_block = ""
    if is_controlled:
        prim_data = results.nutrient_results.get(nutrient_symbol, {})
        rel_kg = prim_data.get("released_kg_ha", fertilizer_dose_kg_ha * 0.1)
        cap_kg = prim_data.get("capsule_kg_ha", fertilizer_dose_kg_ha - rel_kg)
        if has_crop:
            _benefit = (f"* **Descrição física:** Sob a chuva de **{rain_mm:.0f} mm**, "
                        f"**{cap_kg:.1f} kg/ha** permanece na cápsula e **{rel_kg:.1f} kg/ha** solubilizado no período.")
        else:
            _benefit = (f"* **Descrição física:** Sob a chuva de **{rain_mm:.0f} mm**, "
                        f"**{cap_kg:.1f} kg/ha** permanece na cápsula e **{rel_kg:.1f} kg/ha** solubilizado no período.")
        tech_block = f"""
#### 🛡️ Tecnologia de Liberação Controlada (CRF / Polímero)
* **Duração Nominal da Liberação:** **{release_days:.0f} dias**
* **Nutriente Solubilizado no Período da Simulação:** **{rel_kg:.1f} kg/ha** ({ (rel_kg / max(fertilizer_dose_kg_ha, 1e-3)) * 100:.1f}% da dose)
* **Nutriente Protegido no Grânulo (Reserva Segura):** **{cap_kg:.1f} kg/ha** ({ (cap_kg / max(fertilizer_dose_kg_ha, 1e-3)) * 100:.1f}% protegido contra a enxurrada)
{_benefit}
"""

    # ── 8. Tabela Multi-Nutriente (se houver mais de 1 nutriente) ─────────────
    multi_table_block = ""
    is_multi = hasattr(results, "nutrient_results") and len(results.nutrient_results) > 1
    if is_multi:
        rows = []
        for s_sym, s_data in results.nutrient_results.items():
            s_lost_kg = s_data["leached_kg_ha"]
            try:
                _ke_row, _kdif_row = _kd_eff_display(s_data, float(s_data.get("kd", 0.0)))
                _kd_txt = f"{float(s_data.get('kd', 0.0)):.3f}" if not _kdif_row else f"{float(s_data.get('kd', 0.0)):.3f} (efet. {_ke_row:.3f})"
            except Exception:
                _kd_txt = f"{s_data['kd']:.3f}"
            rows.append(
                f"| **{s_data['name']}** | {s_sym} | {s_data['dose_kg_ha']:.0f} kg/ha | {_kd_txt} | "
                f"{_fmt_peak(s_data['peak_depth_cm'])} | {s_data['retained_root_pct']:.1f}% | {s_data['leaching_ratio_pct']:.1f}% | "
                f"{float(s_data.get('leached_bottom_pct', 0.0)):.1f}% | {s_lost_kg:.1f} kg/ha |"
            )
        multi_table_block = f"""
#### 🧪 Comparativo da Formulação Multi-Nutriente
| Nutriente | Símbolo | Dose | Kd (cm³/g) | Pico | Retenção Camada | Lixiviação | Fundo | Perda no Subsolo |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
""" + "\n".join(rows) + "\n"

    # ── 9. Montagem do Laudo Técnico Oficial ─────────────────────────────────
    alerts_block = ""
    if dose_alert:
        alerts_block += f"\n{dose_alert}\n"
    if osmotic_alert:
        alerts_block += f"\n{osmotic_alert}\n"

    if is_multi:
        _n_sol = len(results.nutrient_results)
        _sol_list = ", ".join(f"{d['name']} ({s})" for s, d in results.nutrient_results.items())
        solutes_header = (f"* **Formulação Multi-Soluto:** **{_n_sol} solutos independentes** "
                          f"({_sol_list}) | **Dose Total Aplicada:** **{fertilizer_dose_kg_ha:,.0f} kg/ha**")
        soluto_ref = "conjunto de solutos"
    else:
        solutes_header = (f"* **Nutriente Avaliado:** {nutrient_name} ({nutrient_symbol}) | "
                          f"**Dose Aplicada:** **{fertilizer_dose_kg_ha:,.0f} kg/ha**")
        soluto_ref = nutrient_name

    _crop_line = (f"* **Cultura & Estádio:** {crop.name} (Profundidade Radicular Efetiva: **{root_z:.0f} cm**)"
                  if has_crop else f"* **Cultura:** Sem cultura | **Camada Avaliada:** **{root_z:.0f} cm**")
    _upt_line = (f"\n* **Absorvido (passivo, sem teto nutricional):** **{uptaken_pct:.1f}%** ({uptaken_kg_ha:,.1f} kg/ha de {soluto_ref}) — transporte passivo via transpiração; sem demanda máxima da planta"
                 if float(uptaken_pct or 0.0) > 0.05 else "")
    # (L4) R calculado exibido; (L10) Kd efetivo quando difere do nominal
    _theta_ref_adv = max(0.15, float(soil.theta_s) * 0.75)
    _r_adv = 1.0 + (float(soil.bulk_density) * float(kd_used)) / _theta_ref_adv
    try:
        _prim_nr_adv = (_nr.get(_w_sym, {}) or {}) if _is_multi_rep else (_nr.get(nutrient_symbol, {}) or {})
        _kd_eff_adv, _kd_differs = _kd_eff_display(_prim_nr_adv, float(kd_used))
    except Exception:
        _kd_eff_adv, _kd_differs = float(kd_used), False
    if _kd_differs:
        _kd_line = (f"* **Adsorção Linear (Kd nominal):** {kd_used:.3f} cm³/g *(Fonte: {kd_citation})* | "
                    f"**Kd efetivo usado no transporte:** {_kd_eff_adv:.4f} cm³/g (competição Ca/Langmuir)")
    else:
        _kd_line = f"* **Adsorção Linear (Kd):** {kd_used:.3f} cm³/g *(Fonte: {kd_citation})*"
    _kd_line += " — valor de referência para a textura do solo (ajustável na tabela de nutrientes; não calibrado para este talhão)"
    _r_line = (f"* **Fator de Retardo calculado ($R = 1 + ρb·Kd/θ$):** **{_r_adv:.2f}** "
               f"*(R = 1 indica transporte conservativo; R > 1 indica retenção por adsorção)*")
    _p_note_block = ""
    try:
        _has_p = ("P" in (_nr.keys() if _nr else [])) or nutrient_symbol == "P" or _w_sym == "P"
    except Exception:
        _has_p = nutrient_symbol == "P"
    if _has_p:
        _p_note_block = f"\n{P_UNIT_NOTE}"
    # Balanço hídrico completo (P = E + T + D + RO + ΔS + resíduo).
    try:
        _eA = float(getattr(results, "evap_cum_cm", 0.0) or 0.0) * 10.0
        _tA = float(getattr(results, "transp_cum_cm", 0.0) or 0.0) * 10.0
        _dA = float(getattr(results, "q_bottom_cum_cm", 0.0) or 0.0) * 10.0
        _roA = float(getattr(results, "runoff_cum_cm", 0.0) or 0.0) * 10.0
        import numpy as _npA
        _zA = _npA.asarray(getattr(results, "z", []), dtype=float)
        _dzA = float(_zA[1] - _zA[0]) if _zA.size > 1 else 1.0
        _thA = getattr(results, "theta_profiles", []) or []
        if len(_thA) >= 2:
            _stA = float(_npA.sum(_npA.asarray(_thA[-1], dtype=float) - _npA.asarray(_thA[0], dtype=float)) * _dzA) * 10.0
        else:
            _stA = 0.0
        _clA = float(rain_mm) - (_eA + _tA + _dA + _roA + _stA)
        _hydro_block = (
            f"* **Evapotranspiração real (E+T):** **{_eA + _tA:.1f} mm** (E {_eA:.1f} + T {_tA:.1f} mm)\n"
            f"* **Escoamento superficial (RO):** **{_roA:.1f} mm**\n"
            f"* **Δ Armazenamento no perfil (θf−θi):** **{_stA:+.1f} mm**\n"
            f"* **Resíduo de fechamento hídrico:** **{_clA:+.2f} mm**"
        )
    except Exception:
        _hydro_block = ""
    report = f"""### Laudo Técnico Agronômico & Dinâmica de Nutrientes no Solo
{alerts_block}
#### 1. Parâmetros do Cenário Operacional
{solutes_header}
{_crop_line}
* **Solo:** {soil.name} | **Lâmina de Chuva / Irrigação:** **{rain_mm:.0f} mm**
* **Padrão de Liberação:** **{'Liberação Controlada / Lenta (' + str(int(release_days)) + ' dias)' if is_controlled else 'Convencional (Solubilização Instantânea)'}**
{_kd_line}
{_r_line}
{tech_block}
{multi_table_block}{_p_note_block}
#### 2. Balanço Físico da Modelagem
* **Profundidade do Pico Máximo de Concentração:** **{_fmt_peak(peak)}**
* **Nutriente Retido na Camada Avaliada (0–{root_z:.0f} cm):** **{retained_pct:.1f}%** ({retained_kg_ha:,.1f} kg/ha de {soluto_ref})
* **Nutriente Perdido além da Camada Avaliada (Lixiviação):** **{pct:.1f}%** ({lost_kg_ha:,.1f} kg/ha de {soluto_ref}){_upt_line}
* **Atravessou o fundo do perfil:** **{float(((_nr.get(nutrient_symbol, {}) or {}) if not _is_multi_rep else (_nr.get(_w_sym, {}) or {})).get('leached_bottom_pct', 0.0) or 0.0):.1f}%**
* **Drenagem Profunda Acumulada no Fundo:** {results.q_bottom_cum_cm * 10.0:.1f} mm
{_hydro_block}

#### 3. Descrição Física do Cenário (sem recomendação)
* **Descrição da Simulação:**  
  {plan_diag}  
* **Descrição Física Neutra:**  
  {plan_rec}

{SCOPE_NOTE}""".strip()
    return report


def generate_column_report(
    results: SimulationResults,
    soil: SoilParameters,
    rain_mm: float,
    fertilizer_dose_kg_ha: float,
    target_depth_cm: float = 30.0,
    column_height_cm: float = 70.0,
    nutrient_symbol: str = "K",
    nutrient_name: str = "Potássio",
    kd_used: float = 0.0,
    kd_citation: str = "Literatura",
    release_type: str = "immediate",
    release_days: float = 60.0,
    total_days: float = 7.0,
    active_depth_cm: float = 0.0,
    runoff_mm: float = None,
    storage_mm: float = None,
    evap_mm_day: float = None,
    transp_mm_day: float = None,
    et0_mm_day: float = None,
) -> str:
    _bal = _mass_totals(results, fertilizer_dose_kg_ha, nutrient_symbol)
    pct = _bal["pct"]
    retained_pct = _bal["retained_pct"]
    uptaken_pct = _bal["uptaken_pct"]
    peak = results.peak_depth_cm
    is_controlled = release_type in ["controlled", "liberacao_controlada"]
    _nr_c = getattr(results, "nutrient_results", {}) or {}
    _is_multi_c = len(_nr_c) > 1

    # Trava de dose — POR SOLUTO (L2): nunca o total no primário
    if _is_multi_c:
        _da = []
        for _s, _d in _nr_c.items():
            _f, _a = _dose_sanity(float(_d.get("dose_kg_ha", 0.0) or 0.0), _s, str(_d.get("name", _s)))
            if _f:
                _da.append(_a)
        dose_flag = len(_da) > 0
        dose_alert = "\n".join(_da)
    else:
        _pd = float((_nr_c.get(nutrient_symbol, {}) or {}).get("dose_kg_ha", fertilizer_dose_kg_ha) or fertilizer_dose_kg_ha)
        dose_flag, dose_alert = _dose_sanity(_pd, nutrient_symbol, nutrient_name)

    # Soluto de referência p/ Kd efetivo e nota P (sem classificação)
    _, _, _w_sym, _w_pct = _column_risk_banner(results, nutrient_symbol, pct, target_depth_cm)

    # Balanço de massa real (soma por soluto; retained exclui uptaken)
    lost_kg_ha = _bal["lost_kg"]
    retained_kg_ha = _bal["retained_kg"]
    uptaken_kg_ha = _bal["uptaken_kg"]
    fertilizer_dose_kg_ha = _bal["total_dose"] if _bal["is_multi"] else fertilizer_dose_kg_ha

    # Fator de retardo R = 1 + (rho_b * Kd) / theta_medio
    theta_ref = max(0.15, soil.theta_s * 0.75)
    r_factor = 1.0 + (soil.bulk_density * float(kd_used)) / theta_ref

    # Bloco de Tecnologia de Liberação Controlada
    tech_block = ""
    if is_controlled:
        prim_data = results.nutrient_results.get(nutrient_symbol, {})
        rel_kg = prim_data.get("released_kg_ha", fertilizer_dose_kg_ha * 0.1)
        cap_kg = prim_data.get("capsule_kg_ha", fertilizer_dose_kg_ha - rel_kg)
        tech_block = f"""
#### 🛡️ Tecnologia de Liberação Controlada (CRF / Polímero)
* **Duração Nominal da Liberação:** **{release_days:.0f} dias**
* **Nutriente Solubilizado no Ensaio ({total_days:.0f} dias):** **{rel_kg:.1f} kg/ha** ({ (rel_kg / max(fertilizer_dose_kg_ha, 1e-3)) * 100:.1f}% da dose)
* **Nutriente Protegido no Grânulo (Reserva Intacta):** **{cap_kg:.1f} kg/ha** ({ (cap_kg / max(fertilizer_dose_kg_ha, 1e-3)) * 100:.1f}% imune à lixiviação imediata)
* **Efeito no Ensaio de Coluna:** A taxa de liberação lenta protegeu {cap_kg:.1f} kg/ha do pico inicial de eluição sob a lâmina de {rain_mm:.0f} mm, amortecendo a frente de lavagem vertical.
"""

    # Tabela Multi-Nutriente
    multi_table_block = ""
    is_multi = hasattr(results, "nutrient_results") and len(results.nutrient_results) > 1
    if is_multi:
        rows = []
        for s_sym, s_data in results.nutrient_results.items():
            s_lost_kg = s_data["leached_kg_ha"]
            try:
                _ke_c, _kdif_c = _kd_eff_display(s_data, float(s_data.get("kd", 0.0)))
                _kd_txt_c = f"{float(s_data.get('kd', 0.0)):.3f}" if not _kdif_c else f"{float(s_data.get('kd', 0.0)):.3f} (efet. {_ke_c:.3f})"
            except Exception:
                _kd_txt_c = f"{s_data['kd']:.3f}"
            rows.append(
                f"| **{s_data['name']}** | {s_sym} | {s_data['dose_kg_ha']:.0f} kg/ha | {_kd_txt_c} | "
                f"{_fmt_peak(s_data['peak_depth_cm'])} | {s_data['retained_root_pct']:.1f}% | {s_data['leaching_ratio_pct']:.1f}% | "
                f"{float(s_data.get('leached_bottom_pct', 0.0)):.1f}% | {s_lost_kg:.1f} kg/ha |"
            )
        multi_table_block = f"""
#### 🧪 Comparativo Experimental Multi-Nutriente na Coluna
| Nutriente | Símbolo | Dose | Kd (cm³/g) | Pico | Retenção (0–{target_depth_cm:.0f} cm) | Lixiviação | Fundo | Deslocamento |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
""" + "\n".join(rows) + "\n"

    alerts_block = f"\n{dose_alert}\n" if dose_alert else ""

    # Abertura do deslocado: abaixo na coluna vs. atravessou o fundo.
    try:
        _prim_c = (_nr_c.get(nutrient_symbol, {}) or {}) if not _is_multi_c else {}
        _bot_col = float(_prim_c.get("leached_bottom_pct", 0.0) or 0.0)
    except (TypeError, ValueError):
        _bot_col = 0.0
    _below_col = max(0.0, float(pct or 0.0) - _bot_col)
    if _is_multi_c:
        _fundo_col_line = ""
        for _s, _d in _nr_c.items():
            try:
                _b = float((_d or {}).get("leached_bottom_pct", 0.0) or 0.0)
            except (TypeError, ValueError):
                _b = 0.0
            _fundo_col_line += f"\n* **Atravessou o fundo ({_s}):** **{_b:.1f}%** ({float((_d or {}).get('dose_kg_ha', 0.0) or 0.0) * _b / 100.0:.1f} kg/ha)"
    else:
        _fundo_col_line = f"\n* **Atravessou o fundo (coluna {column_height_cm:.0f} cm):** **{_bot_col:.1f}%** ({fertilizer_dose_kg_ha * _bot_col / 100.0:.1f} kg/ha)"
    _scope_col = f"\n\n{SCOPE_NOTE}"

    # Drenagem em mm (+ RO/armazenamento/ET quando existirem — L11)
    drainage_mm = results.q_bottom_cum_cm * 10.0
    try:
        _ro_mm = float(runoff_mm) if runoff_mm is not None else float(getattr(results, "runoff_cum_cm", 0.0) or 0.0) * 10.0
    except (TypeError, ValueError):
        _ro_mm = 0.0
    _stor_mm = storage_mm
    _has_stor = _stor_mm is not None
    try:
        _stor_f = float(_stor_mm) if _has_stor else 0.0
    except (TypeError, ValueError):
        _stor_f, _has_stor = 0.0, False
    _hydro_extra = ""
    if _ro_mm > 0.005:
        _hydro_extra += f"\n* **Escoamento Superficial (RO):** **{_ro_mm:.1f} mm**"
    if _has_stor:
        _hydro_extra += f"\n* **Δ Armazenamento no Perfil (θf−θi):** **{_stor_f:+.1f} mm**"
    _et_line = ""
    try:
        if evap_mm_day is not None or transp_mm_day is not None or et0_mm_day is not None:
            _e = float(evap_mm_day or 0.0)
            _t = float(transp_mm_day or 0.0)
            _et0 = float(et0_mm_day or 0.0)
            _et_txt = f"{(_e + _t) * float(total_days or 0.0):.1f} mm no período"
            if _et0 > 0:
                _et_txt += f" (ET0 {_et0:.2f} mm/dia; E {_e:.2f} + T {_t:.2f} mm/dia)"
            _et_line = f"\n* **Evapotranspiração (ET):** **{_et_txt}**"
    except (TypeError, ValueError):
        _et_line = ""
    # Resíduo de fechamento hídrico (P − E − T − D − RO − ΔS).
    try:
        _eC = float(evap_mm_day or 0.0) * float(total_days or 0.0)
        _tC = float(transp_mm_day or 0.0) * float(total_days or 0.0)
        _clC = float(rain_mm) - (_eC + _tC + float(drainage_mm) + float(_ro_mm) + float(_stor_f if _has_stor else 0.0))
        _closure_col_line = f"\n* **Resíduo de fechamento hídrico:** **{_clC:+.2f} mm**"
    except (TypeError, ValueError):
        _closure_col_line = ""
    # (L10) Kd efetivo no laudo coluna
    try:
        _nr_kd_c = (_nr_c.get(_w_sym, {}) or {}) if _is_multi_c else (_nr_c.get(nutrient_symbol, {}) or {})
        _kd_eff_c, _kd_dif_c = _kd_eff_display(_nr_kd_c, float(kd_used))
    except Exception:
        _kd_eff_c, _kd_dif_c = float(kd_used or 0.0), False
    if _kd_dif_c:
        _kd_col_line = (f"* **Coeficiente de Adsorção Linear ($K_d$ nominal):** **{float(kd_used):.4f} cm³/g** *(Fonte: {kd_citation})* | "
                        f"**Kd efetivo usado:** **{_kd_eff_c:.4f} cm³/g**")
    else:
        _kd_col_line = f"* **Coeficiente de Adsorção Linear ($K_d$):** **{float(kd_used):.4f} cm³/g** *(Fonte: {kd_citation})*"
    _kd_col_line += " — valor de referência para a textura do solo (ajustável na tabela de nutrientes; não calibrado para este talhão)"
    try:
        _has_p_c = ("P" in (_nr_c.keys() if _nr_c else [])) or nutrient_symbol == "P" or _w_sym == "P"
    except Exception:
        _has_p_c = nutrient_symbol == "P"
    _p_note_c = f"\n{P_UNIT_NOTE}" if _has_p_c else ""

    if is_multi:
        _n_sol = len(results.nutrient_results)
        _sol_list = ", ".join(f"{d['name']} ({s})" for s, d in results.nutrient_results.items())
        solutes_header = (f"* **Formulação Multi-Soluto:** **{_n_sol} solutos independentes** "
                          f"({_sol_list}) | **Dose Total Aplicada:** **{fertilizer_dose_kg_ha:,.0f} kg/ha**")
        soluto_ref = "conjunto de solutos"
    else:
        solutes_header = (f"* **Nutriente / Soluto:** {nutrient_name} ({nutrient_symbol}) | "
                          f"**Dose Aplicada:** **{fertilizer_dose_kg_ha:,.0f} kg/ha**")
        soluto_ref = nutrient_name

    try:
        _tot_mass_col = float(_bal.get("total_dose", fertilizer_dose_kg_ha) or 0.0)
    except (TypeError, ValueError):
        _tot_mass_col = 0.0
    if _tot_mass_col <= 1e-9:
        _col_diag = (
            f"Ensaio sem massa aplicada (0 kg/ha): sem pico, sem retenção e sem deslocamento a classificar; "
            f"hidrologia: P={rain_mm:.0f}mm, D={drainage_mm:.1f}mm."
        )
        _col_neut = "Descrição física neutra: apenas balanço hídrico acima, sem soluto a descrever."
    else:
        _col_diag = (
            f"Sob a lâmina aplicada de **{rain_mm:.0f} mm**, pico de concentração do {soluto_ref} em **{_fmt_peak(peak)}**. "
            f"Retenção de **{retained_pct:.1f}%** na camada avaliada e deslocamento de **{pct:.1f}%** além da camada."
        )
        _col_neut = (
            "Descrição física: balanço de massa apresentado acima, sem recomendação."
        )

    report = f"""### Laudo Técnico Experimental — Dinâmica de Solutos em Coluna de Solo
{alerts_block}
#### 1. Geometria da Coluna & Condições Experimentais
* **Altura Total da Coluna:** **{column_height_cm:.0f} cm** | **Camada de Avaliação:** **0 a {target_depth_cm:.0f} cm**
* **Solo Utilizado:** {soil.name} (Densidade: {soil.bulk_density:.2f} g/cm³, θs: {soil.theta_s * 100:.1f}%, Ks: {soil.ks:.1f} cm/dia)
{solutes_header}
* **Regime Hídrico:** Lâmina de **{rain_mm:.0f} mm** ao longo de **{total_days:.0f} dias** de ensaio
{_kd_col_line}
* **Fator de Retardo Teórico ($R$):** **{r_factor:.2f}** *(R calculado = 1 + ρb·Kd/θ; R = 1 indica transporte conservativo; R > 1 indica retenção por adsorção/troca catiônica)*
{tech_block}
{multi_table_block}{_p_note_c}
#### 2. Balanço Físico de Massa & Perfil de Concentração
* **Profundidade do Pico de Concentração Máxima:** **{_fmt_peak(peak)}**
* **Retenção na Camada de Interesse (0–{target_depth_cm:.0f} cm):** **{retained_pct:.1f}%** ({retained_kg_ha:,.1f} kg/ha)
* **Deslocamento além da Camada (> {target_depth_cm:.0f} cm):** **{pct:.1f}%** ({lost_kg_ha:,.1f} kg/ha){chr(10) + f"* **Absorvido (passivo, sem teto nutricional):** **{uptaken_pct:.1f}%** ({uptaken_kg_ha:,.1f} kg/ha) — transporte passivo via transpiração; sem demanda máxima da planta" if float(uptaken_pct or 0.0) > 0.05 else ""}{_fundo_col_line}
* **Drenagem Acumulada no Fundo da Coluna:** **{drainage_mm:.1f} mm**{_hydro_extra}{_et_line}{_closure_col_line}

#### 3. Descrição Física do Soluto (sem recomendação)
* **Comportamento do Soluto na Matriz do Solo:**  
  {_col_diag}
* **Descrição Física Neutra:**  
  {_col_neut}{_scope_col}""".strip()
    return report


# Backward compatibility alias
def generate_field_report(results, soil, crop, rain_mm, n_dose_kg_ha):
    return generate_advanced_report(
        results=results,
        soil=soil,
        crop=crop,
        rain_mm=rain_mm,
        fertilizer_dose_kg_ha=n_dose_kg_ha,
        nutrient_symbol="N",
        nutrient_name="Nitrogênio",
        mode="planejamento",
        kd_used=0.0,
        kd_citation="Literatura SSSA (Sparks et al., 1996)"
    )
