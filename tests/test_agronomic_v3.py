"""Correções de cálculo da revisão agronômica v3 (rápido)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from backend.app import service as svc
from backend.app.schemas import PlacementInput, SimulateRequest, SoluteInput
from backend.app.validation import validate_request


def _col_req(**kw):
    base = dict(
        soil_key="latossolo_medio",
        crop_key=None,
        depth_cm=100.0,
        total_days=5.0,
        rain_mm=60.0,
        rain_series=None,
        initial_moisture_pct=80.0,
        et0_mm_day=4.0,
        placement=PlacementInput(mode="surface", application_day=0.0),
        solutes=[SoluteInput(symbol="K", name="Potássio", dose_kg_ha=30.0, kd=0.45)],
    )
    base.update(kw)
    return SimulateRequest(**base)


def test_a_column_single_water_event(monkeypatch):
    req = _col_req(rain_mm=60.0, total_days=5.0)
    captured = {}

    from hydrus_core import hydrus_solver as hs

    orig_run = hs.Hydrus1DSimulator.run

    def fake_run(self, *a, **k):
        captured["water_events"] = list(k.get("water_events", []))
        return orig_run(self, *a, **k)

    monkeypatch.setattr(hs.Hydrus1DSimulator, "run", fake_run)
    svc._run_core(req)
    assert captured["water_events"] == [(0.5, 0.3, 60.0)]


def test_b_fertigation_effective_dose():
    req = _col_req(
        placement=PlacementInput(
            mode="fertigation", fertigation_c0_mg_l=20.0,
            fertigation_pulse_days=2.0, application_day=0.0,
        ),
        solutes=[SoluteInput(symbol="N", name="Nitrato", dose_kg_ha=30.0, kd=0.0)],
    )
    results, soil, crop, root_depth, total_rain, total_days = svc._run_core(req)
    bals = svc._balances(req, results)
    assert len(bals) == 1
    b = bals[0]
    applied = float(results.nutrient_results["N"]["applied_kg_ha"])
    assert applied != 30.0
    assert abs(b.dose_kg_ha - applied) < 1e-9
    assert b.dose_input_kg_ha == 30.0
    assert b.is_fertigation is True


def test_c_controlled_capsule_closure():
    req = _col_req(
        total_days=3.0,
        solutes=[SoluteInput(symbol="K", name="Potássio", dose_kg_ha=30.0, kd=0.45,
                             release_type="controlled", release_days=60.0)],
    )
    results, soil, crop, root_depth, total_rain, total_days = svc._run_core(req)
    bals = svc._balances(req, results)
    b = bals[0]
    assert b.capsule_pct > 0.0
    total = (b.retained_root_pct + b.below_profile_pct + b.bottom_pct
             + b.uptaken_pct + b.capsule_pct)
    assert abs(total - 100.0) <= 1.0


def test_d_sim_params_fertilizer():
    req = _col_req()
    results, soil, crop, root_depth, total_rain, total_days = svc._run_core(req)
    p = svc._sim_params(req, results, soil, crop, root_depth, total_rain, total_days)
    assert p["fertilizer_name"] == "Dose Direta do Elemento"
    assert abs(float(p["gross_dose"]) - 30.0) < 1e-9

    req2 = _col_req(
        solutes=[SoluteInput(symbol="K", name="Potássio", dose_kg_ha=104.8, kd=0.45)],
        fertilizer={"fert_key": "kcl", "gross_dose": 200.0},
    )
    results2, soil2, crop2, rd2, tr2, td2 = svc._run_core(req2)
    p2 = svc._sim_params(req2, results2, soil2, crop2, rd2, tr2, td2)
    assert abs(float(p2["gross_dose"]) - 200.0) < 1e-9
    assert p2["fertilizer_name"] == "Cloreto de Potássio - KCl (00-00-60)"


def test_e_steps_text_bugs():
    req = _col_req()
    results, soil, crop, root_depth, total_rain, total_days = svc._run_core(req)
    md = svc.build_steps_markdown(req, results, soil, crop, root_depth, total_rain, total_days)
    assert "cm\\text{ cm}" not in md
    assert "..\n" not in md


def test_f_validation():
    bad_mode = _col_req(placement=PlacementInput(mode="xyz", application_day=0.0))
    issues = validate_request(bad_mode)
    assert any("Posicionamento desconhecido" in i["message"] for i in issues)
    late = _col_req(total_days=7.0,
                    placement=PlacementInput(mode="surface", application_day=30.0))
    issues2 = validate_request(late)
    assert any("deve ser menor que a duração do ensaio" in i["message"] for i in issues2)


def test_g_water_closure_column():
    req = _col_req()
    results, soil, crop, root_depth, total_rain, total_days = svc._run_core(req)
    wb = svc._water_balance(req, results, total_rain, total_days)
    assert wb.evap_mm is not None and wb.transp_mm is not None
    resid = (wb.applied_mm - wb.evap_mm - wb.transp_mm
             - wb.drainage_mm - wb.runoff_mm - wb.storage_mm)
    assert abs(resid) < 0.03 * max(wb.applied_mm, 1e-9)


def test_h_seasonal_multisolute_closure_line():
    import re
    n_days = 10
    req = SimulateRequest(
        soil_key="latossolo_medio", crop_key="soja", depth_cm=100.0,
        rain_series=[5.0] * n_days, et0_series=[4.0] * n_days,
        placement=PlacementInput(mode="surface", application_day=0.0),
        solutes=[
            SoluteInput(symbol="N", name="Nitrato", dose_kg_ha=30.0, kd=0.0),
            SoluteInput(symbol="K", name="Potássio", dose_kg_ha=30.0, kd=0.45),
        ],
    )
    results, soil, crop, root_depth, total_rain, total_days = svc._run_core(req)
    report = svc._seasonal_solute_report(req, results, soil, crop, root_depth, total_rain, total_days)
    assert crop is not None
    for sym in ("N", "K"):
        line = next(l for l in report.splitlines() if l.startswith(f"* **{sym}**"))
        nums = [float(v) for v in re.findall(r"(\d+(?:\.\d+)?)%", line)]
        # retido + abaixo + fundo + absorvido (+ grânulo)
        assert abs(sum(nums) - 100.0) <= 2.0, f"{sym}: {line} -> {nums}"
        assert "absorvido" in line


def test_i_finishing_texts_column():
    # (2) grânulo no laudo de coluna: texto novo, sem "| no grânulo".
    req = _col_req(
        total_days=3.0,
        solutes=[SoluteInput(symbol="K", name="Potássio", dose_kg_ha=30.0, kd=0.45,
                              release_type="controlled", release_days=60.0)],
    )
    results, soil, crop, root_depth, total_rain, total_days = svc._run_core(req)
    report = svc.build_report(req, results, soil, crop, root_depth, total_rain, total_days)
    assert "Ainda no grânulo (não liberado):" in report
    assert "| no grânulo" not in report

    # (3) fertirrigação: dose efetiva injetada no cabeçalho.
    reqf = _col_req(
        placement=PlacementInput(
            mode="fertigation", fertigation_c0_mg_l=20.0,
            fertigation_pulse_days=2.0, application_day=0.0,
        ),
        solutes=[SoluteInput(symbol="N", name="Nitrato", dose_kg_ha=30.0, kd=0.0)],
    )
    rf, soilf, cropf, rdf, trf, tdf = svc._run_core(reqf)
    repf = svc.build_report(reqf, rf, soilf, cropf, rdf, trf, tdf)
    assert "Dose Aplicada (injetada)" in repf

    # (5a) dose direta: sem conversão por garantia.
    reqd = _col_req()
    rd_, soild, cropd, rdd, trd, tdd = svc._run_core(reqd)
    mdd = svc.build_steps_markdown(reqd, rd_, soild, cropd, rdd, trd, tdd)
    assert "sem conversão por garantia" in mdd
    assert "Dose Informada (elementar)" in mdd

    # (5b) fertilizante comercial do catálogo: mantém Garantia MAPA.
    reqk = _col_req(
        solutes=[SoluteInput(symbol="K", name="Potássio", dose_kg_ha=104.8, kd=0.45)],
        fertilizer={"fert_key": "kcl", "gross_dose": 200.0},
    )
    rk, soilk, cropk, rdk, trk, tdk = svc._run_core(reqk)
    mdk = svc.build_steps_markdown(reqk, rk, soilk, cropk, rdk, trk, tdk)
    assert "Garantia MAPA" in mdk
