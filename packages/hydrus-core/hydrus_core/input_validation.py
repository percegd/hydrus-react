"""Validadores de formato + faixa fisica para os inputs da UI (app_gradio.py).

REGRA DO DONO: sem teto de dose — dose positiva NUNCA e bloqueada; erro so para
formato invalido (texto em campo numerico, token invalido, vazio onde obrigatorio)
ou fisicamente impossivel (theta fora de (0,1), n<=1, valor negativo onde a fisica
exige >= 0, limiar de Feddes >= 0 ou fora de ordem etc.).

Uso:
    issues = validate_payload(payload_dict)   # lista completa p/ o modal de erro
    if issues: raise issue.as_error()         # chamada direta/API: ValueError laico

O payload e um dict {nome_do_parametro: valor} (run usa dict(locals())).
Chaves ausentes sao ignoradas (permite validar subconjuntos nos gates de etapa).
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Inventario de inputs (componente / var / elem_id / tipo / range fisico)
# ---------------------------------------------------------------------------
# Formato: (componente, var, elem_id, tipo_ui, range_fisico). elem_id "-" =
# campo oculto/compat (sem borda) ou sem validacao propria.
INPUT_INVENTORY: List[tuple] = [
    # Passo 1 — solo
    ("Dropdown", "soil_choice", "val-soil-choice", "lista fixa", "opcao valida ou personalizado"),
    ("Checkbox", "is_custom_soil", "-", "bool", "-"),
    ("Slider", "sand_pct", "val-sand", "0-100", "[0, 100]; soma areia+argila <= 100"),
    ("Slider", "clay_pct", "val-clay", "0-100", "[0, 100]; soma areia+argila <= 100"),
    ("Number", "adv_theta_r", "val-theta-r", "float", "(0, 1) e < theta_s"),
    ("Number", "adv_theta_s", "val-theta-s", "float", "(0, 1) e > theta_r"),
    ("Number", "adv_alpha", "val-alpha", "float", "> 0"),
    ("Number", "adv_n", "val-n", "float", "> 1.05"),
    ("Number", "adv_ks", "val-ks", "float", "> 0"),
    ("Number", "adv_bulk_density", "val-bulk-density", "float", "(0, 3.0]"),
    ("Number", "adv_kd", "-", "float oculto/compat", "-"),
    ("Number", "initial_residual_mg_dm3", "-", "float oculto/compat", "-"),
    ("Checkbox", "show_adv", "-", "bool oculto", "-"),
    ("Number", "domain_depth_cm", "val-domain-depth", "float", "[1, 500] cm"),
    ("Number", "adv_disp", "val-disp", "float", ">= 0"),
    ("Textbox", "print_days_text", "val-print-days", "lista '1,2,3'", "passo 3; dentro da duracao/janela; vazio bloqueia"),
    ("Number", "analysis_start_day", "val-analysis-start", "int", "[1, 365], <= fim; serie/upload"),
    ("Number", "analysis_end_day", "val-analysis-end", "int", "[1, 365], >= inicio; serie/upload"),
    ("Textbox", "obs_depths_text", "val-obs-depths", "lista '10,20,30'", "tokens numericos em (0, dominio]"),
    # Passo 1 — cultura
    ("Radio", "crop_mode", "val-crop-mode", "2 opcoes", "-"),
    ("Textbox", "crop_name", "val-crop-name", "texto", "nao-vazio se com cultura"),
    ("Number", "crop_root_depth", "val-root-depth", "float", "> 0"),
    ("Number", "crop_kc", "val-kc", "float", "> 0 (sem teto)"),
    ("Number", "crop_h1", "val-h1", "float", "< 0 e h1>h2>h3>h4"),
    ("Number", "crop_h2", "val-h2", "float", "< 0 e h1>h2>h3>h4"),
    ("Number", "crop_h3", "val-h3", "float", "< 0 e h1>h2>h3>h4"),
    ("Number", "crop_h4", "val-h4", "float", "< 0 e h1>h2>h3>h4"),
    # Modal fertilizante comercial
    ("Dropdown", "fert_choice", "val-fert-choice", "lista fixa", "-"),
    ("Number", "gross_dose", "val-gross-dose", "float", ">= 0 (sem teto)"),
    # Passo 2 — modo + compat
    ("Radio", "simulation_mode", "val-simulation-mode", "2 opcoes", "opcao valida"),
    ("Radio", "fert_mode", "-", "oculto/compat", "-"),
    ("Radio", "nutr_mode", "-", "oculto/compat", "-"),
    ("Dropdown", "nutrient_choice", "-", "oculto/compat", "-"),
    ("Number", "elemental_dose", "-", "oculto/compat", "-"),
    ("Textbox", "custom_fert_name", "-", "oculto/compat", "-"),
    ("Number", "custom_n_pct", "-", "oculto/compat", "-"),
    ("Number", "custom_k_pct", "-", "oculto/compat", "-"),
    ("Number", "custom_p_pct", "-", "oculto/compat", "-"),
    ("Number", "custom_s_pct", "-", "oculto/compat", "-"),
    ("Number", "custom_ca_pct", "-", "oculto/compat", "-"),
    ("Number", "custom_mg_pct", "-", "oculto/compat", "-"),
    ("Dropdown", "blend_preset", "-", "oculto/compat", "-"),
    # Passo 2 — tabela N/K/P/S/Ca/Mg (6 x active/dose/kd/disp/res)
    ("Checkbox", "multi_n_active", "-", "bool", "-"),
    ("Number", "multi_n_dose", "val-dose-N", "float", ">= 0 se ativo (sem teto); >0 p/ simular"),
    ("Number", "multi_n_kd", "val-kd-N", "float", ">= 0"),
    ("Number", "multi_n_disp", "val-disp-N", "float", ">= 0"),
    ("Number", "multi_n_res", "val-res-N", "float", ">= 0"),
    ("Checkbox", "multi_k_active", "-", "bool", "-"),
    ("Number", "multi_k_dose", "val-dose-K", "float", ">= 0 se ativo (sem teto); >0 p/ simular"),
    ("Number", "multi_k_kd", "val-kd-K", "float", ">= 0"),
    ("Number", "multi_k_disp", "val-disp-K", "float", ">= 0"),
    ("Number", "multi_k_res", "val-res-K", "float", ">= 0"),
    ("Checkbox", "multi_p_active", "-", "bool", "-"),
    ("Number", "multi_p_dose", "val-dose-P", "float", ">= 0 se ativo (sem teto); >0 p/ simular"),
    ("Number", "multi_p_kd", "val-kd-P", "float", ">= 0"),
    ("Number", "multi_p_disp", "val-disp-P", "float", ">= 0"),
    ("Number", "multi_p_res", "val-res-P", "float", ">= 0"),
    ("Checkbox", "multi_s_active", "-", "bool", "-"),
    ("Number", "multi_s_dose", "val-dose-S", "float", ">= 0 se ativo (sem teto); >0 p/ simular"),
    ("Number", "multi_s_kd", "val-kd-S", "float", ">= 0"),
    ("Number", "multi_s_disp", "val-disp-S", "float", ">= 0"),
    ("Number", "multi_s_res", "val-res-S", "float", ">= 0"),
    ("Checkbox", "multi_ca_active", "-", "bool", "-"),
    ("Number", "multi_ca_dose", "val-dose-Ca", "float", ">= 0 se ativo (sem teto); >0 p/ simular"),
    ("Number", "multi_ca_kd", "val-kd-Ca", "float", ">= 0"),
    ("Number", "multi_ca_disp", "val-disp-Ca", "float", ">= 0"),
    ("Number", "multi_ca_res", "val-res-Ca", "float", ">= 0"),
    ("Checkbox", "multi_mg_active", "-", "bool", "-"),
    ("Number", "multi_mg_dose", "val-dose-Mg", "float", ">= 0 se ativo (sem teto); >0 p/ simular"),
    ("Number", "multi_mg_kd", "val-kd-Mg", "float", ">= 0"),
    ("Number", "multi_mg_disp", "val-disp-Mg", "float", ">= 0"),
    ("Number", "multi_mg_res", "val-res-Mg", "float", ">= 0"),
    # Passo 2 — 3 linhas "Outro soluto" (active/name/dose/kd/disp/res)
    ("Checkbox", "multi_x_active", "-", "bool", "-"),
    ("Textbox", "multi_x_name", "val-name-X", "texto", "nao-vazio se ativo (bloqueante)"),
    ("Number", "multi_x_dose", "val-dose-X", "float", ">= 0 se ativo (sem teto); >0 p/ simular"),
    ("Number", "multi_x_kd", "val-kd-X", "float", ">= 0"),
    ("Number", "multi_x_disp", "val-disp-X", "float", ">= 0"),
    ("Number", "multi_x_res", "val-res-X", "float", ">= 0"),
    ("Checkbox", "multi_x2_active", "-", "bool", "-"),
    ("Textbox", "multi_x2_name", "val-name-X2", "texto", "nao-vazio se ativo (bloqueante)"),
    ("Number", "multi_x2_dose", "val-dose-X2", "float", ">= 0 se ativo (sem teto); >0 p/ simular"),
    ("Number", "multi_x2_kd", "val-kd-X2", "float", ">= 0"),
    ("Number", "multi_x2_disp", "val-disp-X2", "float", ">= 0"),
    ("Number", "multi_x2_res", "val-res-X2", "float", ">= 0"),
    ("Checkbox", "multi_x3_active", "-", "bool", "-"),
    ("Textbox", "multi_x3_name", "val-name-X3", "texto", "nao-vazio se ativo (bloqueante)"),
    ("Number", "multi_x3_dose", "val-dose-X3", "float", ">= 0 se ativo (sem teto); >0 p/ simular"),
    ("Number", "multi_x3_kd", "val-kd-X3", "float", ">= 0"),
    ("Number", "multi_x3_disp", "val-disp-X3", "float", ">= 0"),
    ("Number", "multi_x3_res", "val-res-X3", "float", ">= 0"),
    # Passo 2 — liberacao + posicionamento
    ("Radio", "release_type", "-", "2 opcoes", "-"),
    ("Number", "release_days", "val-release-days", "float", "> 0 se controlada"),
    ("Radio", "placement_mode", "-", "4 opcoes", "-"),
    ("Number", "z_app_top_cm", "val-z-top", "float", ">= 0 (se personalizada)"),
    ("Number", "z_app_bottom_cm", "val-z-bottom", "float", "> De (se personalizada)"),
    ("Number", "fert_c0_mg_l", "val-fert-c0", "float", ">= 0 (se fertirrigacao)"),
    ("Number", "fert_pulse_days", "val-fert-pulse", "float", ">= 0 (se fertirrigacao)"),
    # Passo 3 — regime hidrico
    ("Radio", "water_source", "-", "3 opcoes", "sem restricao estrita (strings legadas em testes)"),
    ("Number", "rain_mm", "val-rain", "float", ">= 0"),
    ("Number", "initial_moisture_pct", "val-moisture", "float", ">= 0 (sem teto: %CC pode passar de 100)"),
    ("Number", "total_days", "val-total-days", "float", "> 0"),
    ("Number", "et0_mm_day", "val-et0", "float", ">= 0"),
    ("Checkbox", "adv_et_toggle", "-", "bool", "-"),
    ("Number", "evap_mm_day", "val-evap", "float", ">= 0"),
    ("Number", "transp_mm_day", "val-transp", "float", ">= 0"),
    ("Dropdown", "hub_choice", "-", "lista polos", "-"),
    ("Radio", "scenario_choice", "-", "cenarios", "-"),
    ("Number", "app_day", "val-app-day", "float", "vazio/0 = ignora; senão [1, 365]"),
    ("Dataframe", "climate_table_data", "-", "365x3", "chuva obrigatoria (cheque proprio na UI)"),
    ("Number", "app_day_upload", "val-app-day-upload", "float", "vazio/0 = ignora; senão [1, 365]"),
    ("Dataframe", "climate_table_upload_data", "-", "365x3", "chuva obrigatoria (cheque proprio na UI)"),
    # Resultado / modal cultura
    ("Dropdown", "solute_view_select", "-", "saida/navegacao", "-"),
    ("Radio", "crop_picker", "-", "lista culturas", "-"),
]
N_INPUTS = len(INPUT_INVENTORY)

NUTRIENT_SYMBOLS = ("N", "K", "P", "S", "Ca", "Mg")
CUSTOM_ROWS = (
    ("multi_x", "Outro soluto", "X"),
    ("multi_x2", "Outro soluto 2", "X2"),
    ("multi_x3", "Outro soluto 3", "X3"),
)
SIM_MODES = ("Água + nutrientes", "Somente água")


@dataclass
class ValidationIssue:
    field: str
    label: str
    elem_id: str
    message: str

    def as_error(self, error_cls=ValueError) -> ValueError:
        err = error_cls(self.message)
        try:
            err.field = self.field  # type: ignore[attr-defined]
            err.elem_id = self.elem_id  # type: ignore[attr-defined]
        except Exception:
            pass
        return err


def _blank(v: Any) -> bool:
    return v is None or (isinstance(v, str) and not v.strip()) or (isinstance(v, float) and str(v) == "nan")


def _to_float(v: Any) -> Optional[float]:
    """float tolerante a str com virgula; None se vazio/invalido (sem levantar)."""
    if v is None or (isinstance(v, bool)):
        return None if v is None else float(v)
    if isinstance(v, (int, float)):
        try:
            import math
            f = float(v)
            return None if math.isnan(f) or math.isinf(f) else f
        except Exception:
            return None
    s = str(v).strip().replace(",", ".")
    if not s or s.lower() in ("none", "nan", "inf", "+inf", "-inf"):
        return None
    try:
        import math
        f = float(s)
        return None if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return None


def _num(p: Dict[str, Any], key: str, label: str, elem_id: str, out: List[ValidationIssue],
         *, required: bool = True, minimum: Optional[float] = None, maximum: Optional[float] = None,
         min_exclusive: bool = False, max_exclusive: bool = False,
         zero_blank: bool = False) -> Optional[float]:
    """Valida um campo numerico. Retorna o float ou None (com issue registrada)."""
    if key not in p:
        return None
    v = p[key]
    if _blank(v):
        if required:
            out.append(ValidationIssue(key, label, elem_id, f"{label} deve ser numérico."))
        return None
    f = _to_float(v)
    if f is None:
        out.append(ValidationIssue(key, label, elem_id, f"{label} deve ser numérico."))
        return None
    if zero_blank and f == 0:
        return None
    if minimum is not None and (f < minimum or (min_exclusive and f == minimum)):
        op = ">" if min_exclusive else "≥"
        out.append(ValidationIssue(key, label, elem_id, f"{label} = {f} é fisicamente impossível: exige-se {op} {minimum}."))
        return None
    if maximum is not None and (f > maximum or (max_exclusive and f == maximum)):
        op = "<" if max_exclusive else "≤"
        out.append(ValidationIssue(key, label, elem_id, f"{label} = {f} é fisicamente impossível: exige-se {op} {maximum}."))
        return None
    return f


# ---------------------------------------------------------------------------
# Grupos
# ---------------------------------------------------------------------------
def validate_soil(p: Dict[str, Any], out: List[ValidationIssue]) -> None:
    thr = _num(p, "adv_theta_r", "θr - umidade residual", "val-theta-r", out)
    ths = _num(p, "adv_theta_s", "θs - umidade de saturação", "val-theta-s", out)
    if thr is not None and ths is not None:
        if not (0.0 < thr < 1.0) or not (0.0 < ths < 1.0):
            out.append(ValidationIssue("adv_theta_r", "θr/θs", "val-theta-r",
                                       f"θr={thr:.4f} e θs={ths:.4f} (theta_r/theta_s) devem estar em (0, 1) cm³/cm³."))
        elif not thr < ths:
            out.append(ValidationIssue("adv_theta_r", "θr/θs", "val-theta-r",
                                       f"θr ({thr:.4f}) deve ser menor que θs (theta_s) ({ths:.4f}). Ajuste as propriedades físico-hídricas."))
    _num(p, "adv_alpha", "α - van Genuchten", "val-alpha", out, minimum=0.0, min_exclusive=True)
    _num(p, "adv_n", "n - índice de van Genuchten", "val-n", out, minimum=1.05, min_exclusive=True)
    _num(p, "adv_ks", "Ks - condutividade saturada", "val-ks", out, minimum=0.0, min_exclusive=True)
    _num(p, "adv_bulk_density", "ρb - densidade aparente", "val-bulk-density", out,
         minimum=0.0, min_exclusive=True, maximum=3.0)
    if "sand_pct" in p or "clay_pct" in p:
        s = _num(p, "sand_pct", "% de Areia", "val-sand", out, minimum=0.0, maximum=100.0)
        c = _num(p, "clay_pct", "% de Argila", "val-clay", out, minimum=0.0, maximum=100.0)
        if s is not None and c is not None and s + c > 100.0 and bool(p.get("is_custom_soil")):
            out.append(ValidationIssue("sand_pct", "Areia/Argila", "val-sand",
                                       f"Areia ({s:.0f}%) + Argila ({c:.0f}%) (sand_pct/clay_pct) ultrapassa 100% — fisicamente impossível."))
    if "soil_choice" in p and not p.get("is_custom_soil"):
        valid = p.get("_soil_labels")
        if valid is not None and str(p.get("soil_choice")) not in valid:
            out.append(ValidationIssue("soil_choice", "Tipo de Solo", "val-soil-choice",
                                       f"Solo (soil_choice) '{p.get('soil_choice')}' desconhecido. Escolha um solo da lista ou marque 'Solo Personalizado'."))


def validate_domain_transport(p: Dict[str, Any], out: List[ValidationIssue]) -> Optional[float]:
    domain = _num(p, "domain_depth_cm", "Profundidade do perfil", "val-domain-depth", out,
                  minimum=1.0, maximum=500.0)
    _num(p, "adv_disp", "λ - dispersividade", "val-disp", out, minimum=0.0)
    if "print_days_text" in p:
        txt = p.get("print_days_text")
        if txt is None:
            pass  # ausente (API legada): marcos automaticos, sem erro
        elif not str(txt).strip():
            out.append(ValidationIssue("print_days_text", "Dias de leitura", "val-print-days",
                                       "Dias de leitura não pode ficar vazio. Informe os dias separados por vírgula (ex.: 55, 128, 237, 365)."))
        else:
            for tok in str(txt).replace(";", ",").split(","):
                tok = tok.strip()
                if not tok:
                    continue
                f = _to_float(tok)
                if f is None:
                    out.append(ValidationIssue("print_days_text", "Dias de leitura", "val-print-days",
                                               f"Dias de leitura têm token inválido: '{tok}'. Use números separados por vírgula (ex.: 55, 128, 237, 365)."))
                    break
                if f < 0:
                    out.append(ValidationIssue("print_days_text", "Dias de leitura", "val-print-days",
                                               f"Dia de leitura ({f}) não pode ser negativo."))
                    break
    if "obs_depths_text" in p:
        txt = p.get("obs_depths_text")
        if txt is not None and str(txt).strip():
            for tok in str(txt).replace(";", ",").split(","):
                tok = tok.strip()
                if not tok:
                    continue
                f = _to_float(tok)
                if f is None:
                    out.append(ValidationIssue("obs_depths_text", "Nós de observação", "val-obs-depths",
                                               f"Nó de observação inválido: '{tok}'. Use profundidades em cm (ex.: 10,20,30,50)."))
                    break
                if f <= 0 or (domain is not None and f > domain):
                    lim = f" em (0, {domain:.0f} cm]" if domain else " positivo"
                    out.append(ValidationIssue("obs_depths_text", "Nós de observação", "val-obs-depths",
                                               f"Nó de observação ({f} cm) fora do perfil{lim} — fisicamente impossível."))
                    break
    return domain


def validate_crop(p: Dict[str, Any], out: List[ValidationIssue]) -> None:
    if not any(k in p for k in ("crop_mode", "crop_name", "crop_root_depth", "crop_kc",
                                "crop_h1", "crop_h2", "crop_h3", "crop_h4")):
        return
    has_crop = "Com cultura" in str(p.get("crop_mode", ""))
    if "crop_name" in p and has_crop and not str(p.get("crop_name") or "").strip():
        out.append(ValidationIssue("crop_name", "Cultura agrícola", "val-crop-name",
                                   "Cultura (crop_name) vazia com 'Com cultura agrícola' marcado. Informe o nome ou volte para 'Sem cultura'."))
    _num(p, "crop_root_depth", "Profundidade radicular", "val-root-depth", out, minimum=0.0, min_exclusive=True)
    _num(p, "crop_kc", "Coeficiente de cultura (Kc)", "val-kc", out, minimum=0.0, min_exclusive=True)
    h: Dict[str, Optional[float]] = {}
    for key, lab, eid in (("crop_h1", "h1 - anaerobiose", "val-h1"), ("crop_h2", "h2 - aeração ótima", "val-h2"),
                          ("crop_h3", "h3 - estresse hídrico", "val-h3"), ("crop_h4", "h4 - murcha", "val-h4")):
        v = _num(p, key, lab, eid, out, maximum=0.0, max_exclusive=True)
        h[key] = v
    if all(v is not None for v in h.values()):
        vals = [h["crop_h1"], h["crop_h2"], h["crop_h3"], h["crop_h4"]]
        if not (vals[0] > vals[1] > vals[2] > vals[3]):
            out.append(ValidationIssue("crop_h1", "Limiares de Feddes", "val-h1",
                                       f"Limiares de Feddes (crop_h1..h4) fora de ordem: {vals[0]} > {vals[1]} > {vals[2]} > {vals[3]} é exigido (ex.: -10 > -25 > -450 > -8000 cm)."))


def validate_fert(p: Dict[str, Any], out: List[ValidationIssue]) -> None:
    if "gross_dose" in p:
        _num(p, "gross_dose", "Dose bruta comercial", "val-gross-dose", out, minimum=0.0)
        try:
            _gd = float(p.get("gross_dose") or 0.0)
            if _gd > 10000:
                out.append(ValidationIssue("gross_dose", "Dose bruta comercial", "val-gross-dose",
                                           f"Dose bruta ({_gd:.0f}) acima de 10000: provável erro de digitação."))
        except (TypeError, ValueError):
            pass


def _validate_row(out: List[ValidationIssue], sym: str, label: str, active: bool,
                  dose: Any, kd: Any, disp: Any, res: Any, tag: str) -> Optional[dict]:
    """Valida uma linha ativa da tabela. Retorna o dict do soluto ou None."""
    if not active:
        return None
    d = _to_float(dose)
    if d is None and _blank(dose):
        d = 0.0
    if d is None:
        out.append(ValidationIssue(f"dose_{tag}", f"Dose de {label}", f"val-dose-{tag}",
                                   f"Dose de {sym} deve ser numérica."))
        return None
    if d < 0:
        out.append(ValidationIssue(f"dose_{tag}", f"Dose de {label}", f"val-dose-{tag}",
                                   f"Dose de {sym} ({d:.1f} kg/ha) não pode ser negativa."))
        return None
    if d > 10000:
        out.append(ValidationIssue(f"dose_{tag}", f"Dose de {label}", f"val-dose-{tag}",
                                   f"Dose de {sym} ({d:.0f} kg/ha) acima de 10000 kg/ha elementar: provável erro de digitação (adubo bruto vs elemento puro)."))
        return None
    if d == 0:
        out.append(ValidationIssue(f"dose_{tag}", f"Dose de {label}", f"val-dose-{tag}",
                                   f"{sym} marcado com dose 0 kg/ha. Informe a dose aplicada ou desmarque o soluto."))
        return None
    k = _to_float(kd)
    if k is None:
        if _blank(kd):
            k = None  # UI usa o Kd de literatura do solo (fallback preservado)
        else:
            out.append(ValidationIssue(f"kd_{tag}", f"Kd de {label}", f"val-kd-{tag}",
                                       f"Kd de {sym} deve ser numérico."))
            return None
    if k is not None and k < 0:
        out.append(ValidationIssue(f"kd_{tag}", f"Kd de {label}", f"val-kd-{tag}",
                                   f"Kd de {sym} ({k}) não pode ser negativo."))
        return None
    lmb = _to_float(disp)
    if lmb is None and not _blank(disp):
        out.append(ValidationIssue(f"disp_{tag}", f"Dispersividade de {label}", f"val-disp-{tag}",
                                   f"Dispersividade λ de {sym} deve ser numérica."))
        return None
    if lmb is not None and lmb < 0:
        out.append(ValidationIssue(f"disp_{tag}", f"Dispersividade de {label}", f"val-disp-{tag}",
                                   f"Dispersividade λ de {sym} ({lmb}) não pode ser negativa."))
        return None
    r = _to_float(res)
    if r is None and not _blank(res):
        out.append(ValidationIssue(f"res_{tag}", f"Residual de {label}", f"val-res-{tag}",
                                   f"Residual de {sym} deve ser numérico."))
        return None
    if r is not None and r < 0:
        out.append(ValidationIssue(f"res_{tag}", f"Residual de {label}", f"val-res-{tag}",
                                   f"Residual de {sym} ({r}) não pode ser negativo."))
        return None
    return {"symbol": sym, "dose_kg_ha": d, "kd": k,
            "initial_residual_mg_dm3": float(r or 0.0),
            "dispersivity_cm": lmb}


def validate_nutrients(p: Dict[str, Any], out: List[ValidationIssue]) -> List[dict]:
    """Valida as 6 linhas NPK + 3 'Outro soluto'. So linhas ATIVAS sao checadas."""
    have = any(k in p for k in ("multi_n_active", "multi_k_active", "multi_p_active",
                               "multi_s_active", "multi_ca_active", "multi_mg_active",
                               "multi_x_active", "multi_x2_active", "multi_x3_active",
                               "simulation_mode"))
    if not have:
        return []
    solutes: List[dict] = []
    for sym in NUTRIENT_SYMBOLS:
        low = sym.lower()
        if f"multi_{low}_active" not in p and f"multi_{low}_dose" not in p:
            continue
        row = _validate_row(out, sym, sym, bool(p.get(f"multi_{low}_active")),
                            p.get(f"multi_{low}_dose"), p.get(f"multi_{low}_kd"),
                            p.get(f"multi_{low}_disp"), p.get(f"multi_{low}_res"), sym)
        if row:
            solutes.append(row)
    for prefix, row_label, tag in CUSTOM_ROWS:
        if f"{prefix}_active" not in p and f"{prefix}_dose" not in p:
            continue
        if not bool(p.get(f"{prefix}_active")):
            continue
        name = str(p.get(f"{prefix}_name") or "").strip()
        if not name:
            out.append(ValidationIssue(
                f"{prefix}_name", row_label, f"val-name-{tag}",
                f"{row_label} ativa sem nome/símbolo. Informe o nome da espécie (ex.: Br-) ou desmarque a linha."))
            continue
        row = _validate_row(out, name, row_label, True, p.get(f"{prefix}_dose"),
                            p.get(f"{prefix}_kd"), p.get(f"{prefix}_disp"),
                            p.get(f"{prefix}_res"), tag)
        if row:
            solutes.append(row)
    if "simulation_mode" in p and str(p.get("simulation_mode")) == "Água + nutrientes":
        custom_on = bool(p.get("c_solute_on") or p.get("custom_solute_active") or p.get("custom_solute_on"))
        if not solutes and not custom_on:
            # Suprime ruído cascata: se a única causa for linha rejeitada (dose/residual/kd), não duplica com modo
            _has_dose_issue = any(getattr(i, "field", "").startswith("dose_") or getattr(i, "field", "").startswith("res_") or getattr(i, "field", "").startswith("kd_") for i in out)
            if not _has_dose_issue:
                out.append(ValidationIssue("simulation_mode", "Modo de simulação", "val-simulation-mode",
                                           "Modo 'Água + nutrientes' exige ao menos um soluto com dose > 0. Marque um nutriente ou troque para 'Somente água'."))
    return solutes


def validate_release_placement(p: Dict[str, Any], out: List[ValidationIssue]) -> None:
    if "release_days" in p and "Controlada" in str(p.get("release_type", "")):
        _num(p, "release_days", "Duração da liberação", "val-release-days", out, minimum=0.0, min_exclusive=True)
    mode = str(p.get("placement_mode", ""))
    if "Personalizada" in mode and ("z_app_top_cm" in p or "z_app_bottom_cm" in p):
        top = _num(p, "z_app_top_cm", "De (profundidade inicial)", "val-z-top", out, minimum=0.0)
        bot = _num(p, "z_app_bottom_cm", "Até (profundidade final)", "val-z-bottom", out)
        if top is not None and bot is not None and not bot > top:
            out.append(ValidationIssue("z_app_bottom_cm", "Posicionamento", "val-z-bottom",
                                       f"Até ({bot} cm) deve ser maior que De ({top} cm) (z_app_bottom_cm > z_app_top_cm)."))
    if "Fertirrigação" in mode and ("fert_c0_mg_l" in p or "fert_pulse_days" in p):
        _num(p, "fert_c0_mg_l", "Concentração C₀", "val-fert-c0", out, minimum=0.0, min_exclusive=True)
        if bool(p.get("fert_continuous")):
            return
        _num(p, "fert_pulse_days", "Duração da injeção", "val-fert-pulse", out, minimum=0.0)


def validate_water(p: Dict[str, Any], out: List[ValidationIssue]) -> None:
    _num(p, "rain_mm", "Lâmina de chuva/irrigação", "val-rain", out, minimum=0.0)
    _num(p, "initial_moisture_pct", "Umidade prévia do solo", "val-moisture", out, minimum=0.0)
    _num(p, "total_days", "Duração do ensaio", "val-total-days", out, minimum=0.0, min_exclusive=True)
    _num(p, "et0_mm_day", "ET0", "val-et0", out, minimum=0.0)
    _num(p, "evap_mm_day", "Evaporação do solo", "val-evap", out, minimum=0.0)
    _num(p, "transp_mm_day", "Transpiração", "val-transp", out, minimum=0.0)
    if "water_source" in p and not _blank(p.get("water_source")):
        _ws = str(p.get("water_source") or "")
        _allowed = ("Série climática", "Upload de série diária", "Lâmina de chuva/irrigação",
                    "Lâmina", "evento único", "Upload", "Série")
        if not any(a in _ws for a in _allowed):
            out.append(ValidationIssue("water_source", "Regime hídrico", "-",
                                       f"Regime hídrico '{_ws}' inválido. Escolha Série climática, Upload de série diária ou Lâmina de chuva/irrigação."))
    for key, eid in (("app_day", "val-app-day"), ("app_day_upload", "val-app-day-upload")):
        if key not in p:
            continue
        v = p.get(key)
        if _blank(v):
            continue
        f = _to_float(v)
        if f is None:
            out.append(ValidationIssue(key, "Dia da aplicação", eid,
                                       f"Dia da aplicação deve ser numérico."))
        elif f != 0 and not (1 <= f <= 365):
            out.append(ValidationIssue(key, "Dia da aplicação", eid,
                                       f"Dia da aplicação = {f:.0f} fora de [1, 365] — fisicamente impossível no calendário anual."))


def validate_analysis_window(p: Dict[str, Any], out: List[ValidationIssue]) -> None:
    """Janela de análise (série/upload) x dias de leitura x dia da aplicação.

    - Lâmina/evento: dias de leitura em [1, duração]; janela ignorada.
    - Série/upload: janela [sw, ew] em [1, 365] com sw<=ew; dias de leitura e
      dia da aplicação (app_day ou app_day_upload) dentro da janela.
    Chaves ausentes = contexto parcial (gates de etapa): sem checagem.
    """
    ws = str(p.get("water_source", ""))
    is_lamina = ("Lâmina" in ws) or ("evento único" in ws)
    if is_lamina:
        if "total_days" in p and "print_days_text" in p:
            try:
                td = float(p.get("total_days") or 0.0)
            except (TypeError, ValueError):
                return
            if td > 0:
                txt = p.get("print_days_text")
                if txt is not None and str(txt).strip():
                    bad = [f for f in _day_list(txt)
                           if f is not None and not (1 <= f <= td)]
                    if bad:
                        out.append(ValidationIssue(
                            "print_days_text", "Dias de leitura", "val-print-days",
                            f"Dia de leitura {int(bad[0])} além da duração do ensaio ({td:.0f} dias). "
                            "Use dias entre 1 e a duração."))
        return
    # Série/upload: só checa se há contexto suficiente.
    if not any(k in p for k in ("analysis_start_day", "analysis_end_day")):
        return
    sw = _to_float(p.get("analysis_start_day", 1)) if "analysis_start_day" in p else 1.0
    ew = _to_float(p.get("analysis_end_day", 365)) if "analysis_end_day" in p else 365.0
    if sw is None or ew is None:
        return  # formato já barrado pelo _num abaixo
    _num(p, "analysis_start_day", "Início da janela", "val-analysis-start",
         out, minimum=1.0, maximum=365.0)
    _num(p, "analysis_end_day", "Fim da janela", "val-analysis-end",
         out, minimum=1.0, maximum=365.0)
    if not (1 <= sw <= 365 and 1 <= ew <= 365):
        return
    if sw > ew:
        out.append(ValidationIssue(
            "analysis_end_day", "Janela de análise", "val-analysis-end",
            f"Início da janela ({sw:.0f}) maior que o fim ({ew:.0f}). Inverta os valores."))
        return
    if "print_days_text" in p:
        txt = p.get("print_days_text")
        if txt is not None and str(txt).strip():
            bad = [f for f in _day_list(txt)
                   if f is not None and not (sw <= f <= ew)]
            if bad:
                out.append(ValidationIssue(
                    "print_days_text", "Dias de leitura", "val-print-days",
                    f"Dia de leitura {int(bad[0])} fora da janela de análise "
                    f"({sw:.0f}–{ew:.0f}). Use dias dentro da janela."))
    app_key = "app_day_upload" if "Upload" in ws and "app_day_upload" in p else "app_day"
    app_eid = "val-app-day-upload" if app_key == "app_day_upload" else "val-app-day"
    if app_key in p and p.get(app_key) not in (None, ""):
        af = _to_float(p.get(app_key))
        if af is not None and af != 0 and not (sw <= af <= ew):
            out.append(ValidationIssue(
                app_key, "Dia da aplicação", app_eid,
                f"Dia da aplicação ({af:.0f}) fora da janela de análise "
                f"({sw:.0f}–{ew:.0f}). A adubação precisa cair dentro do período simulado."))
            return
        # Coerência leitura x aplicação: ao menos um snapshot precisa cair DEPOIS
        # da adubação, senão a evolução do fertilizante nunca é registrada.
        if "print_days_text" in p and app_key in p:
            txt = p.get("print_days_text")
            af2 = _to_float(p.get(app_key))
            if (txt is not None and str(txt).strip() and af2 is not None and af2 != 0
                    and sw <= af2 <= ew):
                valid_days = sorted(f for f in _day_list(txt)
                                    if f is not None and sw <= f <= ew)
                if valid_days and max(valid_days) <= af2:
                    out.append(ValidationIssue(
                        "print_days_text", "Dias de leitura", "val-print-days",
                        f"Todas as leituras ({', '.join(str(int(d)) for d in valid_days)}) "
                        f"são anteriores ou iguais ao dia da aplicação ({af2:.0f}). "
                        f"Inclua ao menos um dia de leitura após a adubação para "
                        f"registrar a evolução do fertilizante."))


def _day_list(txt: Any) -> list:
    """Tokens numéricos de lista '55, 128, 237' (None p/ token inválido)."""
    vals = []
    for tok in str(txt).replace(";", ",").split(","):
        tok = tok.strip()
        if tok:
            vals.append(_to_float(tok))
    return vals


def validate_modes(p: Dict[str, Any], out: List[ValidationIssue]) -> None:
    if "simulation_mode" in p and str(p.get("simulation_mode")) not in SIM_MODES:
        out.append(ValidationIssue("simulation_mode", "Modo de simulação", "val-simulation-mode",
                                   f"Modo de simulação '{p.get('simulation_mode')}' inválido. Escolha 'Água + nutrientes' ou 'Somente água'."))


def validate_payload(p: Dict[str, Any], soil_labels=None) -> List[ValidationIssue]:
    """Valida o payload completo; retorna TODAS as issues (ordem de checagem)."""
    out: List[ValidationIssue] = []
    if soil_labels is not None:
        p = dict(p)
        p["_soil_labels"] = set(soil_labels)
    validate_soil(p, out)
    validate_domain_transport(p, out)
    validate_crop(p, out)
    validate_fert(p, out)
    validate_nutrients(p, out)
    validate_release_placement(p, out)
    validate_water(p, out)
    validate_analysis_window(p, out)
    validate_modes(p, out)
    return out


def validate_legacy_subset(adv_theta_r: Any, adv_theta_s: Any, adv_alpha: Any, adv_n: Any,
                           adv_ks: Any, adv_disp: Any, nutrients_list: Optional[list],
                           simulation_mode: str, custom_solute_on: bool = False) -> List[ValidationIssue]:
    """Subconjunto da Moldura antiga (validate_simulation_inputs): solo + dispersao +
    lista de solutos pronta + modo. Preserva ordem e mensagens legadas."""
    p: Dict[str, Any] = {
        "adv_theta_r": adv_theta_r, "adv_theta_s": adv_theta_s, "adv_alpha": adv_alpha,
        "adv_n": adv_n, "adv_ks": adv_ks, "adv_disp": adv_disp,
        "simulation_mode": simulation_mode,
        "custom_solute_active": bool(custom_solute_on),
    }
    for n in (nutrients_list or []):
        sym = str(n.get("symbol", "?"))
        if sym in NUTRIENT_SYMBOLS:
            tag = sym
            p[f"multi_{tag.lower()}_active"] = True
            p[f"multi_{tag.lower()}_dose"] = n.get("dose_kg_ha", 0.0)
            p[f"multi_{tag.lower()}_kd"] = n.get("kd", 0.0)
            p[f"multi_{tag.lower()}_disp"] = n.get("dispersivity_cm")
            p[f"multi_{tag.lower()}_res"] = n.get("initial_residual_mg_dm3", 0.0)
        else:
            # F6: soluto custom precisa do nome na linha X/X2/X3 correspondente;
            # sem ele, validate_nutrients bloquearia como "X sem nome".
            for _slot in ("x", "x2", "x3"):
                if not p.get(f"multi_{_slot}_active"):
                    p[f"multi_{_slot}_active"] = True
                    p[f"multi_{_slot}_name"] = sym
                    p[f"multi_{_slot}_dose"] = n.get("dose_kg_ha", 0.0)
                    p[f"multi_{_slot}_kd"] = n.get("kd", 0.0)
                    p[f"multi_{_slot}_disp"] = n.get("dispersivity_cm")
                    p[f"multi_{_slot}_res"] = n.get("initial_residual_mg_dm3", 0.0)
                    break
    out: List[ValidationIssue] = []
    validate_soil({k: p[k] for k in ("adv_theta_r", "adv_theta_s", "adv_alpha", "adv_n", "adv_ks") if k in p}, out)
    if "adv_disp" in p:
        _num(p, "adv_disp", "λ - dispersividade", "val-disp", out, minimum=0.0)
    solutes = validate_nutrients(p, out)
    _ = solutes
    return out


# ---------------------------------------------------------------------------
# HTML do modal de erro (overlay pattern) — data-target alimenta a borda via JS
# ---------------------------------------------------------------------------
def render_issues_html(issues: List[ValidationIssue]) -> str:
    items = []
    for i, iss in enumerate(issues, 1):
        target = iss.elem_id or ""
        items.append(
            f'<div class="validation-issue" data-target="{target}">'
            f'<span class="validation-issue-num">{i}</span>'
            f'<div class="validation-issue-body"><b>{_esc(iss.label)}</b>'
            f'<p>{_esc(iss.message)}</p></div></div>'
        )
    return (
        '<div class="validation-modal-head">'
        '<div class="validation-modal-icon">⚠</div>'
        '<div><h3 class="validation-modal-title">Verifique os campos destacados</h3>'
        f'<p class="validation-modal-sub">{len(issues)} campo(s) com formato inválido ou valor fisicamente impossível.</p></div></div>'
        f'<div class="validation-issue-list">{"".join(items)}</div>'
    )


def _esc(s: Any) -> str:
    t = str(s)
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
