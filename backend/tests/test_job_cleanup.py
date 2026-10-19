"""Testes da limpeza de jobs (TTL, limite MAX_JOBS e 404 de job expirado)."""

import os
import time

import pytest
from fastapi.testclient import TestClient

from app import main


@pytest.fixture
def clean_jobs():
    yield
    with main._jobs_lock:
        main._jobs.clear()


def _make_job(status: str, t_end: float | None, t0: float | None = None) -> dict:
    return {
        "status": status,
        "t0": time.time() if t0 is None else t0,
        "t_end": t_end,
        "result": None,
        "error": None,
    }


def _make_job_dir(job_id: str) -> str:
    path = os.path.join(main._jobs_root, job_id)
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, "laudo.md"), "w", encoding="utf-8") as f:
        f.write("laudo")
    return path


def test_done_job_past_ttl_is_removed_with_directory(monkeypatch, clean_jobs) -> None:
    monkeypatch.setattr(main, "JOB_TTL_S", 60.0)
    job_id = "ttl-done-old"
    path = _make_job_dir(job_id)
    with main._jobs_lock:
        main._jobs[job_id] = _make_job("done", t_end=time.time() - 120.0)

    main._cleanup_jobs()

    with main._jobs_lock:
        assert job_id not in main._jobs
    assert not os.path.exists(path)


def test_running_job_past_ttl_is_not_removed(monkeypatch, clean_jobs) -> None:
    monkeypatch.setattr(main, "JOB_TTL_S", 60.0)
    job_id = "ttl-running-old"
    with main._jobs_lock:
        main._jobs[job_id] = _make_job("running", t_end=None, t0=time.time() - 120.0)

    main._cleanup_jobs()

    with main._jobs_lock:
        assert job_id in main._jobs
        assert main._jobs[job_id]["status"] == "running"


def test_max_jobs_removes_oldest_done(monkeypatch, clean_jobs) -> None:
    monkeypatch.setattr(main, "JOB_TTL_S", 3600.0)
    monkeypatch.setattr(main, "MAX_JOBS", 2)
    now = time.time()
    jobs = {
        "max-oldest": now - 300.0,
        "max-middle": now - 200.0,
        "max-newest": now - 100.0,
    }
    for job_id, t_end in jobs.items():
        _make_job_dir(job_id)
        with main._jobs_lock:
            main._jobs[job_id] = _make_job("done", t_end=t_end)

    main._cleanup_jobs()

    with main._jobs_lock:
        assert len(main._jobs) == 2
        assert "max-oldest" not in main._jobs
        assert "max-middle" in main._jobs
        assert "max-newest" in main._jobs
    assert not os.path.exists(os.path.join(main._jobs_root, "max-oldest"))


def test_get_unknown_job_returns_404_expired(clean_jobs) -> None:
    with TestClient(main.app) as client:
        response = client.get("/jobs/id-inexistente")

    assert response.status_code == 404, response.text
    assert "expirado" in response.json()["detail"]
