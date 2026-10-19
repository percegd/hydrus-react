"""Camada de serviço: traduz request HTTP -> hydrus-core -> resposta.

Regras de domínio (as mesmas do app legado):
- camada avaliada = raiz da cultura, ou perfil todo sem cultura;
- balanço em 3 vias: retido 0–raiz / abaixo no perfil / fundo (+ absorvido).
"""

import base64
import io
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


def run_simulation(req: SimulateRequest, with_plot: bool = True) -> SimulateResponse:
    soil = SOIL_DATABASE[req.soil_key]
    crop = CROP_DATABASE.get(req.crop_key) if req.crop_key else None
    root_depth = float(crop.root_depth_cm) if crop else float(req.depth_cm)
    if req.root_depth_cm and crop:
        root_depth = float(req.root_depth_cm)

    cfg = SimulationConfig(
        depth_cm=float(req.depth_cm),
        dz=1.0,
        total_days=float(req.total_days),
        target_depth_cm=root_depth,
    )
    sim = Hydrus1DSimulator(soil=soil, crop=crop, config=cfg)
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
            "placement_mode": "surface",
            "z_app_top_cm": 0.0,
            "z_app_bottom_cm": 2.0,
        }
        for s in req.solutes
    ]
    if req.rain_series:
        series = [max(0.0, float(v or 0.0)) for v in req.rain_series]
        total_days = float(len(series))
        cfg = SimulationConfig(
            depth_cm=float(req.depth_cm),
            dz=1.0,
            total_days=total_days,
            target_depth_cm=root_depth,
        )
        sim = Hydrus1DSimulator(soil=soil, crop=crop, config=cfg)
        water_events = [(float(d), 1.0, float(v)) for d, v in enumerate(series) if v > 0.0]
        total_rain = float(sum(series))
    else:
        # Chuva distribuída uniformemente.
        total_days = float(req.total_days)
        per_day = float(req.rain_mm) / max(total_days, 1.0)
        water_events = [(float(d) + 0.5, 1.0, per_day) for d in range(int(total_days))]
        total_rain = float(req.rain_mm)
    results = sim.run(
        initial_moisture_pct=float(req.initial_moisture_pct),
        fertilizer_dose_kg_ha=sum(n["dose_kg_ha"] for n in nutrients),
        water_events=water_events,
        et0_mm_day=float(req.et0_mm_day),
        kd=float(nutrients[0]["kd"]),
        dispersivity_cm=float(nutrients[0]["dispersivity_cm"]),
        nutrients=nutrients,
    )

    balances: list[SoluteBalance] = []
    for s in req.solutes:
        d = (results.nutrient_results.get(s.symbol) or {})
        leach = float(d.get("leaching_ratio_pct", 0.0) or 0.0)
        bottom = float(d.get("leached_bottom_pct", 0.0) or 0.0)
        balances.append(
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

    plot_b64: str | None = None
    if with_plot:
        first = req.solutes[0]
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "perfil.png")
            plot_nutrient_profile(
                results=results,
                soil=soil,
                crop=crop,
                rain_mm=float(total_rain),
                fertilizer_kg_ha=sum(n["dose_kg_ha"] for n in nutrients),
                nutrient_symbol=first.symbol,
                nutrient_name=first.name,
                output_path=out,
                target_depth_cm=root_depth,
            )
            with open(out, "rb") as f:
                plot_b64 = base64.b64encode(f.read()).decode()

    return SimulateResponse(
        drainage_mm=float(results.q_bottom_cum_cm) * 10.0,
        solutes=balances,
        plot_png_base64=plot_b64,
    )
