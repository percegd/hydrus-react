"""P9 — correções agronômicas no núcleo (catálogo, ciclo/Kc dual, teto e balanço)."""

from hydrus_core.crop import CROP_DATABASE, crop_schedule
from hydrus_core.literature_database import COMMERCIAL_FERTILIZERS
from hydrus_core.soil_physics import SOIL_DATABASE
from hydrus_core.hydrus_solver import Hydrus1DSimulator, SimulationConfig


def test_1_catalogo_kcl_ssp_tsp():
    kcl = COMMERCIAL_FERTILIZERS["kcl"]
    assert abs(float(kcl["nutrient_pct"]) - 49.8) < 1e-9
    assert abs(200.0 * float(kcl["nutrient_pct"]) / 100.0 - 99.6) < 1e-9
    ssp = COMMERCIAL_FERTILIZERS["ssp"]
    tsp = COMMERCIAL_FERTILIZERS["tsp"]
    assert abs(float(ssp["nutrient_pct"]) - 7.9) < 1e-9
    assert abs(float(tsp["nutrient_pct"]) - 20.1) < 1e-9


def test_2_crop_schedule_milho():
    crop = CROP_DATABASE["milho"]
    n, pd = 150, 10
    s = crop_schedule(crop, n, pd)
    # inativo antes do plantio e depois de 125 d
    assert bool(s["active"][0]) is False
    assert bool(s["active"][pd]) is True
    assert bool(s["active"][pd + 125]) is False
    # Kcb ini/mid/end (FAO-56 Tab. 17: 0.15/1.15/0.50)
    assert abs(float(s["kcb"][pd]) - 0.15) < 1e-9
    assert abs(float(s["kcb"][pd + 70]) - 1.15) < 1e-9
    assert abs(float(s["kcb"][pd + 124]) - 0.50) < 0.05
    # raiz 15 -> 40 cm
    assert abs(float(s["root_depth_cm"][pd]) - 15.0) < 1e-9
    assert abs(float(s["root_depth_cm"][pd + 55]) - 40.0) < 1e-9
    assert abs(float(s["root_depth_cm"][pd + 100]) - 40.0) < 1e-9
    # fração acumulada: F(0)=0, F(L)=1, F(L/2)~0.5
    assert abs(float(s["uptake_frac_cum"][pd]) - 0.0) < 1e-12
    assert abs(float(s["uptake_frac_cum"][pd + 125]) - 1.0) < 1e-12
    f_half = float(s["uptake_frac_cum"][pd + 62])
    assert abs(f_half - 0.5) < 0.06


def test_3_coluna_milho_evap_positiva():
    soil = SOIL_DATABASE["latossolo_medio"]
    crop = CROP_DATABASE["milho"]
    assert abs(float(crop.kc) - 1.05) < 1e-9
    cfg = SimulationConfig(depth_cm=100.0, total_days=7.0)
    sim = Hydrus1DSimulator(soil=soil, crop=crop, config=cfg)
    res = sim.run(
        initial_moisture_pct=80.0,
        fertilizer_dose_kg_ha=30.0,
        water_events=[(0.5, 0.3, 20.0)],
        et0_mm_day=4.0,
        nutrients=[{"symbol": "K", "name": "K", "dose_kg_ha": 30.0, "kd": 0.45}],
    )
    assert float(res.evap_cum_cm) > 0.0


def test_4_teto_soja_coluna():
    soil = SOIL_DATABASE["latossolo_medio"]
    crop = CROP_DATABASE["soja"]
    cfg = SimulationConfig(depth_cm=100.0, total_days=7.0)
    sim = Hydrus1DSimulator(soil=soil, crop=crop, config=cfg)
    res = sim.run(
        initial_moisture_pct=80.0,
        fertilizer_dose_kg_ha=300.0,
        water_events=[(0.5, 0.3, 60.0)],
        et0_mm_day=4.0,
        nutrients=[{"symbol": "N", "name": "N", "dose_kg_ha": 300.0, "kd": 0.0}],
    )
    nr = res.nutrient_results["N"]
    cap = float(nr["uptake_cap_kg_ha"])
    upt = float(nr["uptaken_kg_ha"])
    assert cap > 0.0
    assert upt <= cap * 1.005 + 1e-6
    assert bool(nr["uptake_capped"]) is True


def test_5_residual_balanço_inputs():
    soil = SOIL_DATABASE["latossolo_medio"]
    cfg = SimulationConfig(depth_cm=100.0, total_days=7.0)
    sim = Hydrus1DSimulator(soil=soil, crop=None, config=cfg)
    res = sim.run(
        initial_moisture_pct=80.0,
        fertilizer_dose_kg_ha=30.0,
        water_events=[(0.5, 0.3, 60.0)],
        et0_mm_day=4.0,
        nutrients=[{"symbol": "K", "name": "K", "dose_kg_ha": 30.0, "kd": 0.45}],
        initial_residual_mg_dm3={"K": 5.0},
    )
    nr = res.nutrient_results["K"]
    below = float(nr["leaching_ratio_pct"]) - float(nr["leached_bottom_pct"])
    total = (float(nr["retained_root_pct"]) + below + float(nr["leached_bottom_pct"])
             + float(nr["uptaken_pct"]) + float(nr["capsule_pct"]))
    assert abs(total - 100.0) <= 1.0
    assert abs(float(nr["retained_kg_ha"]) - float(nr["retained_root_pct"]) / 100.0 * float(nr["input_kg_ha"])) < 1e-6


def test_6_fechamento_hidrico_sazonal_schedule():
    soil = SOIL_DATABASE["latossolo_medio"]
    crop = CROP_DATABASE["milho"]
    n = 60
    sched = crop_schedule(crop, n, 0)
    water_events = [(float(d), 1.0, 5.0) for d in range(n)]
    et0 = [4.0] * n
    cfg = SimulationConfig(depth_cm=100.0, total_days=float(n))
    sim = Hydrus1DSimulator(soil=soil, crop=crop, config=cfg)
    res = sim.run(
        initial_moisture_pct=80.0,
        fertilizer_dose_kg_ha=30.0,
        water_events=water_events,
        et0_mm_day=et0,
        nutrients=[{"symbol": "K", "name": "K", "dose_kg_ha": 30.0, "kd": 0.45}],
        crop_schedule=sched,
    )
    assert abs(float(res.water_closure_pct)) < 2.0
