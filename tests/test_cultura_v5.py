"""v5 — Situação da cultura no início (planting/established/perennial, HYDRUS equiv, teto restante)."""

import math

from fastapi.testclient import TestClient

from hydrus_core.crop import CROP_DATABASE, crop_schedule
from hydrus_core.soil_physics import SOIL_DATABASE
from hydrus_core.hydrus_solver import Hydrus1DSimulator, SimulationConfig


def _milho():
    return CROP_DATABASE["milho"]


def test_schedule_planting_antes_depois_colheita_bare():
    c = _milho()
    n, pd = 150, 10
    s = crop_schedule(c, n, pd, mode="planting", after_harvest="bare")
    assert bool(s["active"][0]) is False
    assert bool(s["active"][pd]) is True
    assert s["stage"][0] == "fora do ciclo"
    assert s["stage"][pd] == "inicial"
    # após L=125: solo nu
    assert bool(s["active"][pd + 125]) is False
    assert float(s["uptake_frac_cum"][pd + 125]) == 1.0
    he = s["hydrus_equiv"]
    assert he["tRMin"] == float(pd) and he["tRHarv"] == float(pd + 125.0)
    assert he["lRoot"] is True and he["iRootIn"] == 1


def test_schedule_repeat_reinicia():
    c = _milho()
    s = crop_schedule(c, 260, 0, mode="planting", after_harvest="repeat")
    # segundo ciclo ativo (tau=130 -> tin=5)
    assert bool(s["active"][130]) is True
    assert float(s["uptake_frac_cum"][130]) > 1.0
    # raiz reinicia no ciclo novo
    assert float(s["root_depth_cm"][130]) < float(s["root_depth_cm"][60])
    assert s["hydrus_equiv"]["tRPeriod"] == 125.0


def test_schedule_established_tau0():
    c = _milho()
    s = crop_schedule(c, 30, -50, mode="established")
    assert bool(s["active"][0]) is True
    assert s["stage"][0] == "desenvolvimento"
    # tau no dia 0 = 50
    assert abs(float(s["root_depth_cm"][0]) - (15.0 + (50.0 / 55.0) * 25.0)) < 1e-9
    assert s["hydrus_equiv"]["tRMin"] == -50.0


def test_schedule_perennial_constante():
    c = CROP_DATABASE["cafe"]
    s = crop_schedule(c, 10, 0, mode="perennial")
    assert all(bool(a) for a in s["active"])
    assert all(st == "perene" for st in s["stage"])
    assert max(float(v) for v in s["kcb"]) - min(float(v) for v in s["kcb"]) < 1e-12
    assert abs(float(s["uptake_frac_cum"][5]) - 5.0 / 365.0) < 1e-12
    assert s["hydrus_equiv"]["lRoot"] is False


def test_logistico_L0_e_meio():
    c = _milho()
    L = 125.0
    s = crop_schedule(c, 130, 0, mode="planting", root_growth="logistic")
    assert abs(float(s["root_depth_cm"][0]) - 15.0) < 1e-9
    # L(L/2) ~= (Lm+L0)/2 (tau=62 discreto -> tolerância)
    assert abs(float(s["root_depth_cm"][62]) - 27.5) < 0.3
    assert s["hydrus_equiv"]["iRootIn"] == 2
    assert s["hydrus_equiv"]["r"] is not None


def test_logistico_iRFak0_passa_pelo_ponto():
    c = _milho()
    s = crop_schedule(c, 80, -50, mode="established", root_growth="logistic",
                      measured_root_cm=30.0)
    assert abs(float(s["root_depth_cm"][0]) - 30.0) < 1e-9
    assert s["hydrus_equiv"]["iRFak"] == 0


def test_measured_linear():
    c = _milho()
    s = crop_schedule(c, 30, -50, mode="established", root_growth="linear",
                      measured_root_cm=30.0)
    assert abs(float(s["root_depth_cm"][0]) - 30.0) < 1e-9
    # cresce até 40 no fim de Ldev (tau=55)
    assert float(s["root_depth_cm"][-1]) <= 40.0 + 1e-9
    # após o fim do crescimento, constante = máx
    s2 = crop_schedule(c, 30, -60, mode="established", root_growth="linear",
                       measured_root_cm=40.0)
    assert abs(float(s2["root_depth_cm"][0]) - 40.0) < 1e-9


def test_teto_usa_demanda_restante():
    from hydrus_core.crop import _logistic_f
    c = _milho()
    dem = float(c.uptake_demand_kg_ha["N"])
    F = lambda t: _logistic_f(t, 125.0)
    cap_restante = dem * (F(80) - F(50))
    cap_absoluta = dem * F(80)
    assert cap_restante < cap_absoluta
    # solver reporta a restante
    soil = SOIL_DATABASE["latossolo_medio"]
    sched = crop_schedule(c, 31, -50, mode="established")
    cfg = SimulationConfig(depth_cm=100.0, total_days=30.0)
    sim = Hydrus1DSimulator(soil=soil, crop=c, config=cfg)
    res = sim.run(initial_moisture_pct=80.0, fertilizer_dose_kg_ha=300.0,
                  water_events=[(0.5, 0.3, 60.0)], et0_mm_day=4.0,
                  nutrients=[{"symbol": "N", "name": "N", "dose_kg_ha": 300.0, "kd": 0.0}],
                  crop_schedule=sched)
    cap = float(res.nutrient_results["N"]["uptake_cap_kg_ha"])
    assert abs(cap - cap_restante) / max(cap_restante, 1e-9) < 0.05, (cap, cap_restante)


def test_teto_interpolado_primeiro_dia_sem_corte():
    # Teto com interpolação linear de F(x): sem degrau diário (milho 50 DAP,
    # Lâmina 30 d / 100 mm, N 60 kg/ha; ET0 moderado p/ não limitar pela demanda).
    # Antes: _idx_end=int(t+dt) zerava o teto o 1º dia inteiro (F(0)-F(0)).
    c = _milho()
    soil = SOIL_DATABASE["latossolo_medio"]
    sched = crop_schedule(c, 31, -50, mode="established")
    _ev = [(0.5, 0.3, 100.0)]
    _nut = [{"symbol": "N", "name": "N", "dose_kg_ha": 60.0, "kd": 0.0}]
    cfg1 = SimulationConfig(depth_cm=100.0, total_days=1.0)
    res1 = Hydrus1DSimulator(soil=soil, crop=c, config=cfg1).run(
        initial_moisture_pct=80.0, fertilizer_dose_kg_ha=60.0,
        water_events=_ev, et0_mm_day=2.0, nutrients=_nut, crop_schedule=sched)
    n1 = res1.nutrient_results["N"]
    assert float(n1["uptaken_kg_ha"]) > 0.0
    assert bool(n1["uptake_capped"]) is False
    cfg30 = SimulationConfig(depth_cm=100.0, total_days=30.0)
    res30 = Hydrus1DSimulator(soil=soil, crop=c, config=cfg30).run(
        initial_moisture_pct=80.0, fertilizer_dose_kg_ha=60.0,
        water_events=_ev, et0_mm_day=2.0, nutrients=_nut, crop_schedule=sched)
    n30 = res30.nutrient_results["N"]
    _cap = float(n30["uptake_cap_kg_ha"])
    _upt = float(n30["uptaken_kg_ha"])
    assert _upt < 0.5 * _cap
    assert bool(n30["uptake_capped"]) is False


def _run_case(crop_key, total_days, rain_mm=None, rain_series=None, **kw):
    from backend.app.schemas import SimulateRequest, PlacementInput, SoluteInput
    from backend.app.service import _run_core
    solutes = [SoluteInput(symbol="N", name="N", dose_kg_ha=30.0, kd=0.0),
               SoluteInput(symbol="K", name="K", dose_kg_ha=30.0, kd=0.45)]
    req = SimulateRequest(soil_key="latossolo_medio", crop_key=crop_key,
                          depth_cm=100.0, total_days=float(total_days),
                          rain_mm=float(rain_mm or 0.0),
                          rain_series=rain_series,
                          placement=PlacementInput(mode="surface", application_day=0.0),
                          solutes=solutes, **kw)
    return _run_core(req)


def _assert_closure(results):
    for sym, d in results.nutrient_results.items():
        assert abs(float(d["mass_closure_pct"])) < 1.0, (sym, d["mass_closure_pct"])
    assert abs(float(results.water_closure_pct)) < 2.0


def test_fecho_milho_adulto_lamina():
    results, *_ = _run_case("milho", 30, rain_mm=60.0,
                            crop_start_mode="established", crop_age_dap=50.0)
    _assert_closure(results)


def test_fecho_milho_plantio_dia1_lamina():
    results, *_ = _run_case("milho", 30, rain_mm=60.0,
                            crop_start_mode="planting", planting_day=1)
    _assert_closure(results)


def test_fecho_cafe_serie_curta():
    rain = [2.0] * 60
    et0 = [4.0] * 60
    results, *_ = _run_case("cafe", 60, rain_series=rain,
                            crop_start_mode="perennial")
    _assert_closure(results)


def test_fecho_cana_repeat():
    rain = [2.0] * 60
    results, *_ = _run_case("cana_de_acucar", 60, rain_series=rain,
                            crop_start_mode="planting", after_harvest="repeat")
    _assert_closure(results)


def test_preview_endpoint():
    from backend.app.main import app
    with TestClient(app) as client:
        r = client.post("/crops/preview", json={
            "soil_key": "latossolo_medio", "crop_key": "milho",
            "depth_cm": 100.0, "total_days": 30, "rain_mm": 60.0,
            "crop_start_mode": "established", "crop_age_dap": 50.0,
            "solutes": [],
        })
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["stage_day1"] and j["kcb_day1"] is not None
    assert "tRMin" in (j["hydrus_equiv"] or {})


def test_validacoes_422():
    from backend.app.main import app
    base = {"soil_key": "latossolo_medio", "crop_key": "milho", "depth_cm": 100.0,
            "total_days": 10, "rain_mm": 60.0,
            "solutes": [{"symbol": "N", "name": "N", "dose_kg_ha": 10.0, "kd": 0.0}]}
    with TestClient(app) as client:
        r = client.post("/jobs", json={**base, "crop_age_dap": 200.0,
                                       "crop_start_mode": "established"})
        assert r.status_code == 422 and any(e.get("field") == "crop_age_dap" for e in r.json()["detail"])
        r = client.post("/jobs", json={**base, "planting_day": 50})
        assert r.status_code == 422 and any(e.get("field") == "planting_day" for e in r.json()["detail"])
        r = client.post("/jobs", json={**base, "measured_root_depth_cm": 500.0,
                                       "crop_start_mode": "established"})
        assert r.status_code == 422
        r = client.post("/jobs", json={**base, "stage_lengths_days": [1, 2, 3]})
        assert r.status_code == 422
        r = client.post("/jobs", json={**base, "kcb_mid": 9.0})
        assert r.status_code == 422


def test_laudo_contem_hydrus():
    from backend.app.schemas import SimulateRequest, PlacementInput, SoluteInput
    from backend.app.service import _run_core, build_report
    req = SimulateRequest(soil_key="latossolo_medio", crop_key="milho",
                          depth_cm=100.0, total_days=10, rain_mm=60.0,
                          placement=PlacementInput(mode="surface", application_day=0.0),
                          solutes=[SoluteInput(symbol="N", name="N", dose_kg_ha=10.0, kd=0.0)],
                          crop_start_mode="established", crop_age_dap=50.0)
    results, soil, crop, rd, tr, td = _run_core(req)
    rep = build_report(req, results, soil, crop, rd, tr, td)
    assert "HYDRUS-1D" in rep and "tRMin" in rep


def _mk_req(crop_key, **kw):
    from backend.app.schemas import SimulateRequest, PlacementInput, SoluteInput
    base = dict(soil_key="latossolo_medio", crop_key=crop_key,
                depth_cm=100.0, total_days=10, rain_mm=60.0,
                placement=PlacementInput(mode="surface", application_day=0.0),
                solutes=[SoluteInput(symbol="N", name="N", dose_kg_ha=10.0, kd=0.0)])
    base.update(kw)
    return SimulateRequest(**base)


def test_laudo_perene_kcb_estadio_sem_trmin():
    from backend.app.service import _build_crop, _cycle_info
    req = _mk_req("cafe", crop_start_mode="perennial")
    crop = _build_crop(req)
    info = _cycle_info(req, crop)
    txt = info["crop_start_txt"]
    assert "0.90" in txt, txt
    assert "perene" in txt.lower(), txt
    assert "Kcb no dia 1 —" not in txt, txt
    hyd = info["hydrus_txt"]
    assert "lRoot=False" in hyd, hyd
    assert "tRMin" not in hyd, hyd


def test_laudo_logistico_max_periodo_cultura_e_nota():
    from backend.app.service import _build_crop, _cycle_info
    from hydrus_core.crop import _verhulst_root, _r_logistic_iRFak1
    req = _mk_req("milho", crop_start_mode="established", crop_age_dap=50.0,
                  root_growth_model="logistic")
    crop = _build_crop(req)
    info = _cycle_info(req, crop)
    txt = info["crop_start_txt"]
    assert "máx. no período" in txt, txt
    assert "máx. da cultura 40 cm" in txt, txt
    assert "tempo infinito" in txt and "eq. 2.22" in txt, txt
    r = _r_logistic_iRFak1(15.0, 40.0, 125.0)
    exp = _verhulst_root(125.0, 15.0, 40.0, r)
    assert f"~{exp:.0f} cm na colheita" in txt, (txt, exp)


def test_laudo_linear_sem_nota_logistica():
    from backend.app.service import _build_crop, _cycle_info
    req = _mk_req("milho", crop_start_mode="established", crop_age_dap=50.0,
                  root_growth_model="linear")
    crop = _build_crop(req)
    info = _cycle_info(req, crop)
    txt = info["crop_start_txt"]
    assert "máx. no período" in txt and "máx. da cultura 40 cm" in txt, txt
    assert "tempo infinito" not in txt, txt


def test_preview_cafe_perennial_usa_schedule():
    from backend.app.main import app
    with TestClient(app) as client:
        r = client.post("/crops/preview", json={
            "soil_key": "latossolo_medio", "crop_key": "cafe",
            "depth_cm": 100.0, "total_days": 30, "rain_mm": 60.0,
            "crop_start_mode": "perennial",
            "solutes": [],
        })
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["stage_day1"] == "perene", j
    assert abs(float(j["kcb_day1"]) - 0.90) < 1e-9, j
    assert j["ke_day1"] is not None, j
    assert abs(float(j["root_day1_cm"]) - 70.0) < 1e-9, j
    assert bool(j["active_day1"]) is True, j
    assert (j["hydrus_equiv"] or {}).get("lRoot") is False, j
    # teto linear: demanda anual × dias/365 (N 150 × 30/365)
    exp_n = 150.0 * 30.0 / 365.0
    assert abs(float(j["remaining_demand_kg_ha"]["N"]) - exp_n) < 1e-6, j
    assert j["harvest_day_cal"] is None, j
    assert j["dap_effective"] is None, j
    assert j["mode"] == "perennial", j


def test_preview_cana_perennial():
    from backend.app.main import app
    with TestClient(app) as client:
        r = client.post("/crops/preview", json={
            "soil_key": "latossolo_medio", "crop_key": "cana_de_acucar",
            "depth_cm": 100.0, "total_days": 30, "rain_mm": 60.0,
            "crop_start_mode": "perennial",
            "solutes": [],
        })
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["stage_day1"] == "perene", j
    assert abs(float(j["kcb_day1"]) - 1.20) < 1e-9, j
    assert j["ke_day1"] is not None, j
    assert abs(float(j["root_day1_cm"]) - 80.0) < 1e-9, j
    assert (j["hydrus_equiv"] or {}).get("lRoot") is False, j
    exp_n = 140.0 * 30.0 / 365.0
    assert abs(float(j["remaining_demand_kg_ha"]["N"]) - exp_n) < 1e-6, j
    assert j["harvest_day_cal"] is None, j
    assert j["dap_effective"] is None, j


def test_preview_cana_established_repeat():
    from backend.app.main import app
    with TestClient(app) as client:
        r = client.post("/crops/preview", json={
            "soil_key": "latossolo_medio", "crop_key": "cana_de_acucar",
            "depth_cm": 100.0, "total_days": 30, "rain_mm": 60.0,
            "crop_start_mode": "established", "crop_age_dap": 150.0,
            "solutes": [],
        })
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["stage_day1"] == "médio", j
    assert abs(float(j["kcb_day1"]) - 1.20) < 1e-9, j
    assert bool(j["active_day1"]) is True, j
    assert abs(float(j["root_day1_cm"]) - 80.0) < 1e-9, j
    assert abs(float(j["dap_effective"]) - 150.0) < 1e-9, j
    assert abs(float(j["harvest_day_cal"]) - 215.0) < 1e-9, j
    assert (j["hydrus_equiv"] or {}).get("lRoot") is True, j
    # teto logístico restante (0 < restante < demanda total N 140)
    rem_n = float(j["remaining_demand_kg_ha"]["N"])
    assert 0.0 < rem_n < 140.0, j
