"""Laudo do modo "Somente água" — texto portado de /workspace/hydrus/app_gradio.py.

O Gradio gera o laudo water-only inline (sem transporte de solutos): coluna em
run_wizard_simulation (ramo is_column) e série em run_wizard_simulation (ramo
else). Apenas lógica de apresentação; nenhuma física é alterada aqui.
"""

from __future__ import annotations


def column_water_only_report(
    *,
    soil,
    crop,
    col_depth: float,
    rain_mm: float,
    total_days: float,
    initial_moisture_pct: float,
    evap_mm_day: float,
    transp_mm_day: float,
    drainage_mm: float,
    runoff_mm: float,
    storage_mm: float,
    obs_depths_cm,
) -> str:
    """Ramo coluna do laudo só-água do Gradio (Balanço Hídrico no domínio)."""
    e_cm = float(evap_mm_day) / 10.0
    t_cm = float(transp_mm_day) / 10.0
    t_days = float(total_days)
    if crop is not None:
        transp_line = (
            f"* **Transpiração da cultura (T):** {t_cm * 10:.2f} mm/dia — {crop.name} "
            f"(raiz fixa em {float(crop.root_depth_cm):.0f} cm; Feddes h1..h4 = "
            f"{float(crop.h1):.0f}, {float(crop.h2):.0f}, {float(crop.h3):.0f}, {float(crop.h4):.0f} cm)\n"
        )
    else:
        transp_line = "* **Transpiração da cultura (T):** 0 mm/dia (perfil nu, sem cultura)\n"
    return (
        "### Laudo Técnico — Fluxo de Água no Perfil do Solo (Somente Água)\n"
        "**Modo:** sem transporte de solutos — apenas a equação de Richards acoplada à "
        "evaporação do solo e, se houver cultura, à absorção radicular.\n\n"
        "#### 1. Geometria e Solo\n"
        f"* **Profundidade do Perfil Simulado:** **{float(col_depth):.0f} cm**\n"
        f"* **Solo:** {soil.name} (θr = {float(soil.theta_r):.3f} cm³/cm³, θs = {float(soil.theta_s):.3f} cm³/cm³, "
        f"α = {float(soil.alpha):.4f} 1/cm, n = {float(soil.n):.3f}, Ks = {float(soil.ks):.1f} cm/dia, "
        f"ρb = {float(soil.bulk_density):.2f} g/cm³)\n\n"
        "#### 2. Condições do Ensaio\n"
        f"* **Lâmina de Chuva/Irrigação:** **{float(rain_mm):.0f} mm** ao longo de **{t_days:.0f} dias**\n"
        f"* **Umidade Prévia do Solo:** {float(initial_moisture_pct):.0f}% da capacidade de campo\n"
        f"* **Evaporação do solo (E):** {e_cm * 10:.2f} mm/dia\n"
        f"{transp_line}\n"
        "#### 3. Balanço Hídrico (domínio completo, 0 a "
        f"{float(col_depth):.0f} cm)\n"
        f"* **Entrada (chuva/irrigação):** {float(rain_mm):.1f} mm\n"
        f"* **Drenagem no fundo do perfil:** {float(drainage_mm):.1f} mm\n"
        f"* **Escoamento superficial:** {float(runoff_mm):.1f} mm\n"
        f"* **Δ Armazenamento no perfil (θfinal − θinicial):** {float(storage_mm):+.1f} mm\n"
        f"* **Evaporação acumulada (E):** {e_cm * 10.0 * t_days:.1f} mm ({e_cm * 10.0:.2f} mm/dia)\n"
        f"* **Transpiração acumulada (T):** {t_cm * 10.0 * t_days:.1f} mm ({t_cm * 10.0:.2f} mm/dia)\n"
        f"* **Nós de Observação:** {', '.join(f'{float(d):.0f}' for d in (obs_depths_cm or []))} cm\n"
    )


def seasonal_water_only_report(
    *,
    soil,
    crop,
    prof_depth: float,
    total_rain: float,
    n_win: int,
    win_txt: str,
    source_label: str,
    drainage_mm: float,
    runoff_mm: float,
    storage_mm: float,
    obs_depths_cm,
) -> str:
    """Ramo série do laudo só-água do Gradio (Fluxo de Água / janela)."""
    crop_txt = (
        f"{crop.name} (kc={float(crop.kc):.2f}, raiz {float(crop.root_depth_cm):.0f} cm)"
        if crop is not None
        else "Perfil de solo nu (sem cultura)"
    )
    return (
        "### Laudo de Simulação — Fluxo de Água (Somente Água)\n"
        "**Modo:** sem transporte de solutos — apenas a equação de Richards com evaporação do solo\n"
        "e, se houver cultura, absorção radicular (Feddes).\n\n"
        "#### 1. Cenário Hídrico\n"
        f"* **Fonte da série:** {source_label}\n"
        f"* **Precipitação no período:** **{float(total_rain):.1f} mm** em **{int(n_win)} dias (janela {win_txt})**\n"
        f"* **Solo:** {soil.name} (θr = {float(soil.theta_r):.3f}, θs = {float(soil.theta_s):.3f}, "
        f"α = {float(soil.alpha):.4f} 1/cm, n = {float(soil.n):.3f}, Ks = {float(soil.ks):.1f} cm/dia)\n"
        f"* **Cultura:** {crop_txt}\n"
        f"* **Domínio do perfil:** **0 a {float(prof_depth):.0f} cm**\n\n"
        "#### 2. Balanço Hídrico do Período\n"
        f"* **Entrada (precipitação):** **{float(total_rain):.1f} mm**\n"
        f"* **Drenagem profunda acumulada:** **{float(drainage_mm):.1f} mm**\n"
        f"* **Escoamento superficial:** **{float(runoff_mm):.1f} mm**\n"
        f"* **Δ Armazenamento no perfil (θfinal−θinicial):** **{float(storage_mm):+.1f} mm**\n"
        f"* **Nós de observação:** {', '.join(f'{float(d):.0f}' for d in (obs_depths_cm or []))} cm\n"
    ).strip()
