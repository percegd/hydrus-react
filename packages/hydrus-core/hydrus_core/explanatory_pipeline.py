"""
Módulo Explicativo e Auditoria Passo a Passo Dinâmica do Hydrus (perfil de solo).
Gera a memória de cálculo completa e transparente da simulação EXECUTADA PELO USUÁRIO,
substituindo numericamente cada entrada na física matemática correspondente:
1. Dados e Parâmetros Configurados pelo Usuário
2. Rastreabilidade das Escolhas do Usuário: O que cada campo definiu e fontes científicas
3. Etapa 1: Carga Inicial e Estequiometria do Adubo
4. Etapa 2: Parametrização da Água no Solo (van Genuchten) e Capacidade de Campo
5. Etapa 3: Fluxo da Chuva e Velocidade nos Poros (Richards 1D)
6. Etapa 4: Adsorção Coloidal e Fator de Retardamento (R com Kd)
7. Etapa 5: Transporte de Solutos e Deslocamento do Pico (ADE)
8. Etapa 6: Balanço de Massa e Integração na Camada Avaliada
9. Resumo Numérico Final da Simulação
10. Conclusão Técnica e Parecer Agronômico
"""

from typing import Dict, Any, Optional, Tuple
import os
import base64
import markdown

# Armazena a última simulação executada para servir na rota /resultado e /passo-a-passo
_LATEST_SIM_PARAMS: Optional[Dict[str, Any]] = None
_LATEST_SIM_RESULT: Dict[str, Any] = {
    "params": None,
    "img_base64": "",
    "report_markdown": "",
    "report_html": "",
    "zip_path": "",
    "excel_path": "",
}

def get_default_sim_params() -> Dict[str, Any]:
    """Retorna os parâmetros padrão iniciais (baseados na tela de entrada padrão)."""
    return {
        "sim_type": "field",
        "mode_label": "Simulação e Diagnóstico de Campo",
        "nutrient_label": "Potássio (K+)",
        "nutrient_symbol": "K",
        "fertilizer_label": "Polialita (11.6% K, 19.2% S, 12.2% Ca, 3.6% Mg)",
        "fertilizer_name": "Polialita Comercial",
        "gross_dose": 360.0,
        "elemental_dose": 41.76,
        "soil_name": "Latossolo Vermelho Textura Média",
        "soil_citation": "Parâmetro definido por: Solo selecionado = 'Latossolo Vermelho Textura Média'. Para o Latossolo Vermelho de Textura Média (Franco-Argilo-Arenoso), os parâmetros físico-hídricos de van Genuchten calibrados são: θr = 0.065 cm³/cm³, θs = 0.410 cm³/cm³, α = 0.0250 cm⁻¹, n = 1.4500, Ks = 45.0 cm/dia, ρb = 1.35 g/cm³. Curva de retenção representativa de solos agrícolas do Planalto Central. Fonte Científica: Embrapa Solos (Boletim de Solos Tropicais Brasileiros); Funções de Pedotransferência de Tomasella et al. (2000) e USDA Rosetta (Schaap et al., 2001).",
        "theta_r": 0.065,
        "theta_s": 0.410,
        "alpha": 0.0250,
        "n": 1.4500,
        "ks": 45.0,
        "bulk_density": 1.35,
        "kd": 0.4500,
        "kd_citation": "Parâmetros definidos por: Nutriente = 'Potássio (K+)' interagindo com o Solo = 'Latossolo Vermelho Textura Média' (textura: medio). Kd adotado = 0.4500 cm³/g. O potássio (K⁺) é um cátion monovalente adsorvido eletrostaticamente na CTC das argilas e matéria orgânica do solo Latossolo Vermelho Textura Média, produzindo Fator de Retardo R ≈ 2.3 frente à velocidade da água livre. Fonte Científica: Raij (2011) - Fertilidade do Solo e Adubação; Sparks (1987) - Potassium Dynamics in Soils; Ernani et al. (2007) - Química do Solo e Disponibilidade de Nutrientes.",
        "dispersivity": 5.0,
        "crop_name": "Milho - Vegetativo Inicial (V3/V4, raiz 25 cm)",
        "crop_citation": "Parâmetro definido por: Cultura selecionada = 'Milho - Vegetativo Inicial (V3/V4, raiz 25 cm)'. Para a cultura do Milho no Estágio Vegetativo Inicial (V3/V4), a profundidade radicular é calibrada em 25 cm com Kc = 0.40. Os potenciais de estresse hídrico de Feddes são: P0 = -10 cm (anaerobiose), P2H = -25 cm (aeração ótima), P3 = -400 cm (início de estresse hídrico para milho jovem), P4 = -8000 cm (ponto de murcha permanente). Fonte Científica: FAO Irrigation and Drainage Paper 56 (Allen et al., 1998) - Tabela 12; Fancelli & Dourado Neto (2000) - Ecofisiologia e Manejo da Cultura do Milho; Feddes et al. (1978).",
        "h1": -10.0,
        "h2": -25.0,
        "h3": -400.0,
        "h4": -8000.0,
        "root_depth_cm": 25.0,
        "rain_mm": 100.0,
        "total_days": 7.0,
        "initial_moisture_pct": 18.0,
        "leaching_pct": 14.8,
        "retained_pct": 85.2,
        "peak_depth_cm": 15.5,
        "q_bottom_cm": 0.0,
        "dose_note": "Dose bruta de 360 kg/ha de Polialita contém 41.8 kg/ha de K líquido (11.6% de teor)."
    }

def set_latest_simulation_result(
    params: Dict[str, Any],
    img_path: Optional[str] = None,
    report_markdown: Optional[str] = None,
    zip_path: Optional[str] = None,
    excel_path: Optional[str] = None
) -> None:
    """Atualiza o resultado completo da simulação mais recente para a tela unificada."""
    global _LATEST_SIM_PARAMS, _LATEST_SIM_RESULT
    _LATEST_SIM_PARAMS = params

    img_b64 = ""
    if img_path and os.path.exists(img_path):
        try:
            with open(img_path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode("utf-8")
        except Exception:
            img_b64 = ""

    rep_html = ""
    if report_markdown:
        try:
            rep_html = markdown.markdown(report_markdown, extensions=['extra', 'nl2br'])
        except Exception:
            rep_html = f"<pre>{report_markdown}</pre>"

    _LATEST_SIM_RESULT = {
        "params": params,
        "img_base64": img_b64,
        "report_markdown": report_markdown or "",
        "report_html": rep_html,
        "zip_path": zip_path or "",
        "excel_path": excel_path or "",
    }

def get_latest_zip_path() -> Optional[str]:
    """Retorna o caminho do zip da simulação mais recente."""
    global _LATEST_SIM_RESULT
    return _LATEST_SIM_RESULT.get("zip_path") if _LATEST_SIM_RESULT else None

def get_latest_excel_path() -> Optional[str]:
    """Retorna o caminho do arquivo Excel da simulação mais recente."""
    global _LATEST_SIM_RESULT
    return _LATEST_SIM_RESULT.get("excel_path") if _LATEST_SIM_RESULT else None

def set_latest_simulation_data(params: Dict[str, Any]) -> None:
    """Atualiza os parâmetros da simulação mais recente (retrocompatibilidade)."""
    set_latest_simulation_result(params)

def _generate_water_only_step_by_step(p: Dict[str, Any]) -> Tuple[str, str]:
    """Passo a passo (MD e HTML) para o modo "Somente água": apenas a física hídrica.

    Resolve a curva de retenção (van Genuchten), a equação de Richards 1D com absorção
    radicular (Feddes), a velocidade de Darcy nos poros e o balanço hídrico do perfil.
    Não há etapas de adsorção (Kd), transporte advectivo-dispersivo nem balanço de massa
    de soluto.
    """
    soil_name = str(p.get("soil_name", "Solo Selecionado"))
    soil_cit = str(p.get("soil_citation", "Parâmetros físico-hídricos calibrados do solo selecionado."))
    theta_r = float(p.get("theta_r", 0.025))
    theta_s = float(p.get("theta_s", 0.423))
    alpha = float(p.get("alpha", 0.0343))
    n = float(p.get("n", 1.4634))
    m = 1.0 - (1.0 / n) if n > 1.0 else 0.3
    ks = float(p.get("ks", 65.0))
    rho_b = float(p.get("bulk_density", 1.30))

    rain_mm = float(p.get("rain_mm", 0.0))
    total_days = float(p.get("total_days", 1.0))
    profile_depth = float(p.get("profile_depth_cm", p.get("root_depth_cm", 100.0)))
    storage_mm = float(p.get("storage_mm", 0.0) or 0.0)
    runoff_mm = float(p.get("runoff_mm", 0.0) or 0.0)
    _drain = p.get("drainage_mm")
    drainage_mm = float(_drain) if _drain is not None else float(p.get("q_bottom_cm", 0.0)) * 10.0
    et0_mm_day = float(p.get("et0_mm_day", 0.0) or 0.0)
    evap_mm_day = float(p.get("evap_mm_day", 0.0) or 0.0)
    transp_mm_day = float(p.get("transp_mm_day", 0.0) or 0.0)

    crop_name = str(p.get("crop_name", "Perfil de solo nu (sem cultura)")).split(" (")[0]
    crop_cit = str(p.get("crop_citation", "Sem cultura: apenas evaporação do solo."))
    _cn_l = str(p.get("crop_name", "")).lower()
    has_crop = not ("sem cultura" in _cn_l or "solo nu" in _cn_l or "sem cultura" in str(crop_cit).lower())
    root_depth = float(p.get("root_depth_cm", profile_depth))
    h1 = float(p.get("h1", -10.0))
    h2 = float(p.get("h2", -25.0))
    h3 = float(p.get("h3", -400.0))
    h4 = float(p.get("h4", -8000.0))
    if has_crop:
        s_water_md = (
            f"O termo de consumo radicular $S(h, z) = \\alpha(h) \\cdot b(z) \\cdot T_p$ usa os potenciais de Feddes "
            f"($P_0 = {h1:.0f}$, $P_{{2H}} = {h2:.0f}$, $P_3 = {h3:.0f}$, $P_4 = {h4:.0f}\\text{{ cm}}$)."
        )
        s_water_p = (
            f"<p>Consumo radicular $S(h,z)$ via Feddes ($P_0 = {h1:.0f}$, $P_{{2H}} = {h2:.0f}$, "
            f"$P_3 = {h3:.0f}$, $P_4 = {h4:.0f}$ cm).</p>"
        )
    else:
        s_water_md = "Sem cultura: $S(h, z) = 0$ (apenas evaporação do solo, sem absorção radicular)."
        s_water_p = "<p>Sem cultura: $S(h, z) = 0$ (apenas evaporação do solo).</p>"

    # Intermediários físicos
    h_cc = 100.0
    alpha_h = alpha * h_cc
    denom_vg = (1.0 + alpha_h ** n) ** m
    theta_cc = theta_r + (theta_s - theta_r) / denom_vg
    q_avg = (rain_mm / 10.0) / max(total_days, 1.0)
    theta_active = max(theta_r + 0.05, min(theta_s - 0.02, theta_cc * 0.90))
    v_pore = q_avg / theta_active if theta_active > 0 else 0.0
    # Fechamento do balanço: ET efetiva = Entrada − Escoamento − Drenagem − Δ Armazenamento
    et_balance_mm = rain_mm - runoff_mm - drainage_mm - storage_mm

    global _LATEST_SIM_RESULT
    img_b64 = _LATEST_SIM_RESULT.get("img_base64", "") if _LATEST_SIM_RESULT else ""
    report_html = _LATEST_SIM_RESULT.get("report_html", "") if _LATEST_SIM_RESULT else ""

    graph_section = ""
    if img_b64:
        graph_section = f"""
        <div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;padding:22px;margin-bottom:22px;box-shadow:0 1px 4px rgba(0,0,0,0.04);">
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;flex-wrap:wrap;gap:10px;">
                <h3 style="font-size:17px;color:#0f172a;font-weight:700;margin:0;">1. Perfil de Umidade do Solo θ(z)</h3>
                <a href="/download-perfil-excel" target="_blank" style="display:inline-flex;align-items:center;gap:7px;background:#059669;color:#ffffff;text-decoration:none;padding:7px 15px;border-radius:8px;font-size:13px;font-weight:600;">Baixar Dados do Perfil (.XLSX)</a>
            </div>
            <div style="background:#ffffff;border-radius:8px;padding:8px;border:1px solid #e2e8f0;text-align:center;">
                <img src="data:image/png;base64,{img_b64}" alt="Perfil de Umidade do Solo" style="max-width:100%;height:auto;border-radius:6px;display:block;margin:0 auto;" />
            </div>
        </div>
        """

    report_section = ""
    if report_html:
        report_section = f"""
        <div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;padding:22px;margin-bottom:22px;line-height:1.8;box-shadow:0 1px 4px rgba(0,0,0,0.04);">
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;border-bottom:1px solid #e2e8f0;padding-bottom:10px;">
                <h3 style="font-size:17px;color:#0f172a;font-weight:700;margin:0;">2. Laudo Técnico — Balanço Hídrico</h3>
                <span style="font-size:11.5px;font-weight:600;padding:3px 8px;border-radius:6px;background:#ecfdf5;color:#065f46;border:1px solid #a7f3d0;">Fluxo de Água</span>
            </div>
            <div style="color:#1e293b;font-size:14px;">{report_html}</div>
        </div>
        """

    ctx = {
        "graph_section": graph_section,
        "report_section": report_section,
        "soil_name": soil_name,
        "soil_cit": soil_cit,
        "theta_r": f"{theta_r:.4f}",
        "theta_s": f"{theta_s:.4f}",
        "theta_diff": f"{(theta_s - theta_r):.4f}",
        "alpha": f"{alpha:.4f}",
        "n": f"{n:.4f}",
        "m": f"{m:.4f}",
        "ks": f"{ks:.1f}",
        "rho_b": f"{rho_b:.2f}",
        "rain_mm": f"{rain_mm:.1f}",
        "total_days": f"{total_days:.0f}",
        "profile_depth": f"{profile_depth:.0f}",
        "root_depth": f"{root_depth:.0f}",
        "h1": f"{h1:.0f}", "h2": f"{h2:.0f}", "h3": f"{h3:.0f}", "h4": f"{h4:.0f}",
        "crop_name": crop_name,
        "crop_cit": crop_cit,
        "s_water_md": s_water_md,
        "s_water_p": s_water_p,
        "alpha_h": f"{alpha_h:.2f}",
        "denom_vg": f"{denom_vg:.3f}",
        "theta_cc": f"{theta_cc:.3f}",
        "theta_cc_pct": f"{(theta_cc * 100.0):.1f}",
        "q_avg": f"{q_avg:.3f}",
        "theta_active": f"{theta_active:.3f}",
        "v_pore": f"{v_pore:.3f}",
        "drainage_mm": f"{drainage_mm:.1f}",
        "runoff_mm": f"{runoff_mm:.1f}",
        "storage_mm": f"{storage_mm:+.1f}",
        "et_balance_mm": f"{et_balance_mm:.1f}",
        "et0_mm_day": f"{et0_mm_day:.2f}",
        "evap_mm_day": f"{evap_mm_day:.2f}",
        "transp_mm_day": f"{transp_mm_day:.2f}",
    }

    md_template = r"""
# Memória de Cálculo & Passo a Passo — Fluxo de Água no Solo (Somente Água)
**Resolução Numérica Passo a Passo da Simulação Executada**

Esta simulação **não transporta solutos**. Resolve apenas a **Equação de Richards 1D** acoplada à
evaporação do solo e, quando há cultura, à absorção radicular (Feddes).

---

### 1. Dados e Parâmetros Configurados nesta Simulação

| Parâmetro de Entrada | Símbolo | Valor Adotado | Unidade | Significado na Simulação |
| :--- | :---: | :---: | :---: | :--- |
| **Solo Utilizado** | - | **{{soil_name}}** | - | Matriz física do perfil |
| **Umidade Residual** | $\theta_r$ | **{{theta_r}}** | $\text{cm}^3/\text{cm}^3$ | Água fortemente retida aos sólidos |
| **Umidade de Saturação** | $\theta_s$ | **{{theta_s}}** | $\text{cm}^3/\text{cm}^3$ | Porosidade total preenchida por água |
| **Parâmetro de Escala $\alpha$** | $\alpha$ | **{{alpha}}** | $\text{cm}^{-1}$ | Inverso da sucção de borbulhamento |
| **Índice de Distribuição de Poros** | $n$ | **{{n}}** | - | $m = 1 - 1/n = {{m}}$ |
| **Condutividade Hidráulica Saturada** | $K_s$ | **{{ks}}** | cm/dia | Infiltração máxima em saturação |
| **Densidade Aparente do Solo** | $\rho_b$ | **{{rho_b}}** | $\text{g/cm}^3$ | Massa seca por volume |
| **Lâmina de Água (chuva/irrigação)** | $P$ | **{{rain_mm}}** | mm | Entrada de água no perfil |
| **Período de Simulação** | $t_{\text{total}}$ | **{{total_days}}** | dias | Tempo físico simulado |
| **Profundidade do Perfil** | $L$ | **{{profile_depth}}** | cm | Domínio vertical simulado |
| **Cultura & Sistema Radicular** | - | **{{crop_name}}** | - | {{crop_cit}} |

---

### Etapa 1: Curva de Retenção de Água (van Genuchten, 1980)
> **Parâmetro de Entrada:** Tipo de Solo = **{{soil_name}}**
> **Origem & Rastreabilidade Científica:** {{soil_cit}}

$$
\theta(h) = \theta_r + \frac{\theta_s - \theta_r}{\left[1 + |\alpha h|^n\right]^m}, \quad m = 1 - \frac{1}{{{n}}} = {{m}}
$$

Substituindo a sucção de **capacidade de campo** ($h = -100\text{ cm}$):

$$
\theta_{\text{cc}} = {{theta_r}} + \frac{{{theta_diff}}}{{{denom_vg}}} = \mathbf{{{theta_cc}}\text{ cm}^3/\text{cm}^3}
$$

*(equivalente a {{theta_cc_pct}}% de umidade volumétrica na capacidade de campo)*

---

### Etapa 2: Fluxo de Água no Solo (Richards 1D)
> **Parâmetros de Entrada:** Lâmina de Água = **{{rain_mm}} mm** ao longo de **{{total_days}} dias** e Cultura = **{{crop_name}}**

$$
\frac{\partial \theta}{\partial t} = \frac{\partial}{\partial z} \left[ K(h) \left( \frac{\partial h}{\partial z} - 1 \right) \right] - S(h, z)
$$

{{s_water_md}}

---

### Etapa 3: Velocidade da Água nos Poros (Lei de Darcy)
> **Parâmetros de Entrada:** Lâmina = **{{rain_mm}} mm** em **{{total_days}} dias**

$$
v = \frac{q}{\theta} = \frac{{{q_avg}}\text{ cm/dia}}{{{theta_active}}\text{ cm}^3/\text{cm}^3} \approx \mathbf{{{v_pore}}\text{ cm/dia}}
$$

---

### Etapa 4: Balanço Hídrico do Perfil (0 – {{profile_depth}} cm)
> **Princípio de Conservação de Massa da Água**

$$
P = RO + D + \Delta S + ET
$$

| Componente do Balanço | Valor |
| :--- | :---: |
| **Entrada — chuva/irrigação ($P$)** | **{{rain_mm}} mm** |
| **Escoamento superficial ($RO$)** | {{runoff_mm}} mm |
| **Drenagem no fundo do perfil ($D$)** | {{drainage_mm}} mm |
| **Δ Armazenamento no perfil ($\Delta S = \theta_f - \theta_i$)** | {{storage_mm}} mm |
| **Evapotranspiração efetiva ($ET = P - RO - D - \Delta S$)** | **{{et_balance_mm}} mm** |

> **Fechamento do balanço:** com os valores acima, a água que entra sai por escoamento,
> drenagem profunda, armazenamento e evapotranspiração. A demanda atmosférica adotada foi
> ET0 = {{et0_mm_day}} mm/dia (partição: E ≈ {{evap_mm_day}} mm/dia, T ≈ {{transp_mm_day}} mm/dia).
""".strip()

    html_template = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cálculo Detalhado (passo a passo) — Fluxo de Água — Hydrus</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.css">
    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.js"></script>
    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/contrib/auto-render.min.js"
        onload="renderMathInElement(document.body, {delimiters: [{left: '$$', right: '$$', display: true}, {left: '$', right: '$', display: false}, {left: '\\[', right: '\\]', display: true}, {left: '\\(', right: '\\)', display: false}]});"></script>
    <style>
        :root { --bg:#f5f4ef; --surface:#ffffff; --border:#e2e8f0; --text:#1e293b; --muted:#64748b; --accent:#059669; --accent-dark:#047857; --accent-light:#ecfdf5; }
        * { box-sizing:border-box; margin:0; padding:0; }
        body { font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; background:var(--bg); color:var(--text); line-height:1.65; padding:24px; }
        .container { max-width:1100px; margin:0 auto; }
        .app-header { background:linear-gradient(135deg,#065f46 0%,#047857 100%); border-radius:14px; padding:12px 24px; margin-bottom:20px; display:flex; align-items:center; justify-content:space-between; gap:18px; }
        .app-header-text { text-align:right; color:#ffffff; }
        .app-header-text h1 { font-size:18px; font-weight:700; margin:0 0 2px 0; }
        .app-header-text p { font-size:13px; color:#d1fae5; margin:0; }
        .header-logos { display:flex; align-items:center; gap:16px; }
        .header-logo-img { height:56px; width:auto; max-width:180px; object-fit:contain; }
        .page-banner { background:#ffffff; border:1px solid var(--border); border-radius:12px; padding:20px 24px; margin-bottom:22px; display:flex; align-items:center; justify-content:space-between; gap:16px; }
        .page-banner h2 { font-size:18px; font-weight:800; color:#0f172a; margin-bottom:4px; }
        .page-banner p { font-size:13.5px; color:var(--muted); margin:0; }
        .step-card { border:1px solid var(--border); border-radius:12px; background:#ffffff; margin-bottom:20px; overflow:hidden; }
        .step-header { background:#f8fafc; padding:12px 18px; border-bottom:1px solid var(--border); display:flex; align-items:center; justify-content:space-between; }
        .step-title { display:flex; align-items:center; gap:10px; font-weight:700; font-size:15.5px; color:#0f172a; }
        .step-num { background:var(--accent); color:#ffffff; width:26px; height:26px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:12px; font-weight:800; }
        .step-tag { font-size:11.5px; font-weight:600; padding:3px 8px; border-radius:6px; background:var(--accent-light); color:#065f46; border:1px solid #a7f3d0; }
        .step-body { padding:18px; font-size:14px; }
        .math-block { background:#f8fafc; border-radius:8px; padding:12px; margin:12px 0; text-align:center; font-size:15px; border:1px solid var(--border); color:#0f172a; overflow-x:auto; }
        .table-custom { width:100%; border-collapse:collapse; margin:14px 0; font-size:13.5px; background:#ffffff; }
        .table-custom th, .table-custom td { border:1px solid var(--border); padding:8px 12px; text-align:left; }
        .table-custom th { background:#f1f5f9; font-weight:600; color:#0f172a; }
        .info-box { background:#f0fdf4; border-left:4px solid var(--accent); padding:10px 14px; margin-bottom:14px; border-radius:4px; font-size:13.5px; border:1px solid #bbf7d0; color:#166534; }
        .nav-actions { display:flex; justify-content:space-between; margin-top:32px; padding-top:20px; border-top:1px solid var(--border); }
        .btn { display:inline-flex; align-items:center; gap:8px; padding:9px 18px; border-radius:8px; font-size:13.5px; font-weight:600; text-decoration:none; cursor:pointer; border:1px solid #cbd5e1; background:#ffffff; color:var(--text); }
        .btn-primary { background:var(--accent); color:#ffffff !important; border:1px solid var(--accent-dark); font-weight:700; }
    </style>
</head>
<body>
<div class="container">
    <div class="app-header">
        <div class="header-logos">
            <img src="/logo-ppg" alt="PPG" class="header-logo-img" />
            <img src="/logo-gpeas" alt="GPEAS" class="header-logo-img" />
        </div>
        <div class="app-header-text">
            <h1>Hydrus — Relatório Físico & Auditoria</h1>
            <p>Fluxo de Água no Perfil do Solo (Somente Água)</p>
        </div>
    </div>

    <div class="page-banner">
        <div>
            <h2>Cálculo Detalhado (passo a passo) — Fluxo de Água</h2>
            <p>Curva de retenção de van Genuchten, Equação de Richards 1D com absorção radicular e balanço hídrico do perfil.</p>
        </div>
        <button class="btn" onclick="window.print()">Imprimir / Salvar PDF</button>
    </div>

    <div class="content">
        {{graph_section}}
        {{report_section}}

        <div style="margin:28px 0 16px 0;">
            <h2 style="font-size:18px;color:#0f172a;font-weight:800;margin:0 0 4px 0;">3. Memória de Cálculo & Dedução Física Passo a Passo</h2>
            <p style="color:var(--muted);font-size:13.5px;margin:0;">Rastreabilidade das equações de van Genuchten, Richards e do balanço hídrico.</p>
        </div>

        <div class="step-card" style="padding:18px;margin-bottom:20px;">
            <h3 style="font-size:16px;margin-bottom:12px;color:#065f46;font-weight:700;">Dados e Parâmetros Configurados nesta Simulação</h3>
            <table class="table-custom">
                <tr><th>Parâmetro</th><th>Símbolo</th><th>Valor Adotado</th><th>Significado</th></tr>
                <tr><td>Solo</td><td>-</td><td><b>{{soil_name}}</b></td><td>Parâmetros físicos da matriz</td></tr>
                <tr><td>Umidades do Solo</td><td>$\theta_r, \theta_s$</td><td><b>{{theta_r}} / {{theta_s}}</b> cm³/cm³</td><td>Residual e Saturação</td></tr>
                <tr><td>Forma da Curva (VG)</td><td>$\alpha, n$</td><td><b>{{alpha}} cm⁻¹ / {{n}}</b> ($m = {{m}}$)</td><td>Borbulhamento e porosidade</td></tr>
                <tr><td>Condutividade Saturada</td><td>$K_s$</td><td><b>{{ks}} cm/dia</b></td><td>Permeabilidade máxima</td></tr>
                <tr><td>Lâmina de Água</td><td>$P$</td><td><b>{{rain_mm}} mm</b> em <b>{{total_days}} dias</b></td><td>Entrada superficial</td></tr>
                <tr><td>Profundidade do Perfil</td><td>$L$</td><td><b>{{profile_depth}} cm</b></td><td>Domínio vertical</td></tr>
                <tr><td>Cultura & Sistema Radicular</td><td>-</td><td><b>{{crop_name}}</b></td><td>{{crop_cit}}</td></tr>
            </table>
        </div>

        <div class="step-card">
            <div class="step-header"><div class="step-title"><span class="step-num">1</span><span>Curva de Retenção de Água</span></div><span class="step-tag">van Genuchten (1980)</span></div>
            <div class="step-body">
                <div class="info-box"><b>Parâmetro de Entrada:</b> Solo = <b>{{soil_name}}</b><br/><b>Origem & Rastreabilidade:</b> {{soil_cit}}</div>
                <div class="math-block">$$\theta(h) = \theta_r + \frac{\theta_s - \theta_r}{\left[1 + |\alpha h|^n\right]^m}$$</div>
                <div class="math-block">$$\theta_{\text{cc}} = {{theta_r}} + \frac{{{theta_diff}}}{{{denom_vg}}} = \mathbf{{{theta_cc}}\text{ cm}^3/\text{cm}^3}$$</div>
                <p>*(equivalente a {{theta_cc_pct}}% de umidade volumétrica na capacidade de campo)*</p>
            </div>
        </div>

        <div class="step-card">
            <div class="step-header"><div class="step-title"><span class="step-num">2</span><span>Fluxo de Água no Solo</span></div><span class="step-tag">Richards 1D</span></div>
            <div class="step-body">
                <div class="info-box"><b>Parâmetros de Entrada:</b> Lâmina = <b>{{rain_mm}} mm</b> em <b>{{total_days}} dias</b> e Cultura = <b>{{crop_name}}</b></div>
                <div class="math-block">$$\frac{\partial \theta}{\partial t} = \frac{\partial}{\partial z} \left[ K(h) \left( \frac{\partial h}{\partial z} - 1 \right) \right] - S(h, z)$$</div>
                {{s_water_p}}
            </div>
        </div>

        <div class="step-card">
            <div class="step-header"><div class="step-title"><span class="step-num">3</span><span>Velocidade da Água nos Poros</span></div><span class="step-tag">Lei de Darcy</span></div>
            <div class="step-body">
                <div class="math-block">$$v = \frac{q}{\theta} = \frac{{{q_avg}}\text{ cm/dia}}{{{theta_active}}\text{ cm}^3/\text{cm}^3} \approx \mathbf{{{v_pore}}\text{ cm/dia}}$$</div>
            </div>
        </div>

        <div class="step-card">
            <div class="step-header"><div class="step-title"><span class="step-num">4</span><span>Balanço Hídrico do Perfil</span></div><span class="step-tag">Conservação de Massa</span></div>
            <div class="step-body">
                <div class="math-block">$$P = RO + D + \Delta S + ET$$</div>
                <table class="table-custom">
                    <tr><th>Componente do Balanço</th><th>Valor</th></tr>
                    <tr><td>Entrada — chuva/irrigação ($P$)</td><td><b>{{rain_mm}} mm</b></td></tr>
                    <tr><td>Escoamento superficial ($RO$)</td><td>{{runoff_mm}} mm</td></tr>
                    <tr><td>Drenagem no fundo ($D$)</td><td>{{drainage_mm}} mm</td></tr>
                    <tr><td>Δ Armazenamento ($\Delta S = \theta_f - \theta_i$)</td><td>{{storage_mm}} mm</td></tr>
                    <tr><td>Evapotranspiração efetiva ($ET = P - RO - D - \Delta S$)</td><td><b>{{et_balance_mm}} mm</b></td></tr>
                </table>
                <p>Demanda atmosférica adotada: ET0 = {{et0_mm_day}} mm/dia (partição: E ≈ {{evap_mm_day}}, T ≈ {{transp_mm_day}} mm/dia).</p>
            </div>
        </div>

        <div class="nav-actions">
            <button class="btn" onclick="window.print()">Imprimir / Salvar em PDF</button>
            <button class="btn btn-primary" onclick="window.close();">Voltar para o Simulador</button>
        </div>
    </div>
</div>
</body>
</html>
"""

    md_content = md_template
    html_content = html_template
    for k, v in ctx.items():
        placeholder = "{{" + k + "}}"
        md_content = md_content.replace(placeholder, str(v))
        html_content = html_content.replace(placeholder, str(v))

    # Paridade Gradio (coluna): lâmina aplicada como evento único no início;
    # no sazonal (série diária) o texto "ao longo de / em N dias" fica como está.
    try:
        _is_seas_wo = str(p.get("sim_type", "") or "").lower() == "seasonal"
    except Exception:
        _is_seas_wo = False
    if not _is_seas_wo:
        md_content = md_content.replace("mm** ao longo de **", "mm** aplicada no início do ensaio de **")
        # Etapa 3 (valores já substituídos).
        import re as _re_wo
        md_content = _re_wo.sub(
            r"Lâmina = \*\*(.+?) mm\*\* em \*\*(\d+ dias)\*\*",
            r"Lâmina = **\1 mm** aplicada no início do ensaio de **\2**",
            md_content,
        )
        html_content = html_content.replace("mm</b> em <b>", "mm</b> aplicada no início do ensaio de <b>")

    return md_content, html_content


def generate_simulation_step_by_step(params: Optional[Dict[str, Any]] = None) -> Tuple[str, str]:
    """
    Gera o passo a passo explicativo dinâmico (Markdown e HTML)
    com substituição numérica exata das variáveis inseridas pelo usuário na simulação.
    """
    global _LATEST_SIM_PARAMS
    p = params or _LATEST_SIM_PARAMS or get_default_sim_params()

    # Modo "Somente água": apenas a física hídrica (sem adsorção/transporte de soluto).
    if p.get("water_only"):
        return _generate_water_only_step_by_step(p)

    
    # 1. Extração e Tratamento dos Dados
    _nres = p.get("nutrient_results") or {}
    nutr_sym = str(p.get("nutrient_symbol", ""))
    if not nutr_sym or nutr_sym == "water_only" or (nutr_sym not in _nres and _nres):
        nutr_sym = list(_nres.keys())[0] if _nres else "K"

    if nutr_sym in _nres:
        nutr_name = _nres[nutr_sym].get("name", nutr_sym)
        kd = float(_nres[nutr_sym].get("kd", 0.0))
        elem_dose = float(_nres[nutr_sym].get("dose_kg_ha", p.get("elemental_dose", 0.0)))
        peak_depth = float(_nres[nutr_sym].get("peak_depth_cm", p.get("peak_depth_cm", 25.0)))
        # Balanço da zona radicular (mesma definição de cards/laudo/tabelas):
        # retido 0–raiz / deslocado além da raiz (= abaixo no perfil + fundo) / absorvido.
        retained_pct = float(_nres[nutr_sym].get("retained_root_pct", p.get("retained_pct", 0.0)))
        leached_pct = float(_nres[nutr_sym].get("leaching_ratio_pct", p.get("leaching_pct", 0.0)))
        _upt_pct0 = float(_nres[nutr_sym].get("uptaken_pct", 0.0) or 0.0)
        _bottom_pct0 = float(_nres[nutr_sym].get("leached_bottom_pct", 0.0) or 0.0)
    else:
        nutr_name = str(p.get("nutrient_label", f"Nutriente ({nutr_sym})")).split(" (")[0]
        kd = float(p.get("kd", 0.2353))
        elem_dose = float(p.get("elemental_dose", 0.0))
        peak_depth = float(p.get("peak_depth_cm", 25.0))
        leached_pct = float(p.get("leaching_pct", 15.0))
        retained_pct = float(p.get("retained_pct", 100.0 - leached_pct))
        _upt_pct0 = float(p.get("uptaken_pct", 0.0) or 0.0)
        _bottom_pct0 = 0.0
    # Abertura do deslocado: abaixo da raiz dentro do perfil vs. atravessou o fundo.
    _below_pct0 = max(0.0, float(leached_pct or 0.0) - float(_bottom_pct0 or 0.0))

    fert_name = str(p.get("fertilizer_name", p.get("fertilizer_label", "Adubo")))
    gross_dose = float(p.get("gross_dose", 0.0))
    if gross_dose <= 0.0 and elem_dose > 0.0:
        gross_dose = elem_dose
    elem_mg_cm2 = elem_dose * 0.01
    pct_gross = (elem_dose / gross_dose * 100.0) if gross_dose > 0 else 100.0
    
    soil_name = str(p.get("soil_name", "Solo Selecionado"))
    soil_cit = str(p.get("soil_citation", "Pinho & Miranda (2014); Rosetta PTF (Schaap et al., 2001)"))
    theta_r = float(p.get("theta_r", 0.025))
    theta_s = float(p.get("theta_s", 0.423))
    alpha = float(p.get("alpha", 0.0343))
    n = float(p.get("n", 1.4634))
    m = 1.0 - (1.0 / n) if n > 1.0 else 0.3
    ks = float(p.get("ks", 65.0))
    rho_b = float(p.get("bulk_density", 1.30))
    disp = float(p.get("dispersivity", 16.84))

    # Citação e rastreabilidade científica do Kd por elemento
    if nutr_sym == "N":
        kd_cit = (
            "Nitrato (NO₃⁻) é um ânion monovalente que sofre repulsão eletrostática (exclusão aniônica) "
            "na CTC predominantemente negativa dos solos tropicais (Latossolos). Hipótese de soluto "
            "conservativo sem adsorção sólida: Kd = 0.0000 cm³/g e Retardo R = 1.00. "
            "Valor de referência para a textura do solo (ajustável na tabela de nutrientes); "
            "o modelo representa apenas NO₃⁻ e não simula transformações (ex.: amônio → nitrato)."
        )
    elif nutr_sym == "P":
        kd_cit = (
            f"Quimiossorção específica de alta afinidade (troca de ligantes) na superfície dos óxidos de ferro e alumínio "
            f"(gibbsita, goethita, hematita). Fixação quase irreversível: Kd = {kd:.4f} cm³/g (Novais & Smyth, 1999; Raij, 2011)."
        )
    elif nutr_sym == "K":
        kd_cit = str(p.get("kd_citation") or f"Adsorção eletrostática catiônica monovalente na CTC do solo (Kd = {kd:.4f} cm³/g). Sparks (1987); Raij (2011).")
    elif nutr_sym in ("Ca", "Mg"):
        kd_cit = str(p.get("kd_citation") or f"Adsorção eletrostática catiônica divalente na CTC das argilas e matéria orgânica (Kd = {kd:.4f} cm³/g). SSSA (1996).")
    elif nutr_sym == "S":
        kd_cit = str(p.get("kd_citation") or f"Adsorção aniônica fraca de sulfato (SO₄²⁻) em cargas positivas de horizontes subsuperficiais (Kd = {kd:.4f} cm³/g). Raij (2011).")
    else:
        kd_cit = str(p.get("kd_citation", "Literatura Aberta"))
    
    crop_name = str(p.get("crop_name", "Cultura")).split(" (")[0]
    crop_cit = str(p.get("crop_citation", "Feddes et al. (1978); FAO 56 (Allen et al., 1998)"))
    _cn_l = str(p.get("crop_name", "")).lower()
    has_crop = not ("sem cultura" in _cn_l or "solo nu" in _cn_l or "sem cultura" in str(crop_cit).lower())
    root_depth = float(p.get("root_depth_cm", 40.0))
    h1 = float(p.get("h1", -10.0))
    h2 = float(p.get("h2", -25.0))
    h3 = float(p.get("h3", -400.0))
    h4 = float(p.get("h4", -8000.0))
    
    rain_mm = float(p.get("rain_mm", 100.0))
    total_days = float(p.get("total_days", 7.0))
    profile_depth = float(p.get("profile_depth_cm", p.get("root_depth_cm", 100.0)))
    
    # kg/ha vindos do solver (sobre dose+residual; com residual, % × dose
    # elementar não fecha — usa os campos do balanço, com fallback legado).
    _prim_d = _nres.get(nutr_sym, {}) if isinstance(_nres, dict) else {}

    def _kg(_key: str, _fb: float) -> float:
        try:
            _v = float((_prim_d or {}).get(_key, _fb))
        except (TypeError, ValueError):
            return float(_fb)
        try:
            import math as _mm2
            if _mm2.isnan(_v):
                return float(_fb)
        except Exception:
            pass
        return float(_v)

    retained_kg_ha = _kg("retained_kg_ha", elem_dose * (retained_pct / 100.0))
    _leach_kg_sol = _kg("leached_kg_ha", elem_dose * (leached_pct / 100.0))
    _bottom_kg_sol = _kg("leached_bottom_kg_ha", elem_dose * (_bottom_pct0 / 100.0))
    _below_kg_ha = max(0.0, _leach_kg_sol - _bottom_kg_sol)
    _bottom_kg_ha = _bottom_kg_sol
    leached_kg_ha = _leach_kg_sol
    _upt_kg_ha = _kg("uptaken_kg_ha", elem_dose * (_upt_pct0 / 100.0))

    # Bloco multi-soluto (padrão HYDRUS-1D: N solutos independentes, um balanço por soluto)
    # Cada soluto = espécie química fixa, sem transformações entre espécies.
    _SPECIES = {"N": "NO₃⁻ (nitrato)", "K": "K⁺", "S": "SO₄²⁻ (sulfato)",
                "Ca": "Ca²⁺", "Mg": "Mg²⁺", "P": "H₂PO₄⁻ (fosfato)"}
    _multi_solutes_block = ""
    _multi_retard_rows = []
    _hide_upt = not has_crop
    if len(_nres) > 1:
        _rows = []
        for _sym, _d in _nres.items():
            _sp = _SPECIES.get(_sym, _sym)
            _rt = float(_d.get("retained_root_pct", 0.0) or 0.0)
            _lq = float(_d.get("leaching_ratio_pct", 0.0) or 0.0)
            _bt = float(_d.get("leached_bottom_pct", 0.0) or 0.0)
            _bw = max(0.0, _lq - _bt)
            _row = (
                f"| **{_d.get('name', _sym)}** ({_sp}) | {_sym} | {float(_d.get('dose_kg_ha', 0.0)):.1f} | "
                f"{float(_d.get('kd', 0.0)):.4f} | {float(_d.get('initial_residual_mg_dm3', 0.0)):.2f} | "
                f"{float(_d.get('peak_depth_cm', 0.0)):.1f} | {_rt:.1f}% | {_bw:.1f}% | {_bt:.1f}% |"
            )
            if not _hide_upt:
                _row += f" {float(_d.get('uptaken_pct', 0.0)):.1f}% |"
            _rows.append(_row)
        _upt_head = "" if _hide_upt else " Absorvido |"
        _upt_sep = "" if _hide_upt else " :---: |"
        _multi_solutes_block = (
            "\n---\n\n### 1.1 Solutos Simulados Simultaneamente (padrão HYDRUS-1D)\n"
            f"Esta simulação resolve **{len(_nres)} solutos independentes** no mesmo campo de água. "
            "Cada um tem o seu próprio **Kd** e **teor residual inicial**; a **dispersividade longitudinal** "
            f"($\\lambda$ = {disp:.2f} cm) é parâmetro do solo e vale para todos. "
            "Cada soluto representa uma **espécie química fixa** (ex.: N como NO₃⁻); "
            "o modelo **não simula transformações entre espécies** (ex.: nitrificação).\n\n"
            f"| Soluto (espécie) | Símbolo | Dose (kg/ha) | Kd (cm³/g) | Residual inicial (mg/dm³) | Pico (cm) | Retido 0–{root_depth:.0f} cm | Abaixo no perfil | Fundo |"
            f"{_upt_head}\n"
            f"| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | {_upt_sep}\n"
            + "\n".join(_rows) + "\n\n"
            "> As etapas 4 a 6 abaixo são detalhadas com fórmulas para o **soluto principal** "
            f"(**{nutr_name}**), com comparativo analítico para os demais solutos ativos.\n"
        )
    
    # 2. Cálculos Intermediários Passo a Passo
    h_cc = 100.0
    alpha_h = alpha * h_cc
    alpha_h_n = alpha_h ** n
    denom_vg = (1.0 + alpha_h_n) ** m
    theta_cc = theta_r + (theta_s - theta_r) / denom_vg
    
    q_avg = (rain_mm / 10.0) / max(total_days, 1.0)
    # Vazão efetiva média: drenagem acumulada do solver (Ks já limita fisicamente; sem teto).
    _drain_mm = float(p.get("drainage_mm", 0.0) or 0.0)
    if _drain_mm <= 0.0:
        _drain_mm = float(p.get("q_bottom_cm", 0.0) or 0.0) * 10.0
    q_eff = (_drain_mm / 10.0) / max(total_days, 1.0)
    theta_active = max(theta_r + 0.05, min(theta_s - 0.02, theta_cc * 0.90))
    v_pore = q_eff / theta_active if theta_active > 0 else 0.0
    
    R = 1.0 + (rho_b * kd) / theta_active
    v_solute = v_pore / R if R > 0 else v_pore
    
    D0 = 1.33
    D = disp * v_pore + D0
    
    # 3. Classificação e Descrição física com Limiares Dinâmicos por Elemento (sem recomendação)
    try:
        import math as _m
        _peak_lbl = "indefinido" if _m.isnan(float(peak_depth)) else f"{float(peak_depth):.1f} cm"
    except (TypeError, ValueError):
        _peak_lbl = "indefinido"
    nutrient_thresholds = {
        "N": {"low": 10.0, "mod": 25.0},
        "S": {"low": 10.0, "mod": 25.0},
        "K": {"low": 8.0,  "mod": 20.0},
        "Ca": {"low": 8.0, "mod": 20.0},
        "Mg": {"low": 8.0, "mod": 20.0},
        "P": {"low": 2.0,  "mod": 5.0},
    }
    th = nutrient_thresholds.get(nutr_sym, {"low": 10.0, "mod": 25.0})
    low_th = th["low"]
    mod_th = th["mod"]

    if leached_pct <= low_th:
        risk_icon = "✅ [Excelente Retenção]"
        risk_level = f"Baixo deslocamento (≤ {low_th:.0f}%)"
        diag_plan = (
            f"<strong>Descrição física do cenário:</strong> Lâmina de {rain_mm:.0f} mm, {nutr_name} "
            f"com {retained_pct:.1f}% na camada {('rizosfera até ' + f'{root_depth:.0f} cm') if has_crop else (f'avaliada (0–{root_depth:.0f} cm)')}. Pico em {_peak_lbl}."
        )
    elif leached_pct <= mod_th:
        risk_icon = "⚠️ [Deslocamento Moderado]"
        risk_level = f"Deslocamento moderado ({low_th:.0f}% a {mod_th:.0f}%)"
        diag_plan = (
            f"<strong>Descrição física do cenário:</strong> Deslocamento moderado "
            f"({leached_pct:.1f}% além de {root_depth:.0f} cm, pico em {_peak_lbl})."
        )
    else:
        risk_icon = "🚨 [Deslocamento Severo]"
        risk_level = f"Deslocamento severo no subsolo (> {mod_th:.0f}%)"
        diag_plan = (
            f"<strong>Descrição física do cenário:</strong> Deslocamento severo por fluxo vertical. "
            f"Dose sob chuva de {rain_mm:.0f} mm com {leached_pct:.1f}% do {nutr_name} no subsolo."
        )

    diag_text = diag_plan


    if kd <= 1e-4:
        r_interpretation = (
            f"Como o $K_d$ é nulo ($K_d = {kd:.4f}\\text{{ cm}}^3/\\text{{g}}$ para {nutr_name}), "
            "o fator de retardamento é estritamente $R = 1,00$. O nitrato ($NO_3^-$) sofre repulsão "
            "eletrostática pelas cargas negativas dos coloides do solo (fenômeno de exclusão aniônica na CTC), "
            "avançando exatamente na mesma velocidade média da água de infiltração nos poros ($v_s = v$). "
            "Não há adsorção nem fixação na matriz sólida."
        )
    elif R > 1.2:
        r_interpretation = (
            f"O nutriente avança **{R:.1f} vezes mais lento** que a frente de água livre ($v_s = v / {R:.2f}$), "
            f"retido pela interação físico-química com a matriz coloidal do solo ($K_d = {kd:.4f}\\text{{ cm}}^3/\\text{{g}}$)."
        )
    else:
        r_interpretation = (
            f"Como o $K_d$ é muito baixo ($K_d = {kd:.4f}\\text{{ cm}}^3/\\text{{g}}$), $R = {R:.2f} \\approx 1,0$. "
            "O nutriente praticamente não encontra barreiras de adsorção e desce junto com a frente úmida de drenagem."
        )

    # Bloco comparativo de retardamento multi-soluto
    multi_retardation_block = ""
    if len(_nres) > 1:
        _ret_lines = []
        for _s, _d in _nres.items():
            _s_kd = float(_d.get("kd", 0.0))
            _s_R = 1.0 + (rho_b * _s_kd) / max(theta_active, 0.05)
            _s_vs = v_pore / _s_R if _s_R > 0 else v_pore
            if _s_kd < 1e-4:
                _mech = "Exclusão aniônica na CTC (transporte conservativo, R = 1,0)"
            elif _s_kd > 10.0:
                _mech = f"Quimiossorção específica em Fe/Al (alta adsorção, R = {_s_R:.1f})"
            elif _s in ("Ca", "Mg"):
                _mech = f"Adsorção eletrostática divalente na CTC (R = {_s_R:.2f})"
            elif _s == "K":
                _mech = f"Adsorção eletrostática monovalente na CTC (R = {_s_R:.2f})"
            else:
                _mech = f"Adsorção coloidal linear (R = {_s_R:.2f})"
            _ret_lines.append(
                f"| **{_d.get('name', _s)}** ({_s}) | {_s_kd:.4f} | **{_s_R:.2f}** | **{_s_vs:.2f} cm/dia** | {_mech} |"
            )
        multi_retardation_block = (
            "\n\n#### Comparativo de Retardo entre os Solutos da Simulação\n\n"
            "| Soluto | $K_d$ (cm³/g) | Fator de Retardo ($R$) | Velocidade Efetiva ($v_s$) | Mecanismo Físico Predominante |\n"
            "| :--- | :---: | :---: | :---: | :--- |\n"
            + "\n".join(_ret_lines) + "\n"
        )

    # Textos da Etapa 3/6 adaptados à presença de cultura (sem cultura: sem Feddes/raízes).
    if has_crop:
        feddes_detail = (
            f"Onde o termo de consumo radicular $S(h, z) = \\alpha(h) \\cdot b(z) \\cdot T_p$ utiliza "
            f"os potenciais de Feddes da cultura ($P_0 = {h1:.0f}$, $P_{{2H}} = {h2:.0f}$, "
            f"$P_3 = {h3:.0f}$, $P_4 = {h4:.0f}\\text{{ cm}}$)."
        )
        etapa6_title = "Balanço de Massa na Rizosfera"
        etapa6_info = (
            f"**Parâmetro de Entrada que Delimita a Rizosfera:** Cultura selecionada = **{crop_name}** "
            f"(Profundidade útil das raízes: **{root_depth:.0f} cm**)"
        )
        etapa6_origin = (
            f"**Origem & Rastreabilidade:** Todo nutriente transportado além de **{root_depth:.0f} cm** "
            f"é classificado como perda por lixiviação para esta cultura, conforme calibrado em: {crop_cit.rstrip('.')}."
        )
        mass_lhs = "M_{\\text{rizosfera}}"
        retido_local = "retido na rizosfera"
        etapa6_html_title = "Balanço de Massa e Lixiviação na Rizosfera"
        etapa6_html_info = (
            f"<b>Parâmetro de Entrada que Delimita a Rizosfera:</b> Cultura selecionada = <b>{crop_name}</b> "
            f"(Profundidade útil das raízes: <b>{root_depth:.0f} cm</b>)<br/>"
        )
        etapa6_html_origin = (
            f"<b>Origem & Rastreabilidade:</b> Todo nutriente transportado além de <b>{root_depth:.0f} cm</b> "
            f"é classificado como perda por lixiviação para esta cultura, conforme calibrado em: {crop_cit.rstrip('.')}."
        )
    else:
        feddes_detail = "Sem cultura: $S(h, z) = 0$ (sem absorção radicular; apenas evaporação do solo)."
        etapa6_title = "Balanço de Massa na Camada Avaliada"
        etapa6_info = (
            f"**Camada avaliada:** 0–{root_depth:.0f} cm (perfil sem raízes; sem cultura)"
        )
        etapa6_origin = (
            f"**Origem & Rastreabilidade:** Todo nutriente transportado além de **{root_depth:.0f} cm** "
            f"é classificado como perda por lixiviação para além desta camada, conforme calibrado em: {crop_cit.rstrip('.')}."
        )
        mass_lhs = "M_{\\text{camada}}"
        retido_local = "retido na camada avaliada"
        etapa6_html_title = "Balanço de Massa e Lixiviação na Camada Avaliada"
        etapa6_html_info = (
            f"<b>Camada avaliada:</b> 0–{root_depth:.0f} cm (perfil sem raízes; sem cultura)<br/>"
        )
        etapa6_html_origin = (
            f"<b>Origem & Rastreabilidade:</b> Todo nutriente transportado além de <b>{root_depth:.0f} cm</b> "
            f"é classificado como perda por lixiviação para além desta camada, conforme calibrado em: {crop_cit.rstrip('.')}."
        )

    # Seção Unificada: Gráficos, Laudo e Download
    global _LATEST_SIM_RESULT
    img_b64 = _LATEST_SIM_RESULT.get("img_base64", "") if _LATEST_SIM_RESULT else ""
    report_html = _LATEST_SIM_RESULT.get("report_html", "") if _LATEST_SIM_RESULT else ""

    if img_b64:
        graph_section = f"""
        <div style="background: #ffffff; border: 1px solid var(--border); border-radius: 12px; padding: 22px; margin-bottom: 22px; box-shadow: 0 1px 4px rgba(0,0,0,0.04);">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; flex-wrap: wrap; gap: 10px;">
                <h3 style="font-size: 17px; color: #0f172a; font-weight: 700; margin: 0;">1. Perfil de Distribuição no Solo e Frente de Água</h3>
                <div style="display: flex; align-items: center; gap: 10px;">
                    <a href="/download-perfil-excel" target="_blank" style="display: inline-flex; align-items: center; gap: 7px; background: #059669; color: #ffffff; text-decoration: none; padding: 7px 15px; border-radius: 8px; font-size: 13px; font-weight: 600; box-shadow: 0 1px 3px rgba(5,150,105,0.25); transition: background 0.15s ease;">
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
                        Baixar Dados do Perfil (.XLSX)
                    </a>
                    <span class="step-tag">Física 1D de Alta Resolução</span>
                </div>
            </div>
            <div style="background: #ffffff; border-radius: 8px; padding: 8px; border: 1px solid var(--border); text-align: center;">
                <img src="data:image/png;base64,{img_b64}" alt="Perfil Simulado no Solo" style="max-width: 100%; height: auto; border-radius: 6px; display: block; margin: 0 auto;" />
            </div>
            <div style="display: flex; justify-content: flex-end; margin-top: 10px;">
                <a href="/download-perfil-excel" target="_blank" style="display: inline-flex; align-items: center; gap: 6px; color: #059669; text-decoration: none; font-size: 12.5px; font-weight: 600;">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
                    Baixar planilha Excel com profundidade, concentração e umidade (.xlsx)
                </a>
            </div>
        </div>
        """
    else:
        graph_section = ""

    if report_html:
        report_section = f"""
        <div style="background: #ffffff; border: 1px solid var(--border); border-radius: 12px; padding: 22px; margin-bottom: 22px; line-height: 1.8; box-shadow: 0 1px 4px rgba(0,0,0,0.04);">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; border-bottom: 1px solid var(--border); padding-bottom: 10px;">
                <h3 style="font-size: 17px; color: #0f172a; font-weight: 700; margin: 0;">2. Laudo Técnico — Descrição Física</h3>
                <span class="step-tag">Descrição Física</span>
            </div>
            <div style="color: var(--text); font-size: 14px;">
                {report_html}
            </div>
        </div>
        """
    else:
        report_section = ""

    # Download do pacote HYDRUS-1D: retirado do produto por enquanto.
    # O gerador de arquivos segue em `core/hydrus_io.py` para reativação futura.
    download_section = ""

    # Etapa 1: dose direta (sem fertilizante comercial) vs. adubo comercial.
    # Direta: sem conversão por garantia; rótulo da tabela 1 vira elementar.
    _is_direct_dose = (str(fert_name).strip() == "Dose Direta do Elemento")
    if _is_direct_dose:
        _dose_table_label = "Dose Informada (elementar)"
        _etapa1_origem_md = ("dose elementar informada diretamente na tabela de nutrientes "
                             "(sem conversão por garantia comercial; teor = 100%).")
        _etapa1_origem_html = ("dose elementar informada diretamente na tabela de nutrientes "
                               "(sem conversão por garantia comercial; teor = 100%).")
    else:
        _dose_table_label = "Dose Comercial Bruta"
        _etapa1_origem_md = (f"Estequiometria do adubo comercial com garantia de "
                             f"**{pct_gross:.1f}% de {nutr_sym}** (Garantia MAPA / Rótulo Comercial).")
        _etapa1_origem_html = (f"Estequiometria do adubo comercial com garantia de "
                               f"<b>{pct_gross:.1f}% de {nutr_sym}</b> (Garantia MAPA / Rótulo Comercial).")

    # Contexto para substituição de placeholders
    ctx = {
        "dose_table_label": _dose_table_label,
        "etapa1_origem_md": _etapa1_origem_md,
        "etapa1_origem_html": _etapa1_origem_html,
        "graph_section": graph_section,
        "report_section": report_section,
        "download_section": download_section,
        "multi_solutes_block": _multi_solutes_block,
        "nutr_sym": nutr_sym,
        "nutr_name": nutr_name,
        "fert_name": fert_name,
        "gross_dose": f"{gross_dose:.1f}",
        "elem_dose": f"{elem_dose:.2f}",
        "elem_mg_cm2": f"{elem_mg_cm2:.4f}",
        "pct_gross": f"{pct_gross:.1f}",
        "soil_name": soil_name,
        "soil_cit": soil_cit,
        "crop_name": crop_name,
        "crop_cit": crop_cit,
        "h1": f"{h1:.0f}",
        "h2": f"{h2:.0f}",
        "h3": f"{h3:.0f}",
        "h4": f"{h4:.0f}",
        "theta_r": f"{theta_r:.4f}",
        "theta_s": f"{theta_s:.4f}",
        "theta_diff": f"{(theta_s - theta_r):.4f}",
        "alpha": f"{alpha:.4f}",
        "n": f"{n:.4f}",
        "m": f"{m:.4f}",
        "ks": f"{ks:.1f}",
        "rho_b": f"{rho_b:.2f}",
        "kd": f"{kd:.4f}",
        "kd_cit": kd_cit,
        "disp": f"{disp:.2f}",
        "rain_mm": f"{rain_mm:.1f}",
        "total_days": f"{total_days:.0f}",
        "profile_depth": f"{profile_depth:.0f}",
        "root_depth": f"{root_depth:.0f}",
        "leached_pct": f"{leached_pct:.1f}",
        "retained_pct": f"{retained_pct:.1f}",
        "peak_depth": _peak_lbl,
        "retained_kg_ha": f"{retained_kg_ha:.2f}",
        "leached_kg_ha": f"{leached_kg_ha:.2f}",
        "below_pct": f"{_below_pct0:.1f}",
        "below_kg_ha": f"{_below_kg_ha:.2f}",
        "bottom_pct": f"{_bottom_pct0:.1f}",
        "bottom_kg_ha": f"{_bottom_kg_ha:.2f}",
        "upt_pct": f"{_upt_pct0:.1f}",
        "upt_kg_ha": f"{_upt_kg_ha:.2f}",
        "alpha_h": f"{alpha_h:.2f}",
        "alpha_h_n": f"{alpha_h_n:.3f}",
        "denom_vg": f"{denom_vg:.3f}",
        "theta_cc": f"{theta_cc:.3f}",
        "theta_cc_pct": f"{(theta_cc * 100.0):.1f}",
        "q_eff": f"{q_eff:.2f}",
        "theta_active": f"{theta_active:.3f}",
        "v_pore": f"{v_pore:.3f}",
        "R": f"{R:.2f}",
        "v_solute": f"{v_solute:.2f}",
        "D": f"{D:.2f}",
        "D0": f"{D0:.2f}",
        "feddes_detail": feddes_detail,
        "etapa6_title": etapa6_title,
        "etapa6_info": etapa6_info,
        "etapa6_origin": etapa6_origin,
        "mass_lhs": mass_lhs,
        "retido_local": retido_local,
        "etapa6_html_title": etapa6_html_title,
        "etapa6_html_info": etapa6_html_info,
        "etapa6_html_origin": etapa6_html_origin,
        "risk_icon": risk_icon,
        "risk_level": risk_level,
        "diag_text": diag_text,
        "r_interpretation": r_interpretation,
        "multi_retardation_block": multi_retardation_block
    }

    # -------------------------------------------------------------
    # TEMPLATE MARKDOWN
    # -------------------------------------------------------------
    md_template = r"""
# Memória de Cálculo & Passo a Passo da Simulação
**Resolução Numérica Passo a Passo da Simulação Executada**

---

### 1. Dados e Parâmetros Configurados nesta Simulação

| Parâmetro de Entrada | Símbolo | Valor Adotado | Unidade | Significado na Simulação |
| :--- | :---: | :---: | :---: | :--- |
| **Fertilizante Selecionado** | - | **{{fert_name}}** | - | Fonte de adubo informada |
| **{{dose_table_label}}** | $D_{\text{adubo}}$ | **{{gross_dose}}** | kg/ha | Quantidade aplicada na superfície |
| **Nutriente Avaliado** | - | **{{nutr_name}} ({{nutr_sym}})** | - | Elemento monitorado no solo |
| **Dose Elementar Líquida** | $M_{\text{líq}}$ | **{{elem_dose}}** | kg/ha | Fração pura ativa do elemento |
| **Solo Utilizado** | - | **{{soil_name}}** | - | Matriz física do perfil |
| **Umidade Residual** | $\theta_r$ | **{{theta_r}}** | $\text{cm}^3/\text{cm}^3$ | Água fortemente retida aos sólidos |
| **Umidade de Saturação** | $\theta_s$ | **{{theta_s}}** | $\text{cm}^3/\text{cm}^3$ | Porosidade total preenchida por água |
| **Parâmetro de Escala $\alpha$** | $\alpha$ | **{{alpha}}** | $\text{cm}^{-1}$ | Inverso da sucção de borbulhamento |
| **Índice de Distribuição de Poros** | $n$ | **{{n}}** | - | $m = 1 - 1/n = {{m}}$ |
| **Condutividade Hidráulica Saturada** | $K_s$ | **{{ks}}** | cm/dia | Infiltração máxima em saturação |
| **Densidade Aparente do Solo** | $\rho_b$ | **{{rho_b}}** | $\text{g/cm}^3$ | Massa seca por volume de solo |
| **Coeficiente de Adsorção** | $K_d$ | **{{kd}}** | $\text{cm}^3/\text{g}$ | {{kd_cit}} |
| **Dispersividade Longitudinal** | $\lambda$ | **{{disp}}** | cm | Espalhamento mecânico da pluma |
| **Lâmina de Chuva / Água** | $P$ | **{{rain_mm}}** | mm | Precipitação acumulada no período |
| **Período de Simulação** | $t_{\text{total}}$ | **{{total_days}}** | dias | Tempo físico simulado |
| **Cultura & Sistema Radicular** | - | **{{crop_name}}** | - | {{crop_cit}} |
| **Camada Avaliada** | $z_{\text{aval}}$ | **{{root_depth}}** | cm | Camada avaliada (0–{{root_depth}} cm) |
{{multi_solutes_block}}

---

### Etapa 1: Carga Elementar Inicial na Superfície ($z = 0$)
> **Parâmetro de Entrada:** Fertilizante comercial = **{{fert_name}}** com Dose Bruta = **{{gross_dose}} kg/ha**  
> **Origem & Rastreabilidade:** {{etapa1_origem_md}}

O simulador converte a dose bruta de adubo comercial na carga líquida elementar:
$$
M_{\text{{{nutr_sym}}}} = D_{\text{adubo}} \times \left( \frac{\text{Teor}_{\text{{{nutr_sym}}}}}{100} \right) = {{gross_dose}} \times \left( \frac{{{pct_gross}}}{100} \right) = \mathbf{{{elem_dose}}\text{ kg/ha de } {{nutr_sym}}}
$$

Convertendo para a densidade superficial na malha numérica ($1\text{ kg/ha} = 0,01\text{ mg/cm}^2$):
$$
M_{\text{{{nutr_sym}}}} = {{elem_dose}} \times 0,01 = \mathbf{{{elem_mg_cm2}}\text{ mg/cm}^2}
$$

---

### Etapa 2: Parametrização da Curva de Retenção de Água (van Genuchten, 1980)
> **Parâmetro de Entrada:** Tipo de Solo selecionado = **{{soil_name}}**  
> **Origem & Rastreabilidade Científica:** {{soil_cit}}

A umidade volumétrica $\theta$ em função da sucção mátrica $h$ no solo selecionado é calculada por:
$$
\theta(h) = \theta_r + \frac{\theta_s - \theta_r}{\left[1 + |\alpha h|^n\right]^m}, \quad m = 1 - \frac{1}{n} = 1 - \frac{1}{{{n}}} = {{m}}
$$

Substituindo a sucção de **capacidade de campo** ($h = -100\text{ cm}$ ou $-10\text{ kPa}$) com os parâmetros do solo escolhido:
$$
|\alpha h| = {{alpha}} \times 100 = {{alpha_h}} \implies |{{alpha_h}}|^{{{n}}} \approx {{alpha_h_n}}
$$

$$
\theta_{\text{cc}} = {{theta_r}} + \frac{{{theta_diff}}}{{{denom_vg}}} = \mathbf{{{theta_cc}}\text{ cm}^3/\text{cm}^3}
$$
*(equivalente a {{theta_cc_pct}}% de umidade volumétrica na capacidade de campo)*

---

### Etapa 3: Fluxo da Chuva e Velocidade nos Poros (Richards 1D)
> **Parâmetros de Entrada:** Lâmina de Chuva = **{{rain_mm}} mm** (ao longo de **{{total_days}} dias**) e Cultura = **{{crop_name}}**  
> **Origem & Rastreabilidade Científica da Cultura:** {{crop_cit}}

A movimentação da água obedece à **Equação de Richards unidimensional**:
$$
\frac{\partial \theta}{\partial t} = \frac{\partial}{\partial z} \left[ K(h) \left( \frac{\partial h}{\partial z} - 1 \right) \right] - S(h, z)
$$

{{feddes_detail}}

A velocidade média da água que se desloca pelos poros ($v$) sob a lâmina de **{{rain_mm}} mm** é dada pela relação de Darcy:
$$
v = \frac{q}{\theta} = \frac{{{q_eff}}\text{ cm/dia}}{{{theta_active}}\text{ cm}^3/\text{cm}^3} \approx \mathbf{{{v_pore}}\text{ cm/dia}}
$$
*(Velocidade teórica de uma frente de água livre ou de um ânion sem adsorção).*

---

### Etapa 4: Adsorção Coloidal e Fator de Retardamento ($R$)
> **Parâmetros de Entrada:** Nutriente avaliado = **{{nutr_name}} ({{nutr_sym}})** interagindo com o solo = **{{soil_name}}**  
> **Origem & Rastreabilidade Científica da Adsorção:** {{kd_cit}}

A atração do nutriente **{{nutr_name}}** pelos coloides do solo segue a isoterma linear calibrada ($S = K_d \cdot C$). O **Fator de Retardamento ($R$)** é:
$$
R = 1 + \frac{\rho_b \cdot K_d}{\theta}
$$

Substituindo a densidade do solo ($\rho_b = {{rho_b}}\text{ g/cm}^3$), o coeficiente ($K_d = {{kd}}\text{ cm}^3/\text{g}$) e a umidade ativa ($\theta \approx {{theta_active}}$):
$$
R = 1 + \frac{{{rho_b}} \times {{kd}}}{{{theta_active}}} = \mathbf{{{R}}}
$$

> **Significado Físico:**
> {{r_interpretation}}
{{multi_retardation_block}}

---

### Etapa 5: Transporte de Solutos (ADE) e Posição do Pico da Pluma
> **Parâmetros de Entrada:** Nutriente = **{{nutr_name}}**, Solo = **{{soil_name}}**, Chuva = **{{rain_mm}} mm**  
> **Origem & Rastreabilidade:** Transporte Advectivo-Dispersivo com freio coloidal ($R = {{R}}$) e dispersividade mecânica $\lambda = {{disp}}\text{ cm}$.

O transporte advectivo-dispersivo com retardamento é regido por:
$$
R \frac{\partial C}{\partial t} = D \frac{\partial^2 C}{\partial z^2} - v \frac{\partial C}{\partial z}
$$

Onde o coeficiente de dispersão hidrodinâmica total é:
$$
D = \lambda \cdot |v| + D_0 = {{disp}} \times {{v_pore}} + {{D0}} = \mathbf{{{D}}\text{ cm}^2/\text{dia}}
$$

A velocidade aparente de avanço do pico retardado é:
$$
v_s = \frac{v}{R} = \frac{{{v_pore}}\text{ cm/dia}}{{{R}}} \approx \mathbf{{{v_solute}}\text{ cm/dia}}
$$

* **Profundidade final do pico observada nesta simulação:** **$z_{\text{pico}} = {{peak_depth}}$**

---

### Etapa 6: {{etapa6_title}} ($0 - {{root_depth}}\text{ cm}$)
> {{etapa6_info}}  
> {{etapa6_origin}}

Integrando numericamente todo o perfil da coluna de solo ao término dos **{{total_days}} dias** (mesmo balanço de cards, laudo e tabelas — soma retido + abaixo + fundo + absorvido + grânulo = dose + residual):
$$
{{mass_lhs}} = \int_0^{{{root_depth}}\text{ cm}} \left[ \theta(z) C(z) + \rho_b K_d C(z) \right] dz = \mathbf{{{retained_kg_ha}}\text{ kg/ha}}
$$
*(representando {{retained_pct}}% do nutriente aplicado {{retido_local}})*

$$
M_{\text{abaixo ({{root_depth}}–{{profile_depth}} cm, no perfil)}} = \mathbf{{{below_kg_ha}}\text{ kg/ha}}
$$
*(representando {{below_pct}}% do nutriente aplicado presente abaixo da camada, ainda dentro do domínio)*

$$
M_{\text{fundo (atravessou {{profile_depth}} cm)}} = \mathbf{{{bottom_kg_ha}}\text{ kg/ha}}
$$
*(representando {{bottom_pct}}% do nutriente aplicado que efetivamente saiu do domínio pelo fundo)*

---

### Escopo e Limites da Simulação
* **Espécies simuladas:** cada soluto representa uma espécie química fixa (N como NO₃⁻, K como K⁺, S como SO₄²⁻); o modelo **não simula transformações químicas** entre espécies.
* **Kd de referência:** valores de literatura para a textura do solo, ajustáveis na tabela de nutrientes — **não calibrados experimentalmente** para este talhão.
* **Absorção pela cultura:** proporcional à transpiração e à concentração dissolvida, **limitada pela demanda nutricional da cultura no ciclo** (teto por nutriente; o excedente permanece no solo); representa o potencial de captura sob essa demanda, não uma previsão garantida.
* **Uso recomendado:** comparação entre manejos/cenários, não previsão quantitativa garantida de absorção ou perda para a cultura.

""".strip()

    # -------------------------------------------------------------
    # TEMPLATE HTML
    # -------------------------------------------------------------
    html_template = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cálculo Detalhado (passo a passo) - Hydrus</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.css">
    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.js"></script>
    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/contrib/auto-render.min.js"
        onload="renderMathInElement(document.body, {delimiters: [{left: '$$', right: '$$', display: true}, {left: '$', right: '$', display: false}, {left: '\\[', right: '\\]', display: true}, {left: '\\(', right: '\\)', display: false}]});"></script>
    <style>
        :root {
            --bg: #f5f4ef;
            --surface: #ffffff;
            --surface-2: #f8fafc;
            --surface-3: #f1f5f9;
            --border: #e2e8f0;
            --border-strong: #cbd5e1;
            --text: #1e293b;
            --text-muted: #64748b;
            --accent: #059669;
            --accent-dark: #047857;
            --accent-light: #ecfdf5;
            --header-bg: #065f46;
            --code-bg: #f8fafc;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg);
            color: var(--text);
            line-height: 1.65;
            padding: 24px;
        }
        .container {
            max-width: 1100px;
            margin: 0 auto;
        }
        .app-header {
            background: linear-gradient(135deg, #065f46 0%, #047857 100%);
            border: 1px solid rgba(255, 255, 255, 0.18);
            border-radius: 14px;
            box-shadow: 0 4px 16px -2px rgba(6, 95, 70, 0.28);
            padding: 12px 24px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 18px;
        }
        .header-logos {
            display: flex;
            align-items: center;
            gap: 16px;
            flex: 0 0 auto;
        }
        .header-logo-img {
            height: 56px;
            width: auto;
            max-width: 180px;
            object-fit: contain;
            filter: drop-shadow(0 1px 3px rgba(0, 0, 0, 0.25));
        }
        .app-header-text {
            text-align: right;
            color: #ffffff;
        }
        .app-header-text h1 {
            font-size: 18px;
            font-weight: 700;
            margin: 0 0 2px 0;
            color: #ffffff;
            line-height: 1.3;
        }
        .app-header-text p {
            font-size: 13px;
            color: #d1fae5;
            margin: 0;
            font-weight: 500;
        }
        .page-banner {
            background: #ffffff;
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px 24px;
            margin-bottom: 22px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.04);
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
        }
        .page-banner h2 {
            font-size: 18px;
            font-weight: 800;
            color: #0f172a;
            margin-bottom: 4px;
        }
        .page-banner p {
            font-size: 13.5px;
            color: var(--text-muted);
            margin: 0;
        }
        .content { margin-top: 10px; }
        .section-header {
            margin: 28px 0 16px 0;
            border-bottom: 2px solid var(--border);
            padding-bottom: 8px;
        }
        .section-header h2 {
            font-size: 18px;
            color: #0f172a;
            font-weight: 800;
            margin: 0 0 4px 0;
        }
        .section-header p {
            color: var(--text-muted);
            font-size: 13.5px;
            margin: 0;
        }
        .step-card {
            border: 1px solid var(--border);
            border-radius: 12px;
            background: #ffffff;
            margin-bottom: 20px;
            overflow: hidden;
            box-shadow: 0 1px 4px rgba(0,0,0,0.04);
        }
        .step-header {
            background: #f8fafc;
            padding: 12px 18px;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .step-title {
            display: flex;
            align-items: center;
            gap: 10px;
            font-weight: 700;
            font-size: 15.5px;
            color: #0f172a;
        }
        .step-num {
            background: var(--accent);
            color: #ffffff;
            width: 26px;
            height: 26px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            font-weight: 800;
        }
        .step-tag {
            font-size: 11.5px;
            font-weight: 600;
            padding: 3px 8px;
            border-radius: 6px;
            background: var(--accent-light);
            color: #065f46;
            border: 1px solid #a7f3d0;
        }
        .step-body { padding: 18px; font-size: 14px; color: var(--text); }
        .math-block {
            background: var(--code-bg);
            border-radius: 8px;
            padding: 12px;
            margin: 12px 0;
            text-align: center;
            font-size: 15px;
            border: 1px solid var(--border);
            color: #0f172a;
            overflow-x: auto;
        }
        .table-custom {
            width: 100%;
            border-collapse: collapse;
            margin: 14px 0;
            font-size: 13.5px;
            background: #ffffff;
        }
        .table-custom th, .table-custom td {
            border: 1px solid var(--border);
            padding: 8px 12px;
            text-align: left;
            color: var(--text);
        }
        .table-custom th { background: #f1f5f9; font-weight: 600; color: #0f172a; }
        .result-card {
            background: #ffffff;
            border: 1.5px solid var(--accent);
            border-radius: 12px;
            padding: 22px;
            margin: 24px 0;
            box-shadow: 0 4px 16px rgba(5, 150, 105, 0.08);
        }
        .result-card h2 {
            font-size: 18px;
            color: #065f46;
            margin-bottom: 12px;
            font-weight: 700;
        }
        .conclusao-card {
            background: #f8fafc;
            border-left: 5px solid var(--accent);
            border-radius: 0 12px 12px 0;
            padding: 22px;
            margin: 24px 0;
            border-top: 1px solid var(--border);
            border-right: 1px solid var(--border);
            border-bottom: 1px solid var(--border);
        }
        .conclusao-card h2 { font-size: 18px; color: #065f46; margin-bottom: 10px; font-weight: 700; }
        .btn {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 9px 18px;
            border-radius: 8px;
            font-size: 13.5px;
            font-weight: 600;
            text-decoration: none;
            cursor: pointer;
            border: 1px solid var(--border-strong);
            background: #ffffff;
            color: var(--text);
            transition: all 0.2s ease;
        }
        .btn:hover {
            background: #f1f5f9;
            border-color: #94a3b8;
        }
        .btn-primary {
            background: var(--accent);
            color: #ffffff !important;
            border: 1px solid var(--accent-dark);
            font-weight: 700;
        }
        .btn-primary:hover {
            background: var(--accent-dark);
            color: #ffffff !important;
        }
        .nav-actions {
            display: flex;
            justify-content: space-between;
            margin-top: 32px;
            padding-top: 20px;
            border-top: 1px solid var(--border);
        }
        .info-box {
            background: #f0fdf4;
            border-left: 4px solid var(--accent);
            padding: 10px 14px;
            margin-bottom: 14px;
            border-radius: 4px;
            font-size: 13.5px;
            border-top: 1px solid #bbf7d0;
            border-right: 1px solid #bbf7d0;
            border-bottom: 1px solid #bbf7d0;
            color: #166534;
        }
        .info-box b {
            color: #14532d;
        }
        @media print {
            body { padding: 0; background: #ffffff; }
            .nav-actions, .page-banner .btn { display: none !important; }
            .container { box-shadow: none; border: none; max-width: 100%; }
        }
    </style>
</head>
<body>

<div class="container">
    <div class="app-header">
        <div class="header-logos">
            <img src="/logo-ppg" alt="PPG" class="header-logo-img" />
            <img src="/logo-gpeas" alt="GPEAS" class="header-logo-img" />
        </div>
        <div class="app-header-text">
            <h1>Hydrus — Relatório Físico & Auditoria</h1>
            <p>Simulação de transporte de água e nutrientes no perfil do solo</p>
        </div>
    </div>

    <div class="page-banner">
        <div>
            <h2>Cálculo Detalhado (passo a passo)</h2>
            <p>Perfil de infiltração, equações de van Genuchten, Richards e Advecção-Dispersão com substituição numérica exata.</p>
        </div>
        <button class="btn" onclick="window.print()">Imprimir / Salvar PDF</button>
    </div>

    <div class="content">

        <!-- 0. RESULTADOS UNIFICADOS (GRÁFICOS, LAUDO E ARQUIVOS) -->
        {{graph_section}}
        {{report_section}}
        {{download_section}}

        <div class="section-header">
            <h2>3. Memória de Cálculo & Dedução Física Passo a Passo</h2>
            <p>Rastreabilidade completa das equações de van Genuchten, Richards e Advecção-Dispersão.</p>
        </div>

        <!-- 1. DADOS DE ENTRADA -->
        <div class="step-card" style="padding: 18px; margin-bottom: 20px;">
            <h3 style="font-size: 16px; margin-bottom: 12px; color: #065f46; font-weight: 700;">Dados e Parâmetros Configurados nesta Simulação</h3>
            <table class="table-custom">
                <tr><th>Parâmetro</th><th>Símbolo</th><th>Valor Adotado</th><th>Significado</th></tr>
                <tr><td>Fertilizante</td><td>-</td><td><b>{{fert_name}}</b></td><td>Fonte selecionada pelo usuário</td></tr>
                <tr><td>{{dose_table_label}}</td><td>$D_{\text{adubo}}$</td><td><b>{{gross_dose}} kg/ha</b></td><td>Dose total aplicada</td></tr>
                <tr><td>Nutriente</td><td>-</td><td><b>{{nutr_name}} ({{nutr_sym}})</b></td><td>Elemento simulado</td></tr>
                <tr><td>Dose Elementar Líquida</td><td>$M_{\text{líq}}$</td><td><b>{{elem_dose}} kg/ha</b> ({{elem_mg_cm2}} mg/cm²)</td><td>Quantidade pura do nutriente</td></tr>
                <tr><td>Solo</td><td>-</td><td><b>{{soil_name}}</b></td><td>Parâmetros físicos da matriz</td></tr>
                <tr><td>Umidades do Solo</td><td>$\theta_r, \theta_s$</td><td><b>{{theta_r}} / {{theta_s}}</b> cm³/cm³</td><td>Residual e Saturação (van Genuchten)</td></tr>
                <tr><td>Forma da Curva (VG)</td><td>$\alpha, n$</td><td><b>{{alpha}} cm⁻¹ / {{n}}</b> ($m = {{m}}$)</td><td>Borbulhamento e homogeneidade de poros</td></tr>
                <tr><td>Condutividade Saturada</td><td>$K_s$</td><td><b>{{ks}} cm/dia</b></td><td>Permeabilidade máxima em saturação</td></tr>
                <tr><td>Densidade do Solo</td><td>$\rho_b$</td><td><b>{{rho_b}} g/cm³</b></td><td>Massa de sólidos por volume</td></tr>
                <tr><td>Coeficiente de Adsorção</td><td>$K_d$</td><td><b>{{kd}} cm³/g</b></td><td>{{kd_cit}}</td></tr>
                <tr><td>Lâmina de Chuva / Água</td><td>$P$</td><td><b>{{rain_mm}} mm</b> em <b>{{total_days}} dias</b></td><td>Infiltração superficial acumulada</td></tr>
                <tr><td>Cultura & Sistema Radicular</td><td>-</td><td><b>{{crop_name}}</b></td><td>{{crop_cit}}</td></tr>
                <tr><td>Camada Avaliada</td><td>$z_{\text{aval}}$</td><td><b>{{root_depth}} cm</b></td><td>Camada avaliada (0–{{root_depth}} cm)</td></tr>
            </table>
        </div>

        <div style="margin: 28px 0 16px 0;">
            <h3 style="font-size: 17px; color: #0f172a; font-weight: 800; margin: 0 0 4px 0;">Etapas do Cálculo Físico Passo a Passo</h3>
            <p style="color: var(--text-muted); font-size: 13.5px; margin: 0;">Equações resolvidas numericamente com substituição dos valores da sua simulação.</p>
        </div>

        <!-- PASSO 1 -->
        <div class="step-card">
            <div class="step-header">
                <div class="step-title">
                    <span class="step-num">1</span>
                    <span>Carga Elementar Inicial no Topo ($z = 0$)</span>
                </div>
                <span class="step-tag">Estequiometria</span>
            </div>
            <div class="step-body">
                <div class="info-box">
                    <b>Parâmetro de Entrada:</b> Fertilizante comercial = <b>{{fert_name}}</b> com Dose Bruta = <b>{{gross_dose}} kg/ha</b><br/>
                    <b>Origem & Rastreabilidade:</b> {{etapa1_origem_html}}
                </div>
                <p>O simulador converte a dose bruta de adubo comercial na carga líquida elementar:</p>
                <div class="math-block">
                    $$M_{\text{{{nutr_sym}}}} = D_{\text{adubo}} \times \left( \frac{\text{Teor}_{\text{{{nutr_sym}}}}}{100} \right) = {{gross_dose}} \times \left( \frac{{{pct_gross}}}{100} \right) = \mathbf{{{elem_dose}}\text{ kg/ha de } {{nutr_sym}}}$$
                </div>
                <p>Convertendo para a densidade de massa da malha vertical ($1\text{ kg/ha} = 0,01\text{ mg/cm}^2$):</p>
                <div class="math-block">
                    $$M_{\text{{{nutr_sym}}}} = {{elem_dose}} \times 0,01 = \mathbf{{{elem_mg_cm2}}\text{ mg/cm}^2}$$
                </div>
            </div>
        </div>

        <!-- PASSO 2 -->
        <div class="step-card">
            <div class="step-header">
                <div class="step-title">
                    <span class="step-num">2</span>
                    <span>Parametrização Hidráulica e Capacidade de Campo</span>
                </div>
                <span class="step-tag">van Genuchten (1980)</span>
            </div>
            <div class="step-body">
                <div class="info-box">
                    <b>Parâmetro de Entrada:</b> Tipo de Solo selecionado = <b>{{soil_name}}</b><br/>
                    <b>Origem & Rastreabilidade Científica:</b> {{soil_cit}}
                </div>
                <p>A curva de retenção de água do solo selecionado é calculada por:</p>
                <div class="math-block">
                    $$\theta(h) = \theta_r + \frac{\theta_s - \theta_r}{\left[1 + |\alpha h|^n\right]^m}, \quad m = 1 - \frac{1}{{{n}}} = {{m}}$$
                </div>
                <p>Para a sucção de capacidade de campo ($h = -100\text{ cm}$):</p>
                <div class="math-block">
                    $$\theta_{\text{cc}} = {{theta_r}} + \frac{{{theta_diff}}}{{{denom_vg}}} = \mathbf{{{theta_cc}}\text{ cm}^3/\text{cm}^3}$$
                </div>
                <p>*(equivalente a {{theta_cc_pct}}% de umidade volumétrica na capacidade de campo)*</p>
            </div>
        </div>

        <!-- PASSO 3 -->
        <div class="step-card">
            <div class="step-header">
                <div class="step-title">
                    <span class="step-num">3</span>
                    <span>Infiltração da Chuva e Velocidade nos Poros</span>
                </div>
                <span class="step-tag">Richards 1D & Darcy</span>
            </div>
            <div class="step-body">
                <div class="info-box">
                    <b>Parâmetros de Entrada:</b> Lâmina de Chuva = <b>{{rain_mm}} mm</b> (ao longo de <b>{{total_days}} dias</b>) e Cultura = <b>{{crop_name}}</b><br/>
                    <b>Origem & Rastreabilidade Científica da Cultura:</b> {{crop_cit}}
                </div>
                <p>A movimentação da água obedece à Equação de Richards 1D. Sob a chuva de <b>{{rain_mm}} mm</b>, a velocidade média nos poros ($v$) durante a infiltração é:</p>
                <div class="math-block">
                    $$v = \frac{q}{\theta} = \frac{{{q_eff}}\text{ cm/dia}}{{{theta_active}}\text{ cm}^3/\text{cm}^3} \approx \mathbf{{{v_pore}}\text{ cm/dia}}$$
                </div>
            </div>
        </div>

        <!-- PASSO 4 -->
        <div class="step-card">
            <div class="step-header">
                <div class="step-title">
                    <span class="step-num">4</span>
                    <span>Adsorção Coloidal e Fator de Retardamento ($R$)</span>
                </div>
                <span class="step-tag">Isoterma STANMOD (Kd)</span>
            </div>
            <div class="step-body">
                <div class="info-box">
                    <b>Parâmetros de Entrada:</b> Nutriente avaliado = <b>{{nutr_name}} ({{nutr_sym}})</b> interagindo com o Solo = <b>{{soil_name}}</b><br/>
                    <b>Origem & Rastreabilidade Científica da Adsorção:</b> {{kd_cit}}
                </div>
                <p>A partição do nutriente entre a fase sólida e líquida do solo resulta no Fator de Retardamento:</p>
                <div class="math-block">
                    $$R = 1 + \frac{\rho_b \cdot K_d}{\theta} = 1 + \frac{{{rho_b}} \times {{kd}}}{{{theta_active}}} = \mathbf{{{R}}}$$
                </div>
                <p><b>Significado Físico:</b> {{r_interpretation}}</p>
            </div>
        </div>

        <!-- PASSO 5 -->
        <div class="step-card">
            <div class="step-header">
                <div class="step-title">
                    <span class="step-num">5</span>
                    <span>Transporte de Solutos (ADE) e Posição do Pico</span>
                </div>
                <span class="step-tag">Advecção-Dispersão</span>
            </div>
            <div class="step-body">
                <div class="info-box">
                    <b>Parâmetros de Entrada:</b> Nutriente = <b>{{nutr_name}}</b>, Solo = <b>{{soil_name}}</b>, Chuva = <b>{{rain_mm}} mm</b><br/>
                    <b>Origem & Rastreabilidade:</b> Transporte Advectivo-Dispersivo com freio coloidal ($R = {{R}}$) e dispersividade mecânica $\lambda = {{disp}}\text{ cm}$.
                </div>
                <p>A propagação da pluma é regida pela Equação de Advecção-Dispersão:</p>
                <div class="math-block">
                    $$R \frac{\partial C}{\partial t} = D \frac{\partial^2 C}{\partial z^2} - v \frac{\partial C}{\partial z}$$
                </div>
                <p>Dispersão calculada: $D = \lambda |v| + D_0 = {{disp}} \times {{v_pore}} + {{D0}} = \mathbf{{{D}}\text{ cm}^2/\text{dia}}$.</p>
                <p>Velocidade aparente do pico: $v_s = v / R = \mathbf{{{v_solute}}\text{ cm/dia}}$.</p>
                <p><b>Profundidade final do pico na simulação:</b> <b>$z_{\text{pico}} = {{peak_depth}}$</b>.</p>
            </div>
        </div>

        <!-- PASSO 6 -->
        <div class="step-card">
            <div class="step-header">
                <div class="step-title">
                    <span class="step-num">6</span>
                    <span>{{etapa6_html_title}}</span>
                </div>
                <span class="step-tag">Integração Numérica</span>
            </div>
            <div class="step-body">
                <div class="info-box">
                    {{etapa6_html_info}}
                    {{etapa6_html_origin}}
                </div>
                <p>Integrando as frações até a profundidade da raiz ($0 - {{root_depth}}\text{ cm}$) — mesmo balanço de cards, laudo e tabelas:</p>
                <div class="math-block">
                    $${{mass_lhs}} = \int_0^{{{root_depth}}\text{ cm}} \left[ \theta(z) C(z) + \rho_b K_d C(z) \right] dz = \mathbf{{{retained_kg_ha}}\text{ kg/ha}}$$
                </div>
                <p>*(representando {{retained_pct}}% do nutriente aplicado {{retido_local}})*</p>
                <div class="math-block">
                    $$M_{\text{abaixo ({{root_depth}}–{{profile_depth}} cm, no perfil)}} = \mathbf{{{below_kg_ha}}\text{ kg/ha}}$$
                </div>
                <p>*(representando {{below_pct}}% do nutriente aplicado presente abaixo da camada, ainda dentro do domínio)*</p>
                <div class="math-block">
                    $$M_{\text{fundo (atravessou {{profile_depth}} cm)}} = \mathbf{{{bottom_kg_ha}}\text{ kg/ha}}$$
                </div>
                <p>*(representando {{bottom_pct}}% do nutriente aplicado que efetivamente saiu do domínio pelo fundo)*</p>
            </div>
        </div>

        <!-- ESCOPO -->
        <div class="step-card">
            <div class="step-header">
                <div class="step-title">
                    <span class="step-num">•</span>
                    <span>Escopo e Limites da Simulação</span>
                </div>
                <span class="step-tag">Leitura correta</span>
            </div>
            <div class="step-body">
                <p><b>Espécies simuladas:</b> cada soluto representa uma espécie química fixa (N como NO₃⁻, K como K⁺, S como SO₄²⁻); o modelo <b>não simula transformações químicas</b> entre espécies.</p>
                <p><b>Kd de referência:</b> valores de literatura para a textura do solo, ajustáveis na tabela de nutrientes — <b>não calibrados experimentalmente</b> para este talhão.</p>
                <p><b>Absorção pela cultura:</b> proporcional à transpiração e à concentração dissolvida, <b>limitada pela demanda nutricional da cultura no ciclo</b>; representa o potencial de captura sob essa demanda, não uma previsão garantida.</p>
                <p><b>Uso recomendado:</b> comparação entre manejos/cenários, não previsão quantitativa garantida de absorção ou perda para a cultura.</p>
            </div>
        </div>

        <div class="nav-actions">
            <button class="btn" onclick="window.print()">Imprimir / Salvar em PDF</button>
            <button class="btn btn-primary" onclick="window.close();">Voltar para o Simulador</button>
        </div>
    </div>
</div>

</body>
</html>
"""
    md_content = md_template
    html_content = html_template
    for k, v in ctx.items():
        placeholder = "{{" + k + "}}"
        md_content = md_content.replace(placeholder, str(v))
        html_content = html_content.replace(placeholder, str(v))

    return md_content, html_content

def generate_step_by_step_markdown() -> str:
    """Wrapper para compatibilidade com os componentes Markdown do Gradio."""
    return generate_simulation_step_by_step()[0]

def generate_step_by_step_html() -> str:
    """Wrapper para compatibilidade com o endpoint /passo-a-passo."""
    return generate_simulation_step_by_step()[1]

def generate_unified_results_html() -> str:
    """Wrapper para compatibilidade com o endpoint /resultado unificado."""
    return generate_simulation_step_by_step()[1]
