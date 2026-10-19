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

from .schemas import SimulateRequest, SimulateResponse, SoluteBalance


def _peak_or_none(value) -> float | None:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) else v


def _run_core(req: SimulateRequest):
    """Executa o solver uma vez; retorna (results, soil, crop, root_depth, total_rain, total_days)."""
    soil = SOIL_DATABASE[req.soil_key]
    crop = CROP_DATABASE.get(req.crop_key) if req.crop_key else None
    root_depth = float(crop.root_depth_cm) if crop else float(req.depth_cm)
    if req.root_depth_cm and crop:
        root_depth = float(req.root_depth_cm)

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
        for s in req.solutes
    ]
    if req.rain_series:
        series = [max(0.0, float(v or 0.0)) for v in req.rain_series]
        total_days = float(len(series))
        water_events = [(float(d), 1.0, float(v)) for d, v in enumerate(series) if v > 0.0]
        total_rain = float(sum(series))
    else:
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
    results = sim.run(
        initial_moisture_pct=float(req.initial_moisture_pct),
        fertilizer_dose_kg_ha=sum(n["dose_kg_ha"] for n in nutrients),
        water_events=water_events,
        et0_mm_day=([max(0.0, float(v or 0.0)) for v in req.et0_series] if req.et0_series else float(req.et0_mm_day)),
        kd=float(nutrients[0]["kd"]),
        dispersivity_cm=float(nutrients[0]["dispersivity_cm"]),
        nutrients=nutrients,
        application_day=float(req.placement.application_day),
    )
    return results, soil, crop, root_depth, total_rain, total_days


def _balances(req: SimulateRequest, results) -> list[SoluteBalance]:
    out: list[SoluteBalance] = []
    for s in req.solutes:
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


def _plot_b64(req: SimulateRequest, results, soil, crop, root_depth: float, total_rain: float, out_path: str) -> str:
    first = req.solutes[0]
    plot_nutrient_profile(
        results=results,
        soil=soil,
        crop=crop,
        rain_mm=float(total_rain),
        fertilizer_kg_ha=sum(float(s.dose_kg_ha) for s in req.solutes),
        nutrient_symbol=first.symbol,
        nutrient_name=first.name,
        output_path=out_path,
        target_depth_cm=root_depth,
    )
    with open(out_path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def run_simulation(req: SimulateRequest, with_plot: bool = True) -> SimulateResponse:
    results, soil, crop, root_depth, total_rain, _days = _run_core(req)
    plot_b64: str | None = None
    if with_plot:
        with tempfile.TemporaryDirectory() as tmp:
            plot_b64 = _plot_b64(req, results, soil, crop, root_depth, total_rain, os.path.join(tmp, "perfil.png"))
    return SimulateResponse(
        drainage_mm=float(results.q_bottom_cum_cm) * 10.0,
        solutes=_balances(req, results),
        plot_png_base64=plot_b64,
        profiles=_profiles_payload(results),
    )


def execute_job(req: SimulateRequest, job_dir: str) -> tuple[SimulateResponse, str, str]:
    """Roda uma vez e gera response + Excel + laudo no diretório do job."""
    os.makedirs(job_dir, exist_ok=True)
    results, soil, crop, root_depth, total_rain, total_days = _run_core(req)
    plot_b64 = _plot_b64(req, results, soil, crop, root_depth, total_rain, os.path.join(job_dir, "perfil.png"))
    resp = SimulateResponse(
        drainage_mm=float(results.q_bottom_cum_cm) * 10.0,
        solutes=_balances(req, results),
        plot_png_base64=plot_b64,
        profiles=_profiles_payload(results),
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
    """Params mínimos p/ Excel e laudo (mesmas chaves do legado)."""
    dose_total = sum(float(s.dose_kg_ha) for s in req.solutes)
    first = req.solutes[0]
    nr = getattr(results, "nutrient_results", {}) or {}
    prim = nr.get(first.symbol, {}) or {}
    z = getattr(results, "z", [0.0])
    try:
        prof_depth = float(max(z))
    except Exception:
        prof_depth = float(req.depth_cm)
    return {
        "sim_type": "api",
        "nutrient_symbol": first.symbol,
        "fertilizer_name": first.name,
        "elemental_dose": dose_total,
        "soil_name": soil.name,
        "theta_r": float(soil.theta_r),
        "theta_s": float(soil.theta_s),
        "alpha": float(soil.alpha),
        "n": float(soil.n),
        "ks": float(soil.ks),
        "bulk_density": float(soil.bulk_density),
        "kd": float(first.kd),
        "kd_citation": "Referência para a textura (ajustável; não calibrado)",
        "dispersivity": float(first.dispersivity_cm),
        "crop_name": (crop.name if crop else "Perfil de solo nu (sem cultura)"),
        "root_depth_cm": float(root_depth),
        "rain_mm": float(total_rain),
        "total_days": float(total_days),
        "leaching_pct": float(prim.get("leaching_ratio_pct", 0.0) or 0.0),
        "retained_pct": float(prim.get("retained_root_pct", 0.0) or 0.0),
        "leaching_ratio_pct": float(prim.get("leaching_ratio_pct", 0.0) or 0.0),
        "retained_root_pct": float(prim.get("retained_root_pct", 0.0) or 0.0),
        "uptaken_pct": float(prim.get("uptaken_pct", 0.0) or 0.0),
        "peak_depth_cm": float(prim.get("peak_depth_cm", 0.0) or 0.0),
        "q_bottom_cm": float(getattr(results, "q_bottom_cum_cm", 0.0) or 0.0),
        "release_type": (first.release_type or "immediate"),
        "release_days": float(first.release_days or 60.0),
        "nutrient_results": nr,
        "water_only": False,
        "profile_depth_cm": float(prof_depth),
        "runoff_mm": float(getattr(results, "runoff_cum_cm", 0.0) or 0.0) * 10.0,
        "drainage_mm": float(getattr(results, "q_bottom_cum_cm", 0.0) or 0.0) * 10.0,
        "obs_depths_cm": list(getattr(results, "obs_depths_cm", []) or []),
    }


def build_excel(req: SimulateRequest, results, soil, crop, root_depth: float,
                total_rain: float, total_days: float, job_dir: str) -> str:
    from hydrus_core.export_excel import export_soil_profile_excel

    out = os.path.join(job_dir, "perfil.xlsx")
    mode = "seasonal" if float(total_days) >= 180 else "column"
    return export_soil_profile_excel(
        results, out,
        sim_params=_sim_params(req, results, soil, crop, root_depth, total_rain, total_days),
        mode=mode,
    )


def build_report(req: SimulateRequest, results, soil, crop, root_depth: float,
                 total_rain: float, total_days: float) -> str:
    from hydrus_core.agronomic_report import generate_advanced_report, generate_column_report

    first = req.solutes[0]
    dose_total = sum(float(s.dose_kg_ha) for s in req.solutes)
    if float(total_days) >= 180:
        return generate_advanced_report(
            results=results, soil=soil, crop=crop, rain_mm=float(total_rain),
            fertilizer_dose_kg_ha=dose_total, nutrient_symbol=first.symbol,
            nutrient_name=first.name, kd_used=float(first.kd),
            release_type=(first.release_type or "immediate"),
            release_days=float(first.release_days or 60.0),
        )
    z = getattr(results, "z", [0.0])
    try:
        prof_depth = float(max(z))
    except Exception:
        prof_depth = float(req.depth_cm)
    return generate_column_report(
        results=results, soil=soil, rain_mm=float(total_rain),
        fertilizer_dose_kg_ha=dose_total, target_depth_cm=float(root_depth),
        column_height_cm=float(prof_depth), nutrient_symbol=first.symbol,
        nutrient_name=first.name, kd_used=float(first.kd),
        release_type=(first.release_type or "immediate"),
        release_days=float(first.release_days or 60.0),
        total_days=float(total_days),
    )
