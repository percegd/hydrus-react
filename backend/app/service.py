"""Camada de serviço: traduz request HTTP -> hydrus-core -> resposta.

Regras de domínio (as mesmas do app legado):
- camada avaliada = raiz da cultura, ou perfil todo sem cultura;
- balanço em 3 vias: retido 0–raiz / abaixo no perfil / fundo (+ absorvido).
"""

import base64
import math
import os
import tempfile

import matplotlib

matplotlib.use("Agg")

from hydrus_core.crop import CROP_DATABASE
from hydrus_core.hydrus_solver import Hydrus1DSimulator, SimulationConfig
from hydrus_core.soil_physics import SOIL_DATABASE
from hydrus_core.visualizer import plot_nutrient_profile

from .schemas import SimulateRequest, SimulateResponse, SoluteBalance, WaterBalance
from .water_report import (
    seasonal_water_only_report,
    column_water_only_report,
)


def _peak_or_none(value) -> float | None:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) else v


def _is_seasonal(req: SimulateRequest) -> bool:
    """Modo sazonal como no Gradio: série diária (qualquer duração).

    Gradio: is_column = "Lâmina"/"evento único" em water_source; série ou
    upload (qualquer duração) segue o ramo sazonal (janela + relatório anual).
    """
    return bool(req.rain_series)


def _default_print_days(total_days: float, seasonal: bool = False) -> list[float]:
    """Marcos de leitura padrão, iguais aos do Gradio (app_gradio.py).

    - Sazonal longo (>= 180 dias): frações (0.15, 0.35, 0.65, 1.0)
      (em 365 dias = 55, 128, 237, 365, o default da UI do Gradio);
    - Coluna ou sazonal curto: frações (0.25, 0.5, 0.75, 1.0).
    """
    try:
        td = float(total_days)
    except (TypeError, ValueError):
        td = 0.0
    if td <= 0:
        return []
    fracs = (0.15, 0.35, 0.65, 1.0) if (seasonal and td >= 180) else (0.25, 0.5, 0.75, 1.0)
    days = sorted({max(1.0, round(td * f)) for f in fracs})
    return [float(d) for d in days if 0.0 < float(d) <= td + 1e-9]


def _default_obs_depths(depth_cm: float, seasonal: bool) -> list[float] | None:
    """Nós de observação padrão do modo sazonal do Gradio.

    Gradio (série diária) usa [20, 50, 100, prof] quando o usuário não
    informa nada; no modo coluna deixa o default do solver.
    """
    if seasonal:
        try:
            prof = float(depth_cm)
        except (TypeError, ValueError):
            return None
        return sorted({d for d in (20.0, 50.0, 100.0, prof) if 0.0 <= d <= prof})
    return None


def _storage_mm(results) -> float:
    """Δ armazenamento no perfil (θfinal − θinicial), como no Gradio."""
    try:
        import numpy as _np

        z = _np.asarray(getattr(results, "z", []), dtype=float)
        if z.size < 2:
            return 0.0
        d_z = float(z[1] - z[0])
        th = getattr(results, "theta_profiles", []) or []
        if len(th) < 2:
            return 0.0
        return float(_np.sum(_np.asarray(th[-1], dtype=float) - _np.asarray(th[0], dtype=float)) * d_z) * 10.0
    except Exception:
        return 0.0


def _effective_window(req: SimulateRequest, series_len: int) -> tuple[int, int]:
    """Janela de análise [sw, ew] com o clamp do Gradio (dias do ano, 1-based).

    Fora da série (lâmina), a janela é ignorada (validate_analysis_window).
    """
    try:
        sw = int(float(req.analysis_start_day or 1))
    except (TypeError, ValueError):
        sw = 1
    try:
        ew = int(float(req.analysis_end_day or 365))
    except (TypeError, ValueError):
        ew = 365
    sw = max(1, min(sw, max(series_len, 1)))
    ew = max(sw, min(ew, max(series_len, 1)))
    return sw, ew


def _effective_print_days(req: SimulateRequest, total_days: float, sw: int, ew: int) -> list[float]:
    """Dias de leitura (dias de ensaio) como no Gradio.

    - Série: dias de calendário convertidos (d − sw + 1); ausente = marcos
      por frações da duração (em 365 dias = 55, 128, 237, 365).
    - Lâmina: dias de ensaio diretos; ausente = marcos por frações.
    """
    if req.print_days is not None:
        if req.rain_series:
            conv = sorted({int(round(float(d))) - sw + 1 for d in (req.print_days or [])})
            return [float(d) for d in conv if 1 <= d <= int(float(total_days))]
        return [float(d) for d in (req.print_days or [])]
    return _default_print_days(total_days, _is_seasonal(req))


def _run_core(req: SimulateRequest):
    """Executa o solver uma vez; retorna (results, soil, crop, root_depth, total_rain, total_days)."""
    soil = SOIL_DATABASE[req.soil_key]
    crop = CROP_DATABASE.get(req.crop_key) if req.crop_key else None
    root_depth = float(crop.root_depth_cm) if crop else float(req.depth_cm)
    if req.root_depth_cm and crop:
        root_depth = float(req.root_depth_cm)
    water_only = bool(req.water_only)

    _pmode = (req.placement.mode or "surface")
    _ztop, _zbot = float(req.placement.z_top_cm), float(req.placement.z_bottom_cm)
    if _pmode == "furrow":
        _ztop, _zbot = 5.0, 10.0
    elif _pmode == "fertigation":
        _ztop, _zbot = 0.0, 0.0
    nutrients = [
        {
            "symbol": s.symbol,
            "name": s.name,
            "dose_kg_ha": float(s.dose_kg_ha),
            "kd": float(s.kd),
            "initial_residual_mg_dm3": float(s.initial_residual_mg_dm3),
            "dispersivity_cm": float(s.dispersivity_cm),
            "release_type": (s.release_type or "immediate"),
            "release_days": float(s.release_days or 60.0),
            "placement_mode": _pmode,
            "z_app_top_cm": _ztop,
            "z_app_bottom_cm": _zbot,
            "fertigation_c0_mg_l": float(req.placement.fertigation_c0_mg_l),
            "fertigation_pulse_days": float(req.placement.fertigation_pulse_days),
        }
        for s in (req.solutes or [])
    ]
    # T5: modo "Somente água": nenhum soluto é transportado (só Richards + ET),
    # como o Gradio (water_only no sim.run). Escalar de transporte com fallback
    # neutro (exigido numérico pelo solver mesmo sem solutos).
    _kd_scalar = float(nutrients[0]["kd"]) if nutrients else 0.0
    _disp_scalar = (
        float(nutrients[0]["dispersivity_cm"]) if nutrients else float(req.depth_cm) / 10.0
    )
    if req.rain_series:
        full = [max(0.0, float(v or 0.0)) for v in req.rain_series]
        sw, ew = _effective_window(req, len(full))
        series = full[sw - 1:ew]
        if req.et0_series:
            full_et0 = [max(0.0, float(v or 0.0)) for v in req.et0_series]
            et0_eff: object = full_et0[sw - 1:ew]
        else:
            et0_eff = float(req.et0_mm_day)
        try:
            _app_raw = float(req.placement.application_day or 0.0)
        except (TypeError, ValueError):
            _app_raw = 0.0
        app_day_eff = (_app_raw - sw + 1) if _app_raw else 0.0
        total_days = float(len(series))
        water_events = [(float(d), 1.0, float(v)) for d, v in enumerate(series) if v > 0.0]
        total_rain = float(sum(series))
    else:
        sw, ew = 1, int(float(req.total_days))
        et0_eff = ([max(0.0, float(v or 0.0)) for v in req.et0_series] if req.et0_series else float(req.et0_mm_day))
        app_day_eff = float(req.placement.application_day or 0.0)
        total_days = float(req.total_days)
        per_day = float(req.rain_mm) / max(total_days, 1.0)
        water_events = [(float(d) + 0.5, 1.0, per_day) for d in range(int(total_days))]
        total_rain = float(req.rain_mm)

    cfg = SimulationConfig(
        depth_cm=float(req.depth_cm),
        dz=1.0,
        total_days=total_days,
        target_depth_cm=root_depth,
    )
    sim = Hydrus1DSimulator(soil=soil, crop=crop, config=cfg)
    # Defaults iguais ao Gradio: dias de leitura por frações da duração e,
    # no modo sazonal, nós de observação [20, 50, 100, perfil].
    _print_days_eff = _effective_print_days(req, total_days, sw, ew)
    _obs_depths = _default_obs_depths(float(req.depth_cm), _is_seasonal(req))
    results = sim.run(
        initial_moisture_pct=float(req.initial_moisture_pct),
        fertilizer_dose_kg_ha=sum(n["dose_kg_ha"] for n in nutrients),
        water_events=water_events,
        et0_mm_day=et0_eff,
        kd=_kd_scalar,
        dispersivity_cm=_disp_scalar,
        nutrients=nutrients,
        application_day=float(app_day_eff),
        obs_depths_cm=(_obs_depths if _obs_depths else None),
        print_days=(_print_days_eff if _print_days_eff else None),
        water_only=water_only,
    )
    return results, soil, crop, root_depth, total_rain, total_days


def _balances(req: SimulateRequest, results) -> list[SoluteBalance]:
    out: list[SoluteBalance] = []
    for s in (req.solutes or []):
        d = (results.nutrient_results.get(s.symbol) or {})
        leach = float(d.get("leaching_ratio_pct", 0.0) or 0.0)
        bottom = float(d.get("leached_bottom_pct", 0.0) or 0.0)
        out.append(
            SoluteBalance(
                symbol=s.symbol,
                name=s.name,
                dose_kg_ha=float(s.dose_kg_ha),
                retained_root_pct=float(d.get("retained_root_pct", 0.0) or 0.0),
                below_profile_pct=max(0.0, leach - bottom),
                bottom_pct=bottom,
                uptaken_pct=float(d.get("uptaken_pct", 0.0) or 0.0),
                peak_depth_cm=_peak_or_none(d.get("peak_depth_cm")),
            )
        )
    return out


def _common_xmax(results) -> float | None:
    """Escala X comum: maior pico entre todos os solutos (proporção comparável, como no Gradio)."""
    try:
        import numpy as _np

        gx = 0.0
        for _d in (getattr(results, "nutrient_results", {}) or {}).values():
            try:
                gx = max(gx, float(_np.max(_np.asarray(_d.get("final_profile", [0.0]), dtype=float))))
            except Exception:
                continue
        return gx if gx > 0 else None
    except Exception:
        return None


def _plot_one_b64(results, soil, crop, root_depth: float, total_rain: float, dose_total: float,
                  symbol: str, name: str, release_type: str, release_days: float,
                  out_path: str, x_max: float | None = None) -> str:
    """Um gráfico de perfil por soluto, como a galeria por-soluto do Gradio."""
    plot_nutrient_profile(
        results=results,
        soil=soil,
        crop=crop,
        rain_mm=float(total_rain),
        fertilizer_kg_ha=float(dose_total),
        nutrient_symbol=symbol,
        nutrient_name=name,
        output_path=out_path,
        target_depth_cm=root_depth,
        solute_filter=symbol,
        include_moisture=False,
        banner=True,
        x_max=x_max,
        release_type=(release_type or "immediate"),
        release_days=float(release_days or 60.0),
    )
    with open(out_path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def _plots_b64(req: SimulateRequest, results, soil, crop, root_depth: float,
               total_rain: float, out_dir: str) -> dict[str, str]:
    """Gera um PNG de perfil por soluto (símbolo -> base64)."""
    dose_total = sum(float(s.dose_kg_ha) for s in req.solutes)
    x_max = _common_xmax(results)
    out: dict[str, str] = {}
    for s in req.solutes:
        out[s.symbol] = _plot_one_b64(
            results, soil, crop, root_depth, total_rain, dose_total,
            s.symbol, s.name, (s.release_type or "immediate"),
            float(s.release_days or 60.0),
            os.path.join(out_dir, f"perfil_{s.symbol}.png"),
            x_max,
        )
    return out


def _water_balance(req: SimulateRequest, results, total_rain: float, total_days: float) -> WaterBalance:
    """Balanço hídrico do período (lâmina, drenagem, Δ armazenamento,
    escoamento e ET), com os rótulos dinâmicos do Gradio."""
    is_seasonal = _is_seasonal(req)
    if is_seasonal:
        try:
            full_year = float(total_days) >= 360
        except (TypeError, ValueError):
            full_year = False
        applied_label = "Chuva Anual Total" if full_year else "Chuva no Período"
        drainage_label = "Drenagem Anual" if full_year else "Drenagem no Período"
    else:
        applied_label = "Lâmina Aplicada"
        drainage_label = "Drenagem no Fundo"
    try:
        evap_mm = float(getattr(results, "evap_cum_cm", 0.0) or 0.0) * 10.0
    except (TypeError, ValueError):
        evap_mm = None
    try:
        transp_mm = float(getattr(results, "transp_cum_cm", 0.0) or 0.0) * 10.0
    except (TypeError, ValueError):
        transp_mm = None
    return WaterBalance(
        applied_mm=float(total_rain),
        drainage_mm=float(getattr(results, "q_bottom_cum_cm", 0.0) or 0.0) * 10.0,
        storage_mm=float(_storage_mm(results)),
        runoff_mm=float(getattr(results, "runoff_cum_cm", 0.0) or 0.0) * 10.0,
        evap_mm=evap_mm,
        transp_mm=transp_mm,
        applied_label=applied_label,
        drainage_label=drainage_label,
    )


def _water_plot_b64(results, soil, crop, root_depth: float, out_path: str) -> str:
    """Gráfico do perfil de umidade θ(z), como o modo só-água do Gradio."""
    from hydrus_core.visualizer import plot_water_profile

    plot_water_profile(
        results=results,
        output_path=out_path,
        soil=soil,
        root_depth_cm=(float(crop.root_depth_cm) if crop else None),
        crop=crop,
    )
    with open(out_path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def run_simulation(req: SimulateRequest, with_plot: bool = True) -> SimulateResponse:
    results, soil, crop, root_depth, total_rain, total_days = _run_core(req)
    water_only = bool(req.water_only)
    plot_b64: str | None = None
    plots_b64: dict[str, str] | None = None
    if with_plot:
        with tempfile.TemporaryDirectory() as tmp:
            if water_only:
                # Galeria vazia no modo só-água (Gradio: _solute_gallery_out = []).
                plots_b64 = {}
                plot_b64 = _water_plot_b64(
                    results, soil, crop, root_depth, os.path.join(tmp, "perfil_agua.png")
                )
            else:
                plots_b64 = _plots_b64(req, results, soil, crop, root_depth, total_rain, tmp)
                plot_b64 = plots_b64.get(req.solutes[0].symbol)
    return SimulateResponse(
        drainage_mm=float(results.q_bottom_cum_cm) * 10.0,
        solutes=_balances(req, results),
        plot_png_base64=plot_b64,
        plots_png_base64=plots_b64,
        profiles=_profiles_payload(results),
        water_only=water_only,
        water_balance=_water_balance(req, results, total_rain, total_days),
    )


def execute_job(req: SimulateRequest, job_dir: str) -> tuple[SimulateResponse, str, str]:
    """Roda uma vez e gera response + Excel + laudo no diretório do job."""
    os.makedirs(job_dir, exist_ok=True)
    results, soil, crop, root_depth, total_rain, total_days = _run_core(req)
    water_only = bool(req.water_only)
    if water_only:
        plots_b64: dict[str, str] = {}
        plot_b64 = _water_plot_b64(
            results, soil, crop, root_depth, os.path.join(job_dir, "perfil_agua.png")
        )
    else:
        plots_b64 = _plots_b64(req, results, soil, crop, root_depth, total_rain, job_dir)
        plot_b64 = plots_b64.get(req.solutes[0].symbol)
    # Compat: mantém perfil.png como o do primeiro soluto (ou o perfil de água).
    try:
        import shutil

        if water_only:
            src_png = os.path.join(job_dir, "perfil_agua.png")
        else:
            src_png = os.path.join(job_dir, f"perfil_{req.solutes[0].symbol}.png")
        if os.path.exists(src_png):
            shutil.copyfile(src_png, os.path.join(job_dir, "perfil.png"))
    except Exception:
        pass
    resp = SimulateResponse(
        drainage_mm=float(results.q_bottom_cum_cm) * 10.0,
        solutes=_balances(req, results),
        plot_png_base64=plot_b64,
        plots_png_base64=plots_b64,
        profiles=_profiles_payload(results),
        water_only=water_only,
        water_balance=_water_balance(req, results, total_rain, total_days),
    )
    excel_path = build_excel(req, results, soil, crop, root_depth, total_rain, total_days, job_dir)
    report_md = build_report(req, results, soil, crop, root_depth, total_rain, total_days)
    with open(os.path.join(job_dir, "laudo.md"), "w", encoding="utf-8") as f:
        f.write(report_md)
    return resp, excel_path, report_md


def _profiles_payload(results, max_pts: int = 200) -> dict:
    """Perfil final por soluto p/ gráfico interativo (amostrado)."""
    import numpy as _np

    z = _np.asarray(results.z, dtype=float)
    n = len(z)
    step = max(1, n // max_pts)
    idx = list(range(0, n, step))
    if idx[-1] != n - 1:
        idx.append(n - 1)
    out: dict = {"z": [float(z[i]) for i in idx], "solutes": {}}
    for sym, d in (getattr(results, "nutrient_results", {}) or {}).items():
        prof = _np.asarray(d.get("final_profile", []), dtype=float)
        if len(prof) == n:
            out["solutes"][sym] = {
                "name": str(d.get("name", sym)),
                "c": [float(prof[i]) for i in idx],
            }
    return out


def _sim_params(req: SimulateRequest, results, soil, crop, root_depth: float, total_rain: float, total_days: float) -> dict:
    """Params p/ Excel e laudo (mesmas chaves do Gradio sazonal).

    Inclui os defaults do Gradio para o modo seasonal: print_days por
    frações da duração e janela de análise = período todo.
    """
    water_only = bool(req.water_only)
    solutes = list(req.solutes or [])
    dose_total = sum(float(s.dose_kg_ha) for s in solutes)
    first = solutes[0] if solutes else None
    nr = getattr(results, "nutrient_results", {}) or {}
    prim = (nr.get(first.symbol, {}) or {}) if first is not None else {}
    z = getattr(results, "z", [0.0])
    try:
        prof_depth = float(max(z))
    except Exception:
        prof_depth = float(req.depth_cm)
    is_multi = len(solutes) > 1
    is_seasonal = _is_seasonal(req)
    if req.rain_series:
        _sw, _ew = _effective_window(req, len(req.rain_series))
    else:
        _sw, _ew = 1, int(float(total_days))
    _print_days_eff = _effective_print_days(req, total_days, _sw, _ew)
    _n_win = int(float(total_days))
    # Rótulo da janela como no Gradio sazonal (sw/ew efetivos vs ano cheio).
    _win_txt = f"{_sw}–{_ew}" if (_sw > 1 or _ew < 365) else "ano cheio (1–365)"
    _pmode = (req.placement.mode or "surface")
    _ptop, _pbot = float(req.placement.z_top_cm), float(req.placement.z_bottom_cm)
    if _pmode == "furrow":
        _ptop, _pbot = 5.0, 10.0
    elif _pmode == "fertigation":
        _ptop, _pbot = 0.0, 0.0
    try:
        _peak_raw = prim.get("peak_depth_cm", 0.0)
        _peak = float(_peak_raw if _peak_raw is not None else 0.0)
    except (TypeError, ValueError):
        _peak = 0.0
    if req.et0_series:
        try:
            _full_et0 = [max(0.0, float(v or 0.0)) for v in req.et0_series]
            # Média na janela de análise efetiva (como a série usada no solver).
            _et0_vals = _full_et0[_sw - 1:_ew] if req.rain_series else _full_et0
            _et0_mean = float(sum(_et0_vals) / max(len(_et0_vals), 1))
        except (TypeError, ValueError):
            _et0_mean = float(req.et0_mm_day)
    else:
        _et0_mean = float(req.et0_mm_day)
    try:
        _evap_day = float(getattr(results, "evap_cum_cm", 0.0) or 0.0) * 10.0 / max(float(total_days), 1.0)
        _transp_day = float(getattr(results, "transp_cum_cm", 0.0) or 0.0) * 10.0 / max(float(total_days), 1.0)
    except (TypeError, ValueError):
        _evap_day, _transp_day = 0.0, 0.0
    rel_type = ((first.release_type if first is not None else None) or "immediate")
    _nutr_name = first.name if first is not None else "Somente Água"
    _nutr_sym = first.symbol if first is not None else "water_only"
    return {
        "sim_type": ("seasonal" if is_seasonal else "column"),
        "mode_label": (
            f"Simulação Série Hídrica ({_n_win} dias, janela {_win_txt})"
            if is_seasonal else "column"
        ),
        "nutrient_label": (
            "Somente Água" if water_only
            else ("Formulação Multi-Nutriente" if is_multi else _nutr_name)
        ),
        "nutrient_symbol": _nutr_sym,
        "fertilizer_label": _nutr_name,
        "fertilizer_name": _nutr_name,
        "gross_dose": dose_total,
        "elemental_dose": dose_total,
        "soil_name": soil.name,
        "soil_citation": f"Solo {soil.name}",
        "theta_r": float(soil.theta_r),
        "theta_s": float(soil.theta_s),
        "alpha": float(soil.alpha),
        "n": float(soil.n),
        "ks": float(soil.ks),
        "bulk_density": float(soil.bulk_density),
        "kd": float(first.kd) if first is not None else 0.0,
        "kd_citation": "Referência para a textura (ajustável; não calibrado)",
        "dispersivity": float(first.dispersivity_cm) if first is not None else float(req.depth_cm) / 10.0,
        "crop_name": (crop.name if crop else "Perfil de solo nu (sem cultura)"),
        "crop_citation": (
            f"Transpiração via Feddes (kc={float(crop.kc):.2f}); raiz fixa em {float(crop.root_depth_cm):.0f} cm."
            if crop else "Sem cultura: apenas evaporação do solo."
        ),
        "root_depth_cm": float(root_depth),
        "h1": float(crop.h1 if crop else 0.0),
        "h2": float(crop.h2 if crop else 0.0),
        "h3": float(crop.h3 if crop else 0.0),
        "h4": float(crop.h4 if crop else 0.0),
        "rain_mm": float(total_rain),
        "total_days": float(total_days),
        "initial_moisture_pct": float(req.initial_moisture_pct),
        "leaching_pct": float(prim.get("leaching_ratio_pct", 0.0) or 0.0),
        "retained_pct": float(prim.get("retained_root_pct", 0.0) or 0.0),
        "leaching_ratio_pct": float(prim.get("leaching_ratio_pct", 0.0) or 0.0),
        "retained_root_pct": float(prim.get("retained_root_pct", 0.0) or 0.0),
        "uptaken_pct": float(prim.get("uptaken_pct", 0.0) or 0.0),
        "peak_depth_cm": _peak,
        "q_bottom_cm": float(getattr(results, "q_bottom_cum_cm", 0.0) or 0.0),
        "active_depth_cm": float(_pbot - _ptop) if _pbot > _ptop else 0.0,
        "placement_top_cm": float(_ptop),
        "placement_bottom_cm": float(_pbot),
        "dose_note": f"{dose_total:.0f} kg/ha de {_nutr_name}",
        "release_type": rel_type,
        "release_days": float((first.release_days if first is not None else None) or 60.0),
        "release_label": (
            "Liberação Controlada / Lenta (Polímero / CRF)"
            if rel_type == "controlled" else "Convencional (Solubilização Instantânea)"
        ),
        "is_multi_nutr": bool(is_multi),
        "nutrient_results": nr,
        "water_only": bool(water_only),
        "profile_depth_cm": float(prof_depth),
        "storage_mm": float(_storage_mm(results)),
        "runoff_mm": float(getattr(results, "runoff_cum_cm", 0.0) or 0.0) * 10.0,
        "drainage_mm": float(getattr(results, "q_bottom_cum_cm", 0.0) or 0.0) * 10.0,
        "evap_mm_day": float(_evap_day),
        "transp_mm_day": float(_transp_day),
        "et0_mm_day": float(_et0_mean),
        "obs_depths_cm": list(getattr(results, "obs_depths_cm", []) or []),
        # Janela de análise efetiva + dias de leitura (dias de ensaio).
        "print_days": list(_print_days_eff),
        "analysis_start_day": int(_sw),
        "analysis_end_day": int(_ew),
        "window_label": _win_txt,
    }


def _seasonal_results_for_excel(req: SimulateRequest, results, soil, crop, root_depth: float,
                                total_rain: float, total_days: float):
    """Cópia de results com os atributos que _export_seasonal_sheets lê.

    O exportador sazonal espera perfis indexados por dia
    (dicts dia -> perfil): print_days, theta_profiles (dict),
    conc_total_profiles, além de metadados (nutrient_symbol, soil_name…).
    O solver devolve theta_profiles como lista e print_profiles como
    dict dia -> {"theta", "c_total"}; aqui convertemos sem mutar o
    objeto original (o laudo usa as listas).
    """
    import copy

    first = (req.solutes or [None])[0]
    sym = first.symbol if first is not None else "water_only"
    if req.rain_series:
        _sw0, _ew0 = _effective_window(req, len(req.rain_series))
    else:
        _sw0, _ew0 = 1, int(float(total_days))
    print_days = _effective_print_days(req, total_days, _sw0, _ew0)
    pp = getattr(results, "print_profiles", None) or {}
    try:
        _z = getattr(results, "z", None)
        n_z = len(_z) if _z is not None else 0
    except TypeError:
        n_z = 0
    theta_d: dict = {}
    tot_d: dict = {}
    for d in print_days:
        snap = pp.get(float(d))
        if snap is None:
            snap = pp.get(int(d))
        if not isinstance(snap, dict):
            continue
        th = snap.get("theta")
        try:
            if th is not None and len(th) == n_z:
                theta_d[d] = th
        except TypeError:
            pass
        cmap = snap.get("c_total") or {}
        arr = cmap.get(sym)
        try:
            if arr is not None and len(arr) == n_z:
                tot_d[d] = arr
        except TypeError:
            pass
    # Fallback: dia final usa o perfil final do nutriente.
    try:
        nr = getattr(results, "nutrient_results", {}) or {}
        final_prof = (nr.get(sym) or {}).get("final_profile")
        if print_days and final_prof is not None and len(final_prof) == n_z:
            last = print_days[-1]
            tot_d.setdefault(last, final_prof)
    except (TypeError, ValueError):
        pass
    try:
        res = copy.copy(results)
    except Exception:
        res = results
        return res
    try:
        res.print_days = list(print_days)
        res.theta_profiles = dict(theta_d)
        res.conc_total_profiles = dict(tot_d)
        if not hasattr(res, "conc_aq_profiles"):
            res.conc_aq_profiles = {}
        if not hasattr(res, "conc_profiles"):
            res.conc_profiles = {}
        res.nutrient_symbol = sym
        res.soil_name = getattr(res, "soil_name", None) or soil.name
        res.nutrient_name = getattr(res, "nutrient_name", None) or (first.name if first is not None else "Somente Água")
        res.kd_used = getattr(res, "kd_used", None) or (float(first.kd) if first is not None else 0.0)
        res.root_depth_cm = getattr(res, "root_depth_cm", None) or float(root_depth)
        res.total_rain_mm = getattr(res, "total_rain_mm", None) or float(total_rain)
    except Exception:
        pass
    return res


def build_excel(req: SimulateRequest, results, soil, crop, root_depth: float,
                total_rain: float, total_days: float, job_dir: str) -> str:
    from hydrus_core.export_excel import export_soil_profile_excel

    out = os.path.join(job_dir, "perfil.xlsx")
    mode = "seasonal" if _is_seasonal(req) else "column"
    params = _sim_params(req, results, soil, crop, root_depth, total_rain, total_days)
    res_for_excel = (
        _seasonal_results_for_excel(req, results, soil, crop, root_depth, total_rain, total_days)
        if mode == "seasonal" else results
    )
    return export_soil_profile_excel(
        res_for_excel, out,
        sim_params=params,
        mode=mode,
    )


def _report_hydro(req: SimulateRequest, results, total_days: float) -> tuple[float, float, float, float, float]:
    """Hidro-args extras do laudo coluna, iguais aos do Gradio (runoff/storage/ET)."""
    try:
        storage = float(_storage_mm(results))
    except Exception:
        storage = 0.0
    try:
        runoff = float(getattr(results, "runoff_cum_cm", 0.0) or 0.0) * 10.0
    except (TypeError, ValueError):
        runoff = 0.0
    try:
        evap_day = float(getattr(results, "evap_cum_cm", 0.0) or 0.0) * 10.0 / max(float(total_days), 1.0)
        transp_day = float(getattr(results, "transp_cum_cm", 0.0) or 0.0) * 10.0 / max(float(total_days), 1.0)
    except (TypeError, ValueError):
        evap_day, transp_day = 0.0, 0.0
    if req.et0_series:
        try:
            et0_vals = [max(0.0, float(v or 0.0)) for v in req.et0_series]
            et0_mean = float(sum(et0_vals) / max(len(et0_vals), 1))
        except (TypeError, ValueError):
            et0_mean = float(req.et0_mm_day)
    else:
        et0_mean = float(req.et0_mm_day)
    return storage, runoff, evap_day, transp_day, et0_mean


def _report_active_depth(req: SimulateRequest) -> float:
    _pmode = (req.placement.mode or "surface")
    _ptop, _pbot = float(req.placement.z_top_cm), float(req.placement.z_bottom_cm)
    if _pmode == "furrow":
        _ptop, _pbot = 5.0, 10.0
    elif _pmode == "fertigation":
        _ptop, _pbot = 0.0, 0.0
    return float(_pbot - _ptop) if _pbot > _ptop else 0.0


def build_report(req: SimulateRequest, results, soil, crop, root_depth: float,
                 total_rain: float, total_days: float) -> str:
    """Laudo multi-soluto via hydrus_core.agronomic_report (o core já cobre N solutos).

    Usa as mesmas funções do Gradio (generate_advanced_report / generate_column_report);
    como results.nutrient_results contém todos os solutos, o comparativo multi-nutriente
    e o cabeçalho multi-soluto são gerados pelo core sem texto novo.
    """
    from hydrus_core.agronomic_report import generate_advanced_report, generate_column_report
    from hydrus_core.explanatory_pipeline import generate_simulation_step_by_step

    if bool(req.water_only):
        # Laudo do modo "somente água": balanço hídrico (texto portado do Gradio)
        # + passo a passo do core (que já cobre water_only).
        params = _sim_params(req, results, soil, crop, root_depth, total_rain, total_days)
        storage, runoff, evap_day, transp_day, _et0 = _report_hydro(req, results, total_days)
        if _is_seasonal(req):
            if req.rain_series:
                _sw_r, _ew_r = _effective_window(req, len(req.rain_series))
            else:
                _sw_r, _ew_r = 1, int(float(total_days))
            _n_win_r = int(float(total_days))
            _win_txt_r = f"{_sw_r}–{_ew_r}" if (_sw_r > 1 or _ew_r < 365) else "ano cheio (1–365)"
            _full_len = len(req.rain_series) if req.rain_series else _n_win_r
            _win_suffix = (
                f" (janela de análise: dias {_sw_r}–{_ew_r})"
                if (_sw_r > 1 or _ew_r < _full_len) else ""
            )
            base = seasonal_water_only_report(
                soil=soil, crop=crop, prof_depth=float(params["profile_depth_cm"]),
                total_rain=float(total_rain), n_win=_n_win_r, win_txt=_win_txt_r,
                source_label=f"Série diária informada pelo usuário{_win_suffix}",
                drainage_mm=float(params["drainage_mm"]), runoff_mm=float(runoff),
                storage_mm=float(storage),
                obs_depths_cm=list(getattr(results, "obs_depths_cm", []) or []),
            )
        else:
            z = getattr(results, "z", [0.0])
            try:
                prof_depth = float(max(z))
            except Exception:
                prof_depth = float(req.depth_cm)
            base = column_water_only_report(
                soil=soil, crop=crop, col_depth=float(prof_depth),
                rain_mm=float(total_rain), total_days=float(total_days),
                initial_moisture_pct=float(req.initial_moisture_pct),
                evap_mm_day=float(evap_day), transp_mm_day=float(transp_day),
                drainage_mm=float(getattr(results, "q_bottom_cum_cm", 0.0) or 0.0) * 10.0,
                runoff_mm=float(runoff), storage_mm=float(storage),
                obs_depths_cm=list(getattr(results, "obs_depths_cm", []) or []),
            )
        step_md, step_html = generate_simulation_step_by_step(params)
        return f"{base}\n\n---\n\n{step_md}"

    first = (req.solutes or [None])[0]
    dose_total = sum(float(s.dose_kg_ha) for s in (req.solutes or []))
    active_depth = _report_active_depth(req)
    if _is_seasonal(req):
        return generate_advanced_report(
            results=results, soil=soil, crop=crop, rain_mm=float(total_rain),
            fertilizer_dose_kg_ha=dose_total, nutrient_symbol=first.symbol,
            nutrient_name=first.name, kd_used=float(first.kd),
            release_type=(first.release_type or "immediate"),
            release_days=float(first.release_days or 60.0),
            active_depth_cm=float(active_depth),
        )
    z = getattr(results, "z", [0.0])
    try:
        prof_depth = float(max(z))
    except Exception:
        prof_depth = float(req.depth_cm)
    storage, runoff, evap_day, transp_day, et0_mean = _report_hydro(req, results, total_days)
    return generate_column_report(
        results=results, soil=soil, rain_mm=float(total_rain),
        fertilizer_dose_kg_ha=dose_total, target_depth_cm=float(root_depth),
        column_height_cm=float(prof_depth), nutrient_symbol=first.symbol,
        nutrient_name=first.name, kd_used=float(first.kd),
        release_type=(first.release_type or "immediate"),
        release_days=float(first.release_days or 60.0),
        total_days=float(total_days),
        active_depth_cm=float(active_depth),
        runoff_mm=float(runoff),
        storage_mm=float(storage),
        evap_mm_day=float(evap_day),
        transp_mm_day=float(transp_day),
        et0_mm_day=float(et0_mean),
    )
