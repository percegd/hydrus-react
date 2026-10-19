"""API Hydrus — FastAPI fina sobre o hydrus-core."""

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from hydrus_core.crop import CROP_DATABASE
from hydrus_core.soil_physics import SOIL_DATABASE

from .schemas import JobCreated, JobStatus, SimulateRequest, SimulateResponse
from .service import run_simulation

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


def _execute(job_id: str, req: SimulateRequest) -> None:
    with _jobs_lock:
        _jobs[job_id]["status"] = "running"
    try:
        result = run_simulation(req)
        with _jobs_lock:
            _jobs[job_id].update(status="done", result=result)
    except Exception as exc:  # noqa: BLE001 — erro vira status consultável
        with _jobs_lock:
            _jobs[job_id].update(status="failed", error=str(exc))


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
    job_id = uuid.uuid4().hex[:12]
    with _jobs_lock:
        _jobs[job_id] = {"status": "queued", "t0": time.time(), "result": None, "error": None}
    _pool.submit(_execute, job_id, req)
    return JobCreated(job_id=job_id)


@app.get("/jobs/{job_id}", response_model=JobStatus)
def job_status(job_id: str) -> JobStatus:
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job desconhecido")
    return JobStatus(
        job_id=job_id,
        status=job["status"],
        elapsed_s=round(time.time() - job["t0"], 1),
        result=job["result"],
        error=job["error"],
    )


def _validate(req: SimulateRequest) -> None:
    if req.soil_key not in SOIL_DATABASE:
        raise HTTPException(status_code=422, detail=f"soil_key desconhecido: {req.soil_key}")
    if req.crop_key and req.crop_key not in CROP_DATABASE:
        raise HTTPException(status_code=422, detail=f"crop_key desconhecido: {req.crop_key}")
    if req.rain_series and len(req.rain_series) > 730:
        raise HTTPException(status_code=422, detail="rain_series com mais de 730 dias")
