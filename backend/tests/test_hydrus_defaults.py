"""Padrões no estilo HYDRUS-1D, balanço nos cartões e exportador fiel."""

import os

import numpy as np
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import PlacementInput, SimulateRequest, SoluteInput
from app.service import _balances, _cycle_info, _run_core, _water_balance, write_hydrus_project
from hydrus_core.crop import CROP_DATABASE
from hydrus_core.hydrus_io import export_to_hydrus1d_project
from hydrus_core.hydrus_solver import Hydrus1DSimulator, SimulationConfig
from hydrus_core.soil_physics import SOIL_DATABASE
from hydrus_core.surface_bc import potential_partition_cm


def test_schema_defaults_sao_hydrus():
    req = SimulateRequest(soil_key="latossolo_medio", crop_key="soja")
    assert req.use_dual_kc is False
    assert req.growing_root is False
    assert req.bare_after_harvest is False
    assert req.uptake_cap is False


def test_particao_padrao_rroot_kc_et0_rsoil_0():
    crop = CROP_DATABASE["soja"]
    tp, ep = potential_partition_cm(crop, 4.0)
    assert abs(tp * 10.0 - float(crop.kc) * 4.0) < 1e-9
    assert ep == 0.0
    soil = SOIL_DATABASE["latossolo_medio"]
    sim = Hydrus1DSimulator(soil=soil, crop=crop, config=SimulationConfig(depth_cm=80, total_days=5))
    res = sim.run(
        initial_moisture_pct=100.0,
        fertilizer_dose_kg_ha=0.0,
        water_events=[(0.5, 0.3, 40.0)],
        et0_mm_day=4.0,
        water_only=True,
    )
    assert float(res.evap_cum_cm) < 0.05
    assert float(res.transp_cum_cm) > 0.5


def test_plantio_nao_vira_estabelecida_no_laudo():
    req = SimulateRequest(
        soil_key="latossolo_medio",
        crop_key="soja",
        crop_start_mode="planting",
        planting_day=1,
        total_days=30,
        rain_mm=50,
        solutes=[SoluteInput(symbol="K", name="Potássio", dose_kg_ha=30, kd=0.45)],
        placement=PlacementInput(mode="surface", application_day=0),
    )
    from app.service import _build_crop
    info = _cycle_info(req, _build_crop(req))
    txt = info["crop_start_txt"]
    assert "plantio" in txt
    assert "estabelecida com" not in txt
    assert "Kc constante" in txt


def test_cartoes_balanco_e_soluto(tmp_path):
    req = SimulateRequest(
        soil_key="latossolo_medio",
        crop_key="soja",
        crop_start_mode="planting",
        total_days=7,
        rain_mm=40,
        initial_moisture_pct=100,
        et0_mm_day=4,
        solutes=[SoluteInput(symbol="K", name="Potássio", dose_kg_ha=30, kd=0.45, dispersivity_cm=8)],
        placement=PlacementInput(mode="surface", application_day=0),
        print_days=[3, 7],
        obs_depths_cm=[10, 20],
    )
    results, soil, crop, root, rain, days = _run_core(req)
    wb = _water_balance(req, results, rain, days)
    err = wb.applied_mm - wb.runoff_mm - (wb.evap_mm or 0) - (wb.transp_mm or 0) - wb.drainage_mm - wb.storage_mm
    assert abs(err - wb.balance_error_mm) < 1e-6
    assert wb.infiltration_mm == wb.applied_mm - wb.runoff_mm
    assert abs(wb.balance_error_pct) < 5.0
    bal = _balances(req, results)[0]
    assert abs((bal.retained_kg_ha + bal.below_kg_ha) - bal.profile_kg_ha) < 1e-6
    assert abs(bal.mass_closure_pct) < 1.0
    # Umidade: o integral fecha com ΔS; um trecho fundo pode ficar acima do θ inicial.
    z = np.asarray(results.z)
    th0 = np.asarray(results.theta_profiles[0])
    th1 = np.asarray(results.theta_profiles[-1])
    storage = float(np.sum(th1 - th0) * (z[1] - z[0]) * 10.0)
    assert abs(storage - wb.storage_mm) < 0.05
    for series in results.obs_theta_series.values():
        arr = np.asarray(series, dtype=float)
        assert np.all(np.isfinite(arr))
        assert float(arr.max()) < float(soil.theta_s) + 0.05
    assert len(results.flux_times_days) > 2
    assert len(results.cum_infil_cm) == len(results.flux_times_days)
    out = write_hydrus_project(req, soil, crop, days, str(tmp_path))
    selector = open(os.path.join(out, "SELECTOR.IN"), encoding="utf-8").read()
    assert "-450.0" in selector and "-12000.0" in selector
    assert "POptm" in selector
    # POptm é a linha numérica seguinte ao rótulo.
    lines = selector.splitlines()
    i = next(n for n, line in enumerate(lines) if line.startswith("POptm"))
    assert abs(float(lines[i + 1]) - float(crop.h2)) < 1e-6
    atmos = open(os.path.join(out, "ATMOSPH.IN"), encoding="utf-8").read().splitlines()

    def _is_record(line: str) -> bool:
        bits = line.split()
        if len(bits) < 5:
            return False
        try:
            float(bits[0])
            float(bits[2])
            return True
        except ValueError:
            return False

    parts = next(ln.split() for ln in atmos if _is_record(ln))
    # tAtm Prec rSoil rRoot
    assert abs(float(parts[2])) < 1e-6
    assert abs(float(parts[3]) - float(crop.kc) * 4.0 / 10.0) < 1e-4
    prof = open(os.path.join(out, "PROFILE.DAT"), encoding="utf-8").read().splitlines()
    node = prof[4].split()
    assert abs(float(node[2]) - (-150.0)) < 5.0


def test_preview_tp_bate_com_a_particao():
    with TestClient(app) as client:
        r = client.post("/crops/preview", json={
            "soil_key": "latossolo_medio",
            "crop_key": "soja",
            "crop_start_mode": "planting",
            "total_days": 30,
            "et0_mm_day": 4.0,
            "solutes": [],
        })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode"] == "planting"
    assert abs(body["tp_mm_day"] - 4.0) < 1e-6
    assert abs(body["ep_mm_day"]) < 1e-9


def test_job_lamina_aceita_dias_e_nos():
    payload = {
        "soil_key": "latossolo_medio",
        "crop_key": "soja",
        "crop_start_mode": "planting",
        "total_days": 6,
        "rain_mm": 30,
        "initial_moisture_pct": 100,
        "et0_mm_day": 4,
        "print_days": [2, 6],
        "obs_depths_cm": [10, 30],
        "solutes": [{"symbol": "K", "name": "K", "dose_kg_ha": 10, "kd": 0.45}],
    }
    with TestClient(app) as client:
        created = client.post("/jobs", json=payload)
        assert created.status_code == 200, created.text
        job_id = created.json()["job_id"]
        status = client.get(f"/jobs/{job_id}?wait=25")
        assert status.status_code == 200
        body = status.json()
        assert body["status"] == "done", body
        wb = body["result"]["water_balance"]
        assert "infiltration_mm" in wb and "balance_error_pct" in wb
        sol = body["result"]["solutes"][0]
        assert "profile_kg_ha" in sol and "mass_closure_pct" in sol
        screen = body["result"]["screen"]
        assert screen["hydrus_fluxos"]
        zpath = client.get(f"/jobs/{job_id}/hydrus1d.zip")
        assert zpath.status_code == 200
        assert zpath.content[:2] == b"PK"
