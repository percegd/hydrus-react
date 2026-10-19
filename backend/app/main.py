"""API Hydrus — FastAPI fina sobre o hydrus-core."""

import os
import shutil
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from hydrus_core.crop import CROP_DATABASE
from hydrus_core.soil_physics import SOIL_DATABASE

from .schemas import JobCreated, JobStatus, SimulateRequest, SimulateResponse
from .service import execute_job, run_simulation
from .validation import validate_request

app = FastAPI(title="Hydrus API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_pool = ThreadPoolExecutor(max_workers=2)
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()
_jobs_root = tempfile.mkdtemp(prefix="hydrus-jobs-")


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(float(os.environ.get(name, default)))
    except (TypeError, ValueError):
        return default


# Variáveis de módulo (sobrescrevíveis em testes).
JOB_TTL_S: float = _env_float("HYDRUS_JOB_TTL_S", 3600)
MAX_JOBS: int = _env_int("HYDRUS_MAX_JOBS", 100)


def _cleanup_jobs() -> None:
    """Remove jobs terminados expirados (TTL) ou excedentes (MAX), apagando o diretório."""
    ttl = JOB_TTL_S
    max_jobs = MAX_JOBS
    now = time.time()
    expired: list[str] = []
    with _jobs_lock:
        for job_id, job in list(_jobs.items()):
            if job.get("status") not in ("done", "failed"):
                continue
            t_end = job.get("t_end", job.get("t0", now))
            try:
                ref = float(t_end)
            except (TypeError, ValueError):
                ref = now
            if now - ref > ttl:
                expired.append(job_id)
        for job_id in expired:
            _jobs.pop(job_id, None)
        # Limite de tamanho: remover terminados mais antigos primeiro.
        if len(_jobs) > max_jobs:
            finished = [
                (job.get("t_end", job.get("t0", 0)), job_id)
                for job_id, job in _jobs.items()
                if job.get("status") in ("done", "failed")
            ]
            finished.sort(key=lambda kv: kv[0] or 0)
            overflow = len(_jobs) - max_jobs
            for _, job_id in finished[:overflow]:
                _jobs.pop(job_id, None)
                expired.append(job_id)
    for job_id in expired:
        shutil.rmtree(os.path.join(_jobs_root, job_id), ignore_errors=True)


def _execute(job_id: str, req: SimulateRequest) -> None:
    import os

    with _jobs_lock:
        _jobs[job_id]["status"] = "running"
    try:
        resp, excel_path, _report = execute_job(req, os.path.join(_jobs_root, job_id))
        with _jobs_lock:
            _jobs[job_id].update(status="done", result=resp, excel_path=excel_path, t_end=time.time())
    except Exception as exc:  # noqa: BLE001 — erro vira status consultável
        with _jobs_lock:
            _jobs[job_id].update(status="failed", error=str(exc), t_end=time.time())


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/soils")
def soils() -> list[dict]:
    return [
        {"key": k, "name": s.name, "texture": {"sand_pct": s.sand_pct, "clay_pct": s.clay_pct}}
        for k, s in SOIL_DATABASE.items()
    ]


@app.get("/crops")
def crops() -> list[dict]:
    return [
        {"key": k, "name": c.name, "root_depth_cm": c.root_depth_cm, "kc": c.kc}
        for k, c in CROP_DATABASE.items()
    ]


@app.post("/simulate", response_model=SimulateResponse)
def simulate(req: SimulateRequest) -> SimulateResponse:
    _validate(req)
    # Síncrono: casos curtos. Séries longas: usar /jobs.
    return run_simulation(req)


@app.post("/jobs", response_model=JobCreated)
def create_job(req: SimulateRequest) -> JobCreated:
    _validate(req)
    _cleanup_jobs()
    job_id = uuid.uuid4().hex[:12]
    with _jobs_lock:
        _jobs[job_id] = {"status": "queued", "t0": time.time(), "t_end": None, "result": None, "error": None}
    _pool.submit(_execute, job_id, req)
    return JobCreated(job_id=job_id)


@app.get("/jobs/{job_id}", response_model=JobStatus)
def job_status(job_id: str) -> JobStatus:
    _cleanup_jobs()
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job desconhecido ou expirado")
    return JobStatus(
        job_id=job_id,
        status=job["status"],
        elapsed_s=round(time.time() - job["t0"], 1),
        result=job["result"],
        error=job["error"],
        has_excel=bool(job.get("excel_path")),
        has_report=job["status"] == "done",
    )


@app.get("/jobs/{job_id}/excel")
def job_excel(job_id: str):
    import os

    with _jobs_lock:
        job = _jobs.get(job_id)
    path = (job or {}).get("excel_path")
    if not job or job["status"] != "done" or not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="excel indisponível")
    return FileResponse(path, filename=f"perfil_{job_id}.xlsx")


@app.get("/jobs/{job_id}/report")
def job_report(job_id: str) -> dict:
    import os

    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job or job["status"] != "done":
        raise HTTPException(status_code=404, detail="laudo indisponível")
    md_path = os.path.join(_jobs_root, job_id, "laudo.md")
    with open(md_path, encoding="utf-8") as f:
        return {"report_markdown": f.read()}


def _validate(req: SimulateRequest) -> None:
    errors: list[dict] = []
    if req.soil_key not in SOIL_DATABASE:
        errors.append({"field": "soil_key", "message": f"soil_key desconhecido: {req.soil_key}"})
    if req.crop_key and req.crop_key not in CROP_DATABASE:
        errors.append({"field": "crop_key", "message": f"crop_key desconhecido: {req.crop_key}"})
    if req.rain_series and len(req.rain_series) > 730:
        errors.append({"field": "rain_series", "message": "rain_series com mais de 730 dias"})
    _days_eff = len(req.rain_series) if req.rain_series else int(req.total_days)
    if req.et0_series and len(req.et0_series) != _days_eff:
        errors.append(
            {
                "field": "et0_series",
                "message": f"et0_series com {len(req.et0_series)} dias, esperado {_days_eff} (igual aos dias simulados)",
            }
        )
    errors.extend(validate_request(req))
    if errors:
        raise HTTPException(status_code=422, detail=errors)
