"""Testes de acompanhamento: runtime preso, renovação de TTL e erros 410."""

import os
import shutil
import time

import pytest
from fastapi.testclient import TestClient

from app import main


@pytest.fixture
def clean_jobs():
    """Limpa os jobs falsos e os diretórios criados durante o teste."""
    with main._jobs_lock:
        main._jobs.clear()
    before = set(os.listdir(main._jobs_root)) if os.path.isdir(main._jobs_root) else set()
    yield
    with main._jobs_lock:
        main._jobs.clear()
    after = set(os.listdir(main._jobs_root)) if os.path.isdir(main._jobs_root) else set()
    for name in after - before:
        shutil.rmtree(os.path.join(main._jobs_root, name), ignore_errors=True)


def _base_payload(**overrides) -> dict:
    payload = {
        "soil_key": "latossolo_medio",
        "crop_key": "soja",
        "total_days": 7,
        "rain_mm": 60.0,
        "solutes": [
            {"symbol": "K", "name": "Potássio", "dose_kg_ha": 60.0, "kd": 1.0}
        ],
    }
    payload.update(overrides)
    return payload


def test_running_job_exceeds_max_runtime_becomes_failed(monkeypatch, clean_jobs) -> None:
    monkeypatch.setattr(main, "JOB_MAX_RUNTIME_S", 1800.0)
    monkeypatch.setattr(main, "JOB_TTL_S", 3600.0)
    job_id = "runtime-stuck"
    t0 = time.time() - (main.JOB_MAX_RUNTIME_S + 10.0)
    with main._jobs_lock:
        main._jobs[job_id] = {
            "status": "running",
            "t0": t0,
            "t_end": None,
            "result": None,
            "error": None,
        }

    with TestClient(main.app) as client:
        response = client.get(f"/jobs/{job_id}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "failed"
    assert "Tempo máximo" in body["error"]


def test_done_report_renews_t_end(monkeypatch, clean_jobs) -> None:
    monkeypatch.setattr(main, "JOB_TTL_S", 3600.0)
    job_id = "report-renew"
    path = os.path.join(main._jobs_root, job_id)
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, "laudo.md"), "w", encoding="utf-8") as f:
        f.write("laudo")

    old_t_end = time.time() - 600.0
    with main._jobs_lock:
        main._jobs[job_id] = {
            "status": "done",
            "t0": old_t_end,
            "t_end": old_t_end,
            "result": None,
            "error": None,
        }

    with TestClient(main.app) as client:
        response = client.get(f"/jobs/{job_id}/report")

    assert response.status_code == 200, response.text
    with main._jobs_lock:
        assert main._jobs[job_id]["t_end"] > old_t_end + 1.0


def test_unknown_job_excel_and_report_return_410(clean_jobs) -> None:
    with TestClient(main.app) as client:
        excel = client.get("/jobs/nao-existe/excel")
        report = client.get("/jobs/nao-existe/report")

    assert excel.status_code == 410, excel.text
    assert "expirado" in excel.json()["detail"]
    assert report.status_code == 410, report.text
    assert "expirado" in report.json()["detail"]


def test_done_job_with_missing_excel_returns_410(monkeypatch, clean_jobs) -> None:
    monkeypatch.setattr(main, "JOB_TTL_S", 3600.0)
    job_id = "excel-missing"
    now = time.time()
    with main._jobs_lock:
        main._jobs[job_id] = {
            "status": "done",
            "t0": now,
            "t_end": now,
            "result": None,
            "error": None,
            "excel_path": os.path.join(main._jobs_root, job_id, "nao_existe.xlsx"),
        }

    with TestClient(main.app) as client:
        response = client.get(f"/jobs/{job_id}/excel")

    assert response.status_code == 410, response.text
    assert "expirado" in response.json()["detail"]


def test_simulate_unknown_soil_has_no_duplicate_messages(clean_jobs) -> None:
    payload = _base_payload(soil_key="solo_inexistente")
    with TestClient(main.app) as client:
        response = client.post("/simulate", json=payload)

    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert isinstance(detail, list) and detail
    unique = {(d["field"], d["message"]) for d in detail}
    assert len(detail) == len(unique)
