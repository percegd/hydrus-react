"""Paridade numérica: hydrus_core (novo pacote) vs core legado.

Garante que a extração do pacote (renomeação de imports) não alterou
a física. Requer o checkout legado em HYDRUS_LEGACY_ROOT
(default: ../Hydrus).
"""

import os
import sys

import pytest

LEGACY_ROOT = os.environ.get(
    "HYDRUS_LEGACY_ROOT",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "Hydrus"),
)

needs_legacy = pytest.mark.skipif(
    not os.path.isdir(os.path.join(LEGACY_ROOT, "core")),
    reason="checkout legado ausente (HYDRUS_LEGACY_ROOT)",
)

if os.path.isdir(os.path.join(LEGACY_ROOT, "core")) and LEGACY_ROOT not in sys.path:
    sys.path.insert(0, LEGACY_ROOT)

from hydrus_core.crop import CROP_DATABASE as NEW_CROPS  # noqa: E402
from hydrus_core.hydrus_solver import Hydrus1DSimulator as NewSim  # noqa: E402
from hydrus_core.hydrus_solver import SimulationConfig as NewCfg  # noqa: E402
from hydrus_core.soil_physics import SOIL_DATABASE as NEW_SOILS  # noqa: E402


def _run(sim_cls, cfg_cls, soils, crops, days, events, nutrients):
    sim = sim_cls(
        soil=soils["latossolo_medio"],
        crop=crops["soja"],
        config=cfg_cls(depth_cm=200.0, dz=1.0, total_days=float(days), target_depth_cm=35.0),
    )
    return sim.run(
        initial_moisture_pct=20.0,
        fertilizer_dose_kg_ha=sum(n["dose_kg_ha"] for n in nutrients),
        water_events=events,
        et0_mm_day=4.0,
        kd=float(nutrients[0]["kd"]),
        nutrients=nutrients,
    )


def _balances(res):
    out = {}
    for sym, d in (res.nutrient_results or {}).items():
        out[sym] = (
            float(d.get("retained_root_pct", 0.0) or 0.0),
            float(d.get("leaching_ratio_pct", 0.0) or 0.0),
            float(d.get("uptaken_pct", 0.0) or 0.0),
            float(d.get("peak_depth_cm", 0.0) or 0.0),
        )
    return out


CASES = [
    (
        "K coluna 30d",
        30,
        [(5.0, 1.0, 50.0)],
        [{"symbol": "K", "name": "Potássio", "dose_kg_ha": 30.0, "kd": 0.45,
          "initial_residual_mg_dm3": 0.0, "dispersivity_cm": 20.0}],
    ),
    (
        "N/K/S serie 120d",
        120,
        [(float(d), 1.0, 3.5) for d in range(120)],
        [
            {"symbol": "N", "name": "Nitrato", "dose_kg_ha": 30.0, "kd": 0.0,
             "initial_residual_mg_dm3": 0.0, "dispersivity_cm": 20.0},
            {"symbol": "K", "name": "Potássio", "dose_kg_ha": 30.0, "kd": 0.45,
             "initial_residual_mg_dm3": 0.0, "dispersivity_cm": 20.0},
            {"symbol": "S", "name": "Enxofre", "dose_kg_ha": 40.0, "kd": 0.15,
             "initial_residual_mg_dm3": 0.0, "dispersivity_cm": 20.0},
        ],
    ),
]


@needs_legacy
@pytest.mark.parametrize("label,days,events,nutrients", CASES)
def test_parity_with_legacy(label, days, events, nutrients):
    import core.crop as legacy_crop
    import core.hydrus_solver as legacy_solver
    import core.soil_physics as legacy_soil

    new_res = _run(NewSim, NewCfg, NEW_SOILS, NEW_CROPS, days, events, nutrients)
    old_res = _run(
        legacy_solver.Hydrus1DSimulator, legacy_solver.SimulationConfig,
        legacy_soil.SOIL_DATABASE, legacy_crop.CROP_DATABASE, days, events, nutrients,
    )
    new_bal, old_bal = _balances(new_res), _balances(old_res)
    assert set(new_bal) == set(old_bal)
    for sym in new_bal:
        for a, b in zip(new_bal[sym], old_bal[sym]):
            assert abs(a - b) <= 1e-6 * max(1.0, abs(b)), f"{label} {sym}: {a} != {b}"
    assert abs(float(new_res.q_bottom_cum_cm) - float(old_res.q_bottom_cum_cm)) <= 1e-9
