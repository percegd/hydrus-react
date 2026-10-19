"""
Visualizer Module: Generates clean, high-resolution agronomic graphs of Nutrients and Soil Water profiles.
Supports any nutrient (N, K, Ca, Mg, S, P) and both Planning and Diagnostic modes.
"""

import matplotlib
matplotlib.use("Agg")  # Headless backend for web
import matplotlib.pyplot as plt
import numpy as np
from hydrus_core.hydrus_solver import SimulationResults
from hydrus_core.crop import CropParameters
from hydrus_core.soil_physics import SoilParameters, water_content_from_h


def _truncate(text: str, max_len: int) -> str:
    """Truncates a string to max_len characters, adding '…' if needed."""
    return text if len(text) <= max_len else text[:max_len - 1] + "…"


def plot_water_profile(
    results: SimulationResults,
    output_path: str = "water_profile.png",
    title: str = "Solo 1D — Perfil de Umidade do Solo (Somente Água)",
    soil: SoilParameters = None,
    root_depth_cm: float = None,
    crop=None,
) -> str:
    """Perfil final de umidade θ(z) para o modo "somente água" (sem solutos).

    Mostra o perfil inicial (condição de contorno do ensaio) e o perfil final,
    com a profundidade no eixo vertical (0 cm no topo), no mesmo estilo do perfil
    de nutrientes do HYDRUS-1D. Quando ``soil`` é informado, o eixo de umidade é
    escalado para o intervalo efetivo do perfil (θr … θcc) e são marcadas as
    referências de umidade residual e de capacidade de campo — evitando que a
    curva apareça como uma linha vertical achatada.
    """
    z = np.asarray(results.z, dtype=float)
    if len(getattr(results, "theta_profiles", []) or []) == 0:
        return None

    final_theta = np.asarray(results.theta_profiles[-1], dtype=float)
    init_theta = np.asarray(results.theta_profiles[0], dtype=float)

    fig, ax = plt.subplots(1, 1, figsize=(6.8, 7.2), dpi=150)
    ax.plot(init_theta, z, color="#9e9e9e", lw=2.0, ls="--", label="Inicial")
    ax.plot(final_theta, z, color="#1f77b4", lw=2.4, label="Final")

    # Escala do eixo de umidade baseada no intervalo efetivo do perfil.
    vals = np.concatenate([init_theta, final_theta])
    lo = float(np.min(vals))
    hi = float(np.max(vals))

    th_cc = None
    if soil is not None:
        lo = min(lo, float(soil.theta_r))
        try:
            th_cc = float(water_content_from_h(np.array([-100.0]), soil)[0])
            hi = max(hi, th_cc)
        except Exception:
            th_cc = None

    span = max(0.06, hi - lo)
    ax.set_xlim(max(0.0, lo - 0.12 * span), hi + 0.12 * span)

    # Referências agronômicas de umidade.
    if soil is not None:
        ax.axvline(float(soil.theta_r), color="#8d6e63", ls=":", lw=1.4,
                   label=f"θr = {float(soil.theta_r):.3f}")
        if th_cc is not None:
            ax.axvline(th_cc, color="#2e7d32", ls="-.", lw=1.4,
                       label=f"θcc = {th_cc:.3f}")

    # Zona radicular (quando há cultura).
    has_crop_w = crop is not None
    if has_crop_w and root_depth_cm and 0 < float(root_depth_cm) < float(np.max(z)):
        rd = float(root_depth_cm)
        ax.axhspan(0, rd, color="#2ca02c", alpha=0.08)
        ax.axhline(rd, color="#2ca02c", ls="--", lw=1.5, label=f"Zona radicular ({rd:.0f} cm)")

    ax.set_ylim(float(np.max(z)), 0.0)
    ax.set_xlabel("Umidade Volumétrica θ [cm³/cm³]", fontsize=10)
    ax.set_ylabel("Profundidade [cm]", fontsize=10)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="lower right", fontsize=9)

    q_bottom_mm = float(getattr(results, "q_bottom_cm", 0.0) or getattr(results, "q_bottom_cum_cm", 0.0)) * 10.0
    runoff_mm = float(getattr(results, "runoff_cum_cm", 0.0) or 0.0) * 10.0
    ax.text(
        0.02, 0.02,
        f"Drenagem no fundo: {q_bottom_mm:.1f} mm\nEscoamento superficial: {runoff_mm:.1f} mm",
        transform=ax.transAxes, fontsize=8.5, va="bottom", ha="left",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="white", edgecolor="#cccccc", alpha=0.9)
    )

    fig.suptitle(title, fontsize=11, fontweight="bold", color="#2e7d32", y=0.98)
    plt.tight_layout(rect=(0.01, 0.01, 0.99, 0.95))
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white", edgecolor="none")
    plt.close(fig)
    return output_path


def plot_nutrient_profile(
    results: SimulationResults,
    soil: SoilParameters,
    crop: CropParameters = None,
    rain_mm: float = 0.0,
    fertilizer_kg_ha: float = 0.0,
    nutrient_symbol: str = "N",
    nutrient_name: str = "Nitrogênio",
    mode: str = "planejamento",
    output_path: str = "nutrient_profile.png",
    release_type: str = "immediate",
    release_days: float = 60.0,
    target_depth_cm: float = None,
    solute_filter: str = None,
    include_moisture: bool = True,
    banner: bool = True,
    x_max: float = None,
) -> str:
    """
    Plots the final depth profile of any Nutrient and Soil Moisture with agronomic annotations.
    Supports single nutrient and multi-nutrient simultaneous curves (N, K, Ca, Mg, S, P).

    Com N solutos: por padrao gera o grafico COMBINADO (todas as curvas). Com
    ``solute_filter`` gera o grafico POR SOLUTO (so a curva do soluto pedido).
    Com ``include_moisture=False`` omite o painel de umidade (usado na galeria
    por-soluto, para a frente de umidade aparecer uma única vez, no combinado).
    Com ``banner=False`` omite o selo superior (galeria por-soluto).
    """
    if include_moisture:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 7.2), sharey=True, dpi=150)
    else:
        fig, ax1 = plt.subplots(1, 1, figsize=(6.2, 7.2), dpi=150)
        ax2 = None

    z = results.z
    dz = z[1] - z[0] if len(z) > 1 else 1.0
    if crop is not None:
        root_depth = float(crop.root_depth_cm)
    elif target_depth_cm is not None:
        root_depth = float(target_depth_cm)
    else:
        root_depth = float(getattr(results, "target_depth_cm", 30.0) or 30.0)

    final_theta = results.theta_profiles[-1]
    init_theta = results.theta_profiles[0]

    # Invert Y axis: 0 cm is soil surface at top
    ax1.set_ylim(max(z), 0)
    if ax2 is not None:
        ax2.set_ylim(max(z), 0)

    # ------------------ GRÁFICO 1: PERFIL DO(S) NUTRIENTE(S) ------------------
    nutrient_colors = {
        "N": "#d95f02",   # Laranja terracota
        "K": "#7570b3",   # Violeta / Púrpura
        "Ca": "#1b9e77",  # Turquesa florestal
        "Mg": "#e7298a",  # Magenta / Rosa escuro
        "S": "#e6ab02",   # Âmbar dourado
        "P": "#66a61e"    # Verde oliva
    }

    # Zonas agronômicas de fundo (comum para todos os nutrientes)
    lbl_eval = "Zona Radicular" if crop else "Camada Avaliada"
    lbl_deep = "Zona de Perda (Subsolo)" if crop else "Deslocamento Profundo"
    ax1.axhspan(0, root_depth, color="#2ca02c", alpha=0.12, label=lbl_eval)
    ax1.axhspan(root_depth, max(z), color="#d62728", alpha=0.06, label=lbl_deep)
    ax1.axhline(root_depth, color="#2ca02c", linestyle="--", lw=1.8)

    is_multi = hasattr(results, "nutrient_results") and len(results.nutrient_results) > 1
    if solute_filter and getattr(results, "nutrient_results", None) and solute_filter in results.nutrient_results:
        is_multi = False
        nutrient_symbol = solute_filter
        nutrient_name = results.nutrient_results[solute_filter].get("name", solute_filter)

    if is_multi:
        # Plot de múltiplos nutrientes simultâneos
        for sym, n_data in results.nutrient_results.items():
            color_nutr = nutrient_colors.get(sym, "#388e3c")
            c_prof = n_data["final_profile"]
            lbl = f"{n_data['name']} ({sym})"
            ax1.plot(c_prof, z, color=color_nutr, lw=2.4, label=lbl)
            ax1.fill_betweenx(z, 0, c_prof, color=color_nutr, alpha=0.18)

        ax1.set_title("Dinâmica Multi-Nutriente no Perfil", fontsize=11, fontweight='bold', pad=8)
        ax1.set_xlabel("Teor TOTAL no Solo [mg elemento / cm³] (dissolvido+adsorvido)", fontsize=9)
    else:
        _per = (getattr(results, "nutrient_results", {}) or {}).get(nutrient_symbol, {})
        if _per and _per.get("final_profile") is not None:
            final_n = np.asarray(_per["final_profile"], dtype=float)
            peak_z = float(_per.get("peak_depth_cm", getattr(results, "peak_depth_cm", 0.0)))
        else:
            final_n = results.n_profiles[-1]
            peak_z = results.peak_depth_cm
        color_nutr = nutrient_colors.get(nutrient_symbol, "#d95f02")

        ax1.plot(final_n, z, color=color_nutr, lw=2.6, label=f"{nutrient_name} ({nutrient_symbol})")
        ax1.fill_betweenx(z, 0, final_n, color=color_nutr, alpha=0.35)

        ax1.set_title(f"Dinâmica de {nutrient_name} ({nutrient_symbol})", fontsize=11, fontweight='bold', pad=8)
        if nutrient_symbol == "P":
            ax1.set_xlabel(f"P TOTAL no Solo [mg P / cm³] (dissolvido+adsorvido)", fontsize=9)
        else:
            ax1.set_xlabel(f"Teor no Solo [mg {nutrient_symbol} / cm³]", fontsize=10)

    ax1.set_ylabel("Profundidade do Solo [cm]", fontsize=10)
    ax1.grid(True, linestyle=":", alpha=0.6)
    ax1.legend(loc="lower right", fontsize=8.2, framealpha=0.9)
    if x_max is not None and x_max > 0:
        # Escala X comum (maior pico entre solutos): proporcao comparavel na galeria.
        ax1.set_xlim(0.0, float(x_max))

    # ------------------ GRÁFICO 2: UMIDADE DO SOLO (só se include_moisture) ------------------
    if ax2 is not None:
        ax2.plot(init_theta * 100, z, color="#7f7f7f", linestyle=":", lw=1.8, label="Umidade Inicial")
        ax2.plot(final_theta * 100, z, color="#1f77b4", lw=2.5, label="Umidade Atual")
        ax2.fill_betweenx(z, init_theta * 100, final_theta * 100, color="#1f77b4", alpha=0.25)

        # Linha da raiz também no gráfico 2
        ax2.axhline(root_depth, color="#2ca02c", linestyle="--", lw=1.8)
        ax2.axhspan(0, root_depth, color="#2ca02c", alpha=0.12)

        ax2.set_title("Frente de Umidade da Água", fontsize=11, fontweight='bold', pad=8)
        ax2.set_xlabel("Umidade Volumétrica [%]", fontsize=10)
        ax2.grid(True, linestyle=":", alpha=0.6)
        ax2.legend(loc="lower right", fontsize=8.5)

    # ------------------ BANNER SUPERIOR (suptitle neutro, sem classificação) ------------------
    if banner:
        soil_short = _truncate(soil.name, 40)
        crop_short = _truncate(crop.name, 28) if crop else "Ensaio em Coluna de Solo"

        if solute_filter:
            nutr_header = f"Soluto {nutrient_symbol} (vista por soluto)"
        else:
            nutr_header = "Multi-Nutriente" if is_multi else f"Dose: {fertilizer_kg_ha:,.0f} kg/ha {nutrient_symbol}"

        fig.suptitle(
            f"Solo 1D — {crop_short}  |  {soil_short}\n"
            f"{nutr_header}  |  Chuva/Irrigação: {rain_mm:.0f} mm",
            fontsize=10,
            fontweight='bold',
            color="#2e7d32",
            y=0.98
        )
        plt.tight_layout(rect=(0.01, 0.01, 0.99, 0.95))
    else:
        plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white", edgecolor="none")
    plt.close(fig)
    return output_path


# Backward compatibility alias
def plot_nitrogen_profile(
    results: SimulationResults,
    soil: SoilParameters,
    crop: CropParameters,
    rain_mm: float,
    fertilizer_kg_ha: float,
    output_path: str = "nitrogen_profile.png",
    **kwargs
) -> str:
    return plot_nutrient_profile(
        results=results,
        soil=soil,
        crop=crop,
        rain_mm=rain_mm,
        fertilizer_kg_ha=fertilizer_kg_ha,
        nutrient_symbol="N",
        nutrient_name="Nitrogênio",
        mode=kwargs.get("mode", "planejamento"),
        output_path=output_path
    )


def _solute_symbols_from_obs(results, nutrient_symbol: str) -> list:
    """Solutos disponíveis nas séries de observação (padrão HYDRUS: um por soluto)."""
    obs_c = getattr(results, "obs_c_series", {}) or {}
    syms = [s for s, series in obs_c.items() if series]
    if not syms:
        return [nutrient_symbol]
    if nutrient_symbol in syms:
        syms.remove(nutrient_symbol)
        syms.insert(0, nutrient_symbol)
    return syms


def plot_breakthrough_curves(
    results: SimulationResults,
    nutrient_symbol: str = "N",
    output_path: str = "breakthrough_curves.png",
    focus_symbol: str = None,
    crop=None,
    include_moisture: bool = True,
    only_moisture: bool = False,
):
    """
    Gera o gráfico clássico do HYDRUS-1D de curvas de avanço (Breakthrough Curves - BTC):
    - Um painel de concentração C(t) [mg/L] por soluto, com uma curva por nó de observação.
    - Um painel final com a evolução da umidade volumétrica θ(t) [cm³/cm³] nos mesmos nós.

    Com N solutos (padrão HYDRUS-1D), são gerados N conjuntos de curvas — um por soluto.
    Com ``focus_symbol`` gera só o painel do soluto pedido (vista por soluto).
    """
    times = getattr(results, "obs_times_days", [])
    if not times or len(times) < 2:
        return None

    depths = getattr(results, "obs_depths_cm", [])
    if not depths:
        return None

    obs_c = getattr(results, "obs_c_series", {})
    obs_theta = getattr(results, "obs_theta_series", {})
    symbols = _solute_symbols_from_obs(results, nutrient_symbol)
    if focus_symbol and focus_symbol in symbols:
        symbols = [focus_symbol]

    # Paleta de alto contraste, daltonismo-amigável (Okabe-Ito expandida)
    palette = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9", "#8c564b", "#333333"]
    # Estilos de linha variados por profundidade para desambiguação visual imediata
    linestyles = ["-", "--", "-.", ":", (0, (3, 1, 1, 1)), (0, (5, 2))]

    z_max = float(np.max(getattr(results, "z", [100.0])))

    def _depth_label(d):
        _has_crop_btc = crop is not None
        if d <= 15:
            return f"z = {d:.0f} cm (superfície)"
        elif d <= 35:
            return f"z = {d:.0f} cm (rizosfera)" if _has_crop_btc else f"z = {d:.0f} cm (subsuperfície)"
        elif d >= z_max - 5:
            return f"z = {d:.0f} cm (fundo)"
        else:
            return f"z = {d:.0f} cm (subsolo)"

    def _draw_theta(ax):
        for idx, d in enumerate(depths):
            th_vals = obs_theta.get(d, [])
            if len(th_vals) == len(times):
                ax.plot(
                    times, th_vals,
                    color=palette[idx % len(palette)],
                    linestyle=linestyles[idx % len(linestyles)],
                    lw=1.8,
                    alpha=0.92,
                    label=_depth_label(d)
                )
        ax.set_title("Evolução da Umidade no Tempo θ(t)", fontsize=11, fontweight="bold", pad=8)
        ax.set_xlabel("Tempo Decorrido [dias]", fontsize=10)
        ax.set_ylabel("Umidade Volumétrica θ [cm³/cm³]", fontsize=10)
        ax.grid(True, linestyle=":", alpha=0.5)
        ncol = 2 if len(depths) >= 4 else 1
        ax.legend(loc="lower right", fontsize=8.5, framealpha=0.92, facecolor="#ffffff", edgecolor="#cbd5e1", ncol=ncol)

    # Modo "somente água" ou exportação isolada da curva de umidade θ(t):
    if only_moisture or not obs_c or not symbols:
        if not obs_theta:
            return None
        fig, ax = plt.subplots(1, 1, figsize=(8.5, 5.8), dpi=150)
        _draw_theta(ax)
        fig.suptitle(
            "Solo 1D — Umidade nos Nós de Observação θ(t)",
            fontsize=11, fontweight="bold", color="#2e7d32", y=0.98
        )
        plt.tight_layout(rect=(0.01, 0.01, 0.99, 0.95))
        plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white", edgecolor="none")
        plt.close(fig)
        return output_path

    def _draw_solute(ax, sym):
        c_series_dict = obs_c.get(sym, {})
        for idx, d in enumerate(depths):
            c_vals = c_series_dict.get(d, [])
            if len(c_vals) == len(times):
                ax.plot(
                    times, c_vals,
                    color=palette[idx % len(palette)],
                    linestyle=linestyles[idx % len(linestyles)],
                    lw=1.8,
                    alpha=0.92,
                    label=_depth_label(d)
                )
        ax.set_title(f"Avanço do Soluto ({sym}) no Tempo C(t)", fontsize=11, fontweight="bold", pad=8)
        ax.set_xlabel("Tempo Decorrido [dias]", fontsize=10)
        ax.set_ylabel("Concentração na Fase Líquida [mg/L]", fontsize=10)
        ax.grid(True, linestyle=":", alpha=0.5)
        ncol = 2 if len(depths) >= 4 else 1
        ax.legend(loc="upper right", fontsize=8.5, framealpha=0.92, facecolor="#ffffff", edgecolor="#cbd5e1", ncol=ncol)

    n = len(symbols)
    if n == 1 and not include_moisture:
        fig, ax1 = plt.subplots(1, 1, figsize=(8.5, 5.8), dpi=150)
        _draw_solute(ax1, symbols[0])
    elif n == 1:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.2, 5.8), dpi=150)
        _draw_solute(ax1, symbols[0])
        _draw_theta(ax2)
    else:
        ncols = 2
        nrows = -(-(n + 1) // ncols)  # N painéis C(t) + 1 painel θ(t)
        fig, axes = plt.subplots(nrows, ncols, figsize=(13.2, 3.8 * nrows + 1.0), dpi=150, squeeze=False)
        flat = [axes[r][c] for r in range(nrows) for c in range(ncols)]
        for i, sym in enumerate(symbols):
            _draw_solute(flat[i], sym)
        _draw_theta(flat[n])
        for ax in flat[n + 1:]:
            ax.set_visible(False)

    fig.suptitle(
        "Séries Temporais nos Nós de Observação",
        fontsize=12,
        fontweight="bold",
        color="#2e7d32",
        y=0.98
    )
    plt.tight_layout(rect=(0.01, 0.01, 0.99, 0.95))
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white", edgecolor="none")
    plt.close(fig)
    return output_path


def plot_profiles_at_days(
    results: SimulationResults,
    soil: SoilParameters,
    nutrient_symbol: str = "K",
    nutrient_name: str = "Potássio",
    output_path: str = "perfis_dias.png",
    focus_symbol: str = None,
    include_moisture: bool = True,
    only_moisture: bool = False,
) -> str:
    """Perfis de concentração (C(z)) e umidade (θ(z)) nos dias de leitura (print times).

    Com N solutos (padrão HYDRUS-1D) gera um painel C(z) por soluto — cada um com o seu
    Kd — e um painel compartilhado de umidade θ(z). Com ``focus_symbol`` gera só o
    painel do soluto pedido (vista por soluto).
    """
    profs = getattr(results, "print_profiles", None) or {}
    days = sorted(profs.keys())
    z = np.asarray(results.z, dtype=float)
    rho = float(getattr(soil, "bulk_density", 1.3))
    nutr_results = getattr(results, "nutrient_results", None) or {}

    symbols = list(nutr_results.keys())
    if not symbols:
        for d in days:
            symbols = list((profs[d].get("c_total") or {}).keys())
            if symbols:
                break
    if not symbols:
        symbols = [nutrient_symbol]
    if nutrient_symbol in symbols:
        symbols.remove(nutrient_symbol)
        symbols.insert(0, nutrient_symbol)
    if focus_symbol and focus_symbol in symbols:
        symbols = [focus_symbol]

    cmap = plt.get_cmap("viridis")
    n_days = max(1, len(days))

    def _kd_for(sym):
        _nr_map = getattr(results, "nutrient_results", None) or {}
        _kd_nom = float((_nr_map.get(sym) or {}).get("kd", 0.0))
        try:
            _ke_raw = (_nr_map.get(sym) or {}).get("kd_eff", _kd_nom)
            import numpy as _npk
            if _ke_raw is None:
                return _kd_nom
            elif hasattr(_ke_raw, "__len__") and not isinstance(_ke_raw, (float, int)):
                return float(_npk.mean(_npk.asarray(_ke_raw, dtype=float)))
            else:
                return float(_ke_raw) if str(_ke_raw) != "" else _kd_nom
        except Exception:
            return _kd_nom

    # Eixo X comum: maior concentração entre todos os solutos/dias (mesma escala).
    _xmax_all = 0.0
    for _sym in symbols:
        _kd_g = _kd_for(_sym)
        for _d in days:
            try:
                _prof = profs[_d]
                _theta = np.asarray(_prof.get("theta"), dtype=float)
                _ct = (_prof.get("c_total") or {}).get(_sym)
                if _ct is not None and _theta is not None and len(_theta) == len(z):
                    _rc = np.maximum(_theta + rho * max(0.0, _kd_g), 1e-6)
                    _vmax = float(np.max(np.asarray(_ct, dtype=float) / _rc * 1000.0))
                    if _vmax > _xmax_all:
                        _xmax_all = _vmax
            except Exception:
                continue
    if not (_xmax_all > 0):
        _xmax_all = 0.0

    def _draw_theta(ax):
        for i, d in enumerate(days):
            theta = np.asarray(profs[d].get("theta"), dtype=float)
            if theta is not None and len(theta) == len(z):
                ax.plot(theta, z, color=cmap(i / max(1, n_days - 1)), lw=2.2, label=f"{d:.0f} d")
        ax.set_xlabel("θ [cm³/cm³]", fontsize=10)
        ax.set_title("Perfil de Umidade", fontsize=11, fontweight="bold")
        ax.grid(True, linestyle=":", alpha=0.5)
        if days:
            _th_all = np.concatenate([
                np.asarray(profs[d].get("theta"), dtype=float)
                for d in days if profs[d].get("theta") is not None
            ])
            if _th_all.size:
                _lo = float(np.min(_th_all)); _hi = float(np.max(_th_all))
                _span = max(0.06, _hi - _lo)
                ax.set_xlim(max(0.0, _lo - 0.12 * _span), _hi + 0.12 * _span)
            ax.legend(title="Dias de leitura", fontsize=8.5)

    def _draw_solute(ax, sym, show_ylabel):
        kd = _kd_for(sym)
        name = ((getattr(results, "nutrient_results", None) or {}).get(sym) or {}).get("name", sym)
        for i, d in enumerate(days):
            prof = profs[d]
            theta = np.asarray(prof.get("theta"), dtype=float)
            c_total = (prof.get("c_total") or {}).get(sym)
            if c_total is not None and theta is not None and len(theta) == len(z):
                ret_cap = np.maximum(theta + rho * max(0.0, kd), 1e-6)
                c_aq_mg_l = np.asarray(c_total, dtype=float) / ret_cap * 1000.0  # mg/L na solução
                ax.plot(c_aq_mg_l, z, color=cmap(i / max(1, n_days - 1)), lw=2.2, label=f"{d:.0f} d")
        ax.set_xlabel(f"{name} ({sym}) na solução [mg/L]", fontsize=10)
        ax.set_title(f"Perfil de Concentração — {name} ({sym})", fontsize=11, fontweight="bold")
        ax.grid(True, linestyle=":", alpha=0.5)
        ax.set_ylim(float(np.max(z)), 0.0)
        if _xmax_all > 0:
            ax.set_xlim(0.0, float(_xmax_all))
        if show_ylabel:
            ax.set_ylabel("Profundidade [cm]", fontsize=10)
        if days:
            ax.legend(title="Dias de leitura", fontsize=8.5)

    n = len(symbols)
    if only_moisture or not nutr_results:
        # Modo "somente água" ou exportação isolada do painel de umidade θ(z) nos print times.
        fig, ax1 = plt.subplots(1, 1, figsize=(7.2, 7.2), dpi=150)
        _draw_theta(ax1)
        ax1.set_ylim(float(np.max(z)), 0.0)
        ax1.set_ylabel("Profundidade [cm]", fontsize=10)
    elif n == 1 and not include_moisture:
        fig, ax1 = plt.subplots(1, 1, figsize=(7.2, 7.2), dpi=150)
        _draw_solute(ax1, symbols[0], True)
    elif n == 1:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.0, 7.2), sharey=True, dpi=150)
        _draw_solute(ax1, symbols[0], True)
        _draw_theta(ax2)
    else:
        ncols = 2
        nrows = -(-(n + 1) // ncols)  # N painéis C(z) + 1 painel θ(z)
        fig, axes = plt.subplots(nrows, ncols, figsize=(12.0, 4.6 * nrows + 1.0), sharey=True, dpi=150, squeeze=False)
        flat = [axes[r][c] for r in range(nrows) for c in range(ncols)]
        for i, sym in enumerate(symbols):
            _draw_solute(flat[i], sym, i % ncols == 0)
        _draw_theta(flat[n])
        for ax in flat[n + 1:]:
            ax.set_visible(False)

    fig.suptitle(
        "Solo 1D — Evolução Temporal do Perfil (Snapshots nos Dias de Leitura)",
        fontsize=12,
        fontweight="bold",
        color="#2e7d32",
        y=0.98
    )
    plt.tight_layout(rect=(0.01, 0.01, 0.99, 0.95))
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white", edgecolor="none")
    plt.close(fig)
    return output_path


