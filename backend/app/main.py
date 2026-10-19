"""API Hydrus — FastAPI fina sobre o hydrus-core."""

import os
import shutil
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response

from hydrus_core.crop import CROP_DATABASE
from hydrus_core.soil_physics import SOIL_DATABASE

from . import climate as _climate
from .schemas import JobCreated, JobStatus, SimulateRequest, SimulateResponse
from .service import execute_job, run_simulation
from .validation import validate_request

app = FastAPI(title="Hydrus API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",") if o],
    allow_origin_regex=os.environ.get("CORS_ORIGIN_REGEX", r"https://.*\.vercel\.app"),
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
JOB_MAX_RUNTIME_S: float = _env_float("HYDRUS_JOB_MAX_RUNTIME_S", 1800)


def _cleanup_jobs() -> None:
    """Remove jobs terminados expirados (TTL) ou excedentes (MAX), apagando o diretório."""
    ttl = JOB_TTL_S
    max_jobs = MAX_JOBS
    max_runtime = JOB_MAX_RUNTIME_S
    now = time.time()
    expired: list[str] = []
    with _jobs_lock:
        # Jobs presos: queued/running além do tempo máximo viram failed (depois segue o TTL normal).
        for job in _jobs.values():
            if job.get("status") not in ("queued", "running"):
                continue
            try:
                t0 = float(job.get("t0", now))
            except (TypeError, ValueError):
                t0 = now
            if now - t0 > max_runtime:
                job["status"] = "failed"
                job["error"] = "Tempo máximo de execução excedido"
                job["t_end"] = now
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
        job = _jobs.get(job_id)
        if job is None or job.get("status") not in ("queued", "running"):
            return
        job["status"] = "running"
    try:
        resp, excel_path, _report = execute_job(req, os.path.join(_jobs_root, job_id))
        with _jobs_lock:
            job = _jobs.get(job_id)
            if job is None or job.get("status") == "failed":
                shutil.rmtree(os.path.join(_jobs_root, job_id), ignore_errors=True)
                return
            job.update(status="done", result=resp, excel_path=excel_path, t_end=time.time())
    except Exception as exc:  # noqa: BLE001 — erro vira status consultável
        with _jobs_lock:
            job = _jobs.get(job_id)
            if job is None or job.get("status") == "failed":
                shutil.rmtree(os.path.join(_jobs_root, job_id), ignore_errors=True)
                return
            job.update(status="failed", error=str(exc), t_end=time.time())


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


@app.get("/hubs")
def hubs() -> list[dict]:
    """Polos agrícolas (dropdown hub_choice do Gradio: nome + coords)."""
    return _climate.list_hubs()


@app.get("/hubs/{hub_key}/series")
def hub_series(hub_key: str, scenario: str = Query(default="medio")) -> dict:
    """Série diária de 365 dias do polo/cenário, como o Gradio monta.

    scenario: seco | medio | umido (alias do "Ano Chuvoso" do Gradio;
    "chuvoso" também é aceito).
    """
    if hub_key not in _climate._HUB_ORDER:
        raise HTTPException(status_code=404, detail=f"polo desconhecido: {hub_key}")
    try:
        return _climate.series_payload(hub_key, scenario)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=[{"field": "scenario", "message": str(exc)}])


@app.get("/climate/example")
def climate_example() -> dict:
    """Tabela-exemplo do formato esperado no upload (Dia, Chuva, ET0)."""
    return _climate.example_table()


@app.post("/climate/parse")
async def climate_parse(file: UploadFile = File(...)) -> dict:
    """Lê planilha climática (.xlsx/.csv, máx. 2 MB) -> 365 linhas.

    Porta handle_climate_upload do Gradio; erros viram 422 com as mensagens
    do Gradio ("Erro ao ler arquivo: ...").
    """
    name = file.filename or ""
    lname = name.lower()
    if not (lname.endswith(".xlsx") or lname.endswith(".xls") or lname.endswith(".csv")):
        raise HTTPException(
            status_code=422,
            detail=[{"field": "file", "message": "Formato não suportado. Envie .xlsx ou .csv."}],
        )
    try:
        content = await file.read()
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=[{"field": "file", "message": f"Erro ao ler arquivo: {exc}"}],
        )
    if len(content) > _climate.MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=422,
            detail=[{"field": "file", "message": "Arquivo muito grande (máx. 2 MB)."}],
        )
    if not content:
        raise HTTPException(
            status_code=422,
            detail=[{"field": "file", "message": "Erro ao ler arquivo: arquivo vazio ou sem dados válidos"}],
        )
    try:
        return _climate.parse_upload_file(name, content)
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail=[{"field": "file", "message": str(exc)}]
        )


@app.post("/simulate", response_model=SimulateResponse)
def simulate(req: SimulateRequest) -> SimulateResponse:
    _validate(req)
    # Síncrono: casos curtos. Séries longas: usar /jobs.
    return run_simulation(req)


@app.post("/jobs", response_model=JobCreated)
def create_job(req: SimulateRequest) -> JobCreated:
    _validate(req)
    _cleanup_jobs()
    if len(_jobs) >= MAX_JOBS:
        raise HTTPException(status_code=429, detail="Fila de jobs cheia; tente novamente em instantes")
    job_id = uuid.uuid4().hex[:12]
    with _jobs_lock:
        _jobs[job_id] = {"status": "queued", "t0": time.time(), "t_end": None, "result": None, "error": None}
    _pool.submit(_execute, job_id, req)
    return JobCreated(job_id=job_id)


@app.get("/jobs/{job_id}", response_model=JobStatus)
def job_status(job_id: str) -> JobStatus:
    _cleanup_jobs()
    now = time.time()
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job desconhecido ou expirado")
        if job.get("status") == "done":
            job["t_end"] = now
        snapshot = dict(job)
    return JobStatus(
        job_id=job_id,
        status=snapshot["status"],
        elapsed_s=round(now - snapshot["t0"], 1),
        result=snapshot["result"],
        error=snapshot["error"],
        has_excel=bool(snapshot.get("excel_path")),
        has_report=snapshot["status"] == "done",
    )


@app.get("/jobs/{job_id}/excel")
def job_excel(job_id: str):
    import os

    _cleanup_jobs()
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is not None and job.get("status") == "done":
            job["t_end"] = time.time()
        snapshot = dict(job) if job is not None else None
    if snapshot is None:
        raise HTTPException(status_code=410, detail="Job expirado; rode a simulação novamente.")
    path = snapshot.get("excel_path")
    if snapshot.get("status") != "done":
        raise HTTPException(status_code=404, detail="excel indisponível")
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=410, detail="Job expirado; rode a simulação novamente.")
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        raise HTTPException(status_code=410, detail="Job expirado; rode a simulação novamente.")
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="perfil_{job_id}.xlsx"'},
    )


@app.get("/jobs/{job_id}/report")
def job_report(job_id: str) -> dict:
    import os

    _cleanup_jobs()
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is not None and job.get("status") == "done":
            job["t_end"] = time.time()
        snapshot = dict(job) if job is not None else None
    if snapshot is None:
        raise HTTPException(status_code=410, detail="Job expirado; rode a simulação novamente.")
    if snapshot.get("status") != "done":
        raise HTTPException(status_code=404, detail="laudo indisponível")
    md_path = os.path.join(_jobs_root, job_id, "laudo.md")
    if not os.path.exists(md_path):
        raise HTTPException(status_code=410, detail="Job expirado; rode a simulação novamente.")
    try:
        with open(md_path, encoding="utf-8") as f:
            return {"report_markdown": f.read()}
    except FileNotFoundError:
        raise HTTPException(status_code=410, detail="Job expirado; rode a simulação novamente.")


def _validate(req: SimulateRequest) -> None:
    # soil_key: coberto pela validação central (validate_request retorna issue
    # em soil_choice; verificado que não lança exceção para solo desconhecido),
    # por isso sem checagem manual aqui para evitar mensagem duplicada.
    # crop_key/et0_series: verificado que validate_request retorna [] para esses
    # casos, então as checagens manuais abaixo são mantidas (não duplicam).
    # rain >730 dias e símbolo repetido: exclusivos da API, mantidos.
    errors: list[dict] = []
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
    _seen: set[str] = set()
    for s in req.solutes or []:
        _sym = getattr(s, "symbol", None)
        if _sym in _seen:
            errors.append({"field": "solutes", "message": f"Símbolo de soluto repetido: {_sym}"})
            break
        _seen.add(_sym)
    errors.extend(validate_request(req))
    errors = [e if isinstance(e, dict) else {"field": "request", "message": str(e)} for e in errors]
    seen: set[tuple[str, str]] = set()
    unique: list[dict] = []
    for e in errors:
        key = (str(e.get("field")), str(e.get("message")))
        if key not in seen:
            seen.add(key)
            unique.append(e)
    if unique:
        raise HTTPException(status_code=422, detail=unique)
