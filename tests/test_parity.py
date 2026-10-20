"""Invariantes físicos do hydrus_core (física revisada v4).

Física revisada v4: Kc dual FAO-56 (Tp=Kcb·ET0, Ep=Ke·ET0 em vez de
E=ET0−T), teto de absorção pela demanda da cultura, % sobre dose+residual
e raiz variável no ciclo. Cada caso parametrizado roda o solver 1D do
pacote e verifica os invariantes que valem em qualquer simulação:

- fechamento hídrico (|water_closure_pct| < 2%) e drenagem não-negativa;
- fechamento de massa por nutriente (|mass_closure_pct| < 1%);
- soma dos destinos ≈ 100% (±1): retido na raiz + abaixo da raiz +
  fundo + absorvido + cápsula;
- faixas físicas dos % de destino (0–100).
"""

import pytest

from hydrus_core.crop import CROP_DATABASE
from hydrus_core.hydrus_solver import Hydrus1DSimulator, SimulationConfig
from hydrus_core.soil_physics import SOIL_DATABASE


def _run(days, events, nutrients):
    sim = Hydrus1DSimulator(
        soil=SOIL_DATABASE["latossolo_medio"],
        crop=CROP_DATABASE["soja"],
        config=SimulationConfig(
            depth_cm=200.0, dz=1.0, total_days=float(days), target_depth_cm=35.0
        ),
    )
    return sim.run(
        initial_moisture_pct=20.0,
        fertilizer_dose_kg_ha=sum(n["dose_kg_ha"] for n in nutrients),
        water_events=events,
        et0_mm_day=4.0,
        kd=float(nutrients[0]["kd"]),
        nutrients=nutrients,
    )


def _assert_invariants(res, nutrients, label: str) -> None:
    """Invariantes garantidos pela física revisada v4."""
    # Fechamento hídrico.
    assert abs(float(res.water_closure_pct)) < 2.0, f"{label}: water_closure={res.water_closure_pct}"
    assert res.q_bottom_cum_cm >= 0.0, f"{label}: drenagem negativa"
    for n in nutrients:
        sym = n["symbol"]
        d = res.nutrient_results[sym]
        # Fechamento de massa por nutriente.
        assert abs(float(d.get("mass_closure_pct", 0.0) or 0.0)) < 1.0, (
            f"{label} {sym}: mass_closure={d.get('mass_closure_pct')}"
        )
        # Soma dos destinos fecha 100% (±1): retido + abaixo + fundo + absorvido + cápsula.
        below = float(d.get("leaching_ratio_pct", 0.0) or 0.0) - float(d.get("leached_bottom_pct", 0.0) or 0.0)
        total = (
            float(d.get("retained_root_pct", 0.0) or 0.0) + below
            + float(d.get("leached_bottom_pct", 0.0) or 0.0)
            + float(d.get("uptaken_pct", 0.0) or 0.0)
            + float(d.get("capsule_pct", 0.0) or 0.0)
        )
        assert abs(total - 100.0) <= 1.0, f"{label} {sym}: soma={total}"
        for key in ("retained_root_pct", "leaching_ratio_pct", "uptaken_pct"):
            v = float(d.get(key, 0.0) or 0.0)
            assert 0.0 <= v <= 100.0, f"{label} {sym} {key}={v}"


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


@pytest.mark.parametrize("label,days,events,nutrients", CASES)
def test_invariants_hydrus_core(label, days, events, nutrients):
    res = _run(days, events, nutrients)
    _assert_invariants(res, nutrients, label)
