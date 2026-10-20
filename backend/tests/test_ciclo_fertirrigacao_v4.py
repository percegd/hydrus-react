"""Testes v4 (backend): ciclo da cultura, umidade sazonal, C0 da fertirrigação e contabilidade."""

import time

from fastapi.testclient import TestClient

from app.climate import build_series_rows
from app.main import app
from app.schemas import PlacementInput, SimulateRequest, SoluteInput
from app.service import run_simulation


def _k_req(**overrides):
    base = {
        "soil_key": "latossolo_medio",
        "crop_key": "soja",
        "depth_cm": 100.0,
        "total_days": 7,
        "rain_mm": 60.0,
        "solutes": [
            {
                "symbol": "K",
                "name": "Potássio",
                "dose_kg_ha": 30.0,
                "kd": 0.45,
            }
        ],
    }
    base.update(overrides)
    return base


def test_planting_day_fora_do_intervalo_retorna_422() -> None:
    with TestClient(app) as client:
        # Série de 10 dias com plantio no dia 50.
        r = client.post(
            "/jobs",
            json=_k_req(rain_series=[1.0] * 10, planting_day=50),
        )
    assert r.status_code == 422, r.text
    detail = r.json()["detail"]
    assert any(e.get("field") == "planting_day" for e in detail), detail


def test_planting_day_zero_na_lamina_retorna_422() -> None:
    with TestClient(app) as client:
        r = client.post("/jobs", json=_k_req(planting_day=0))
    assert r.status_code == 422, r.text
    assert any(e.get("field") == "planting_day" for e in r.json()["detail"])


def test_fertirrigacao_c0_por_nutriente_e_applied_proximo_da_dose() -> None:
    req = SimulateRequest(
        soil_key="latossolo_medio",
        crop_key=None,
        total_days=7,
        rain_mm=60.0,
        placement=PlacementInput(
            mode="fertigation",
            fertigation_c0_mg_l=999.0,  # legado: ignorado no cálculo
            fertigation_pulse_days=0.0,
            application_day=0.0,
        ),
        solutes=[
            SoluteInput(symbol="N", name="Nitrato", dose_kg_ha=30.0, kd=0.0),
            SoluteInput(symbol="K", name="Potássio", dose_kg_ha=20.0, kd=0.45),
        ],
    )
    resp = run_simulation(req, with_plot=False)
    by_sym = {s.symbol: s for s in resp.solutes}
    # C0_i = dose_i × 100 / W_pulso (W = 60 mm): 50.0 e 33.3 mg/L.
    assert abs(float(by_sym["N"].fertigation_c0_mg_l) - 50.0) < 1e-9
    assert abs(float(by_sym["K"].fertigation_c0_mg_l) - 100.0 / 3.0) < 1e-9
    assert by_sym["N"].fertigation_c0_mg_l != by_sym["K"].fertigation_c0_mg_l
    # Massa injetada real ≈ dose (±10%).
    for sym, dose in (("N", 30.0), ("K", 20.0)):
        applied = float(by_sym[sym].dose_kg_ha)
        assert abs(applied - dose) / dose < 0.10, (sym, applied, dose)
        assert float(by_sym[sym].dose_input_kg_ha) == dose


def test_fertirrigacao_sem_agua_retorna_422() -> None:
    with TestClient(app) as client:
        r = client.post(
            "/jobs",
            json=_k_req(
                crop_key=None,
                total_days=7,
                rain_mm=0.0,
                placement={
                    "mode": "fertigation",
                    "fertigation_pulse_days": 2.0,
                    "application_day": 1.0,
                },
            ),
        )
    assert r.status_code == 422, r.text
    assert "sem água no período de injeção" in r.text


def test_serie_umidade_default_sem_delta_s_artificial() -> None:
    rain, et0, _year = build_series_rows("piracicaba_sp", "medio")

    def _stor(moist=None) -> float:
        kw = {} if moist is None else {"seasonal_initial_moisture_pct": moist}
        req = SimulateRequest(
            soil_key="latossolo_medio",
            crop_key=None,
            depth_cm=200.0,
            rain_series=list(rain),
            et0_series=list(et0),
            placement=PlacementInput(mode="surface", application_day=30.0),
            solutes=[SoluteInput(symbol="K", name="Potássio", dose_kg_ha=30.0, kd=0.45)],
            **kw,
        )
        return float(run_simulation(req, with_plot=False).water_balance.storage_mm)

    # Default (100% = CC): sem o ΔS artificial do início seco.
    assert abs(_stor(None)) < 80.0
    # Início seco (20%, regra antiga): ΔS artificial de +100 a +220 mm.
    assert _stor(20.0) > 100.0


def test_sem_solo_1d_no_laudo_e_passos_do_job() -> None:
    with TestClient(app) as client:
        created = client.post("/jobs", json=_k_req())
        assert created.status_code == 200, created.text
        job_id = created.json()["job_id"]
        deadline = time.monotonic() + 240
        status = None
        while time.monotonic() < deadline:
            status = client.get(f"/jobs/{job_id}").json()
            if status["status"] in {"done", "failed"}:
                break
            time.sleep(0.5)
        assert status is not None and status["status"] == "done", status
        report = client.get(f"/jobs/{job_id}/report").json()["report_markdown"]
        steps = client.get(f"/jobs/{job_id}/steps").json()["steps_markdown"]
    for txt, label in ((report, "report_markdown"), (steps, "steps_markdown")):
        assert "solo 1d" not in txt.lower(), f"'Solo 1D' em {label}"
