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
from hydrus_core.literature_database import COMMERCIAL_FERTILIZERS
from hydrus_core.soil_physics import SOIL_DATABASE

from . import climate as _climate
from .schemas import (
    FertilizerDoseRequest,
    FertilizerDoseResponse,
    HelpEntry,
    JobCreated,
    JobStatus,
    KdEntry,
    KdResponse,
    RosettaRequest,
    RosettaResponse,
    SimulateRequest,
    SimulateResponse,
    StepsResponse,
)
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
        {
            "key": k,
            "name": c.name,
            "root_depth_cm": c.root_depth_cm,
            "kc": c.kc,
            "h1": c.h1,
            "h2": c.h2,
            "h3": c.h3,
            "h4": c.h4,
        }
        for k, c in CROP_DATABASE.items()
    ]


@app.get("/fertilizers")
def fertilizers() -> dict:
    """Catálogo de fertilizantes comerciais + presets de mistura (Gradio).

    commercial: COMMERCIAL_FERTILIZERS com rótulos do fert_choice;
    blend_presets: presets de apply_blend_preset (% N-P-K-S-Ca-Mg).
    """
    from .fertilizers import list_blend_presets, list_fertilizers

    return {"commercial": list_fertilizers(), "blend_presets": list_blend_presets()}


@app.post("/fertilizers/dose", response_model=FertilizerDoseResponse)
def fertilizer_dose(req: FertilizerDoseRequest) -> FertilizerDoseResponse:
    """Converte dose bruta [kg/ha] -> dose elementar por nutriente.

    Porta calculate_effective_dose do Gradio (incl. custom % N-P-K-S-Ca-Mg e
    blend_preset). Com nutrient_symbol, replica o modo 1-soluto: erro 422
    quando o adubo não contém o nutriente.
    """
    from .fertilizers import (
        FERTILIZER_CHOICES,
        NUTRIENT_ORDER,
        blend_preset_pcts,
        calculate_effective_dose,
        elemental_doses_for_pcts,
        fertilizer_display_name,
        fertilizer_nutrient_pcts,
        FertilizerDoseError,
    )

    fert_key = (req.fert_key or "").strip() or "direto"
    # Aceita rótulo do dropdown do Gradio além da chave.
    if fert_key in FERTILIZER_CHOICES:
        fert_key = FERTILIZER_CHOICES[fert_key]
    if fert_key not in COMMERCIAL_FERTILIZERS and fert_key not in ("direto", "custom"):
        raise HTTPException(status_code=404, detail=f"fertilizante desconhecido: {req.fert_key}")
    if req.gross_dose is not None and float(req.gross_dose) > 10000:
        raise HTTPException(
            status_code=422,
            detail=[{"field": "gross_dose", "message": f"Dose bruta ({float(req.gross_dose):.0f}) acima de 10000: provável erro de digitação."}],
        )

    pcts: dict[str, float]
    if req.blend_preset:
        found = blend_preset_pcts(req.blend_preset)
        if found is None:
            raise HTTPException(status_code=404, detail=f"blend desconhecido: {req.blend_preset}")
        fert_key = "custom"
        pcts = found
        fert_name = str(req.blend_preset)
    elif req.custom_pcts:
        fert_key = "custom" if fert_key == "direto" else fert_key
        pcts = {s: 0.0 for s in NUTRIENT_ORDER}
        for sym in NUTRIENT_ORDER:
            for alias in (sym, sym.lower()):
                if alias in (req.custom_pcts or {}):
                    try:
                        pcts[sym] = float((req.custom_pcts or {})[alias] or 0.0)
                    except (TypeError, ValueError):
                        raise HTTPException(
                            status_code=422,
                            detail=[{"field": f"custom_pcts.{sym}", "message": f"Teor de {sym} deve ser numérico."}],
                        )
        for sym, v in pcts.items():
            if v < 0 or v > 100:
                raise HTTPException(
                    status_code=422,
                    detail=[{"field": f"custom_pcts.{sym}", "message": f"Teor de {sym} ({v}) fora de [0, 100] %."}],
                )
        fert_name = "Fertilizante Personalizado"
    elif fert_key == "custom":
        pcts = {s: 0.0 for s in NUTRIENT_ORDER}
        fert_name = "Fertilizante Personalizado"
    else:
        pcts = fertilizer_nutrient_pcts(fert_key)
        fert_name = fertilizer_display_name(fert_key)

    elemental = elemental_doses_for_pcts(pcts, float(req.gross_dose or 0.0))
    if req.nutrient_symbol:
        try:
            _dose, message = calculate_effective_dose(fert_key, float(req.gross_dose or 0.0), req.nutrient_symbol)
        except FertilizerDoseError as exc:
            raise HTTPException(status_code=422, detail=[{"field": "nutrient_symbol", "message": str(exc)}])
    else:
        actives = ", ".join(f"{elemental[s]:.1f} kg/ha de {s}" for s in NUTRIENT_ORDER if elemental[s] > 0)
        message = (
            f"Dose bruta de {float(req.gross_dose or 0.0):.0f} kg/ha de {fert_name} contém "
            f"{actives}." if actives else f"Dose bruta de {float(req.gross_dose or 0.0):.0f} kg/ha de {fert_name}."
        )
    return FertilizerDoseResponse(
        fert_key=fert_key,
        fert_name=fert_name,
        gross_dose=float(req.gross_dose or 0.0),
        nutrient_pcts={s: float(pcts.get(s, 0.0)) for s in NUTRIENT_ORDER},
        elemental_doses={s: float(elemental.get(s, 0.0)) for s in NUTRIENT_ORDER},
        message=message,
    )


@app.post("/soils/rosetta", response_model=RosettaResponse)
def soils_rosetta(req: RosettaRequest) -> RosettaResponse:
    """Estima van Genuchten via Rosetta (Gradio update_rosetta_parameters).

    RosettaUnavailableError -> 422 (sem fallback aproximado, como no Gradio).
    """
    from hydrus_core.soil_physics import RosettaUnavailableError, classify_texture

    from .soils import rosetta_params

    try:
        s = float(req.sand_pct)
        c = float(req.clay_pct)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=422, detail=[{"field": "sand_pct", "message": "% de Areia/% de Argila deve ser numérico."}]
        )
    if not (0 <= s <= 100) or not (0 <= c <= 100):
        raise HTTPException(
            status_code=422,
            detail=[{"field": "sand_pct", "message": f"Areia ({s:.0f}%) / Argila ({c:.0f}%) fora de [0, 100] — fisicamente impossível."}],
        )
    if s + c > 100:
        raise HTTPException(
            status_code=422,
            detail=[{"field": "clay_pct", "message": f"Soma de Areia ({s:.0f}%) e Argila ({c:.0f}%) ultrapassa 100%. Corrija os valores (soma ≤ 100%)."}],
        )
    try:
        params = rosetta_params(s, c, req.bulk_density)
    except RosettaUnavailableError as exc:
        raise HTTPException(status_code=422, detail=[{"field": "sand_pct", "message": str(exc)}])
    silt = max(0.0, 100.0 - s - c)
    return RosettaResponse(
        theta_r=params["theta_r"],
        theta_s=params["theta_s"],
        alpha=params["alpha"],
        n=params["n"],
        ks=params["ks"],
        bulk_density=params["bulk_density"],
        silt_pct=round(silt, 1),
        texture=classify_texture(s, c),
    )


@app.get("/kd", response_model=KdResponse)
def kd_lookup(
    soil_key: str | None = Query(default=None),
    sand: float | None = Query(default=None),
    clay: float | None = Query(default=None),
    symbol: str | None = Query(default=None),
) -> KdResponse:
    """Kd de literatura por nutriente (Gradio default_literature_kd / badge).

    soil_key = solo da lista; ou sand+clay (solo personalizado). Inclui
    citação/descrição por nutriente e Langmuir do P (quando houver, como na
    base de literatura). symbol filtra um nutriente.
    """
    from .soils import DEFAULT_SOIL_KEY, literature_kd, texture_for

    key = soil_key or (None if (sand is not None or clay is not None) else DEFAULT_SOIL_KEY)
    if key is not None and key != "custom" and key not in SOIL_DATABASE:
        raise HTTPException(status_code=404, detail=f"solo desconhecido: {soil_key}")
    s = float(sand) if sand is not None else None
    c = float(clay) if clay is not None else None
    if (s is not None and not (0 <= s <= 100)) or (c is not None and not (0 <= c <= 100)):
        raise HTTPException(
            status_code=422, detail=[{"field": "sand", "message": "Areia/Argila fora de [0, 100] — fisicamente impossível."}]
        )
    if s is not None and c is not None and s + c > 100:
        raise HTTPException(
            status_code=422, detail=[{"field": "clay", "message": f"Soma de Areia ({s:.0f}%) e Argila ({c:.0f}%) ultrapassa 100%. Corrija os valores (soma ≤ 100%)."}]
        )
    texture = texture_for(key, s, clay if c is None else c)
    symbols = ["N", "K", "P", "S", "Ca", "Mg"]
    if symbol:
        up = str(symbol).strip().upper()
        symbols = [up] if up in symbols else [str(symbol).strip()]
    entries = [KdEntry(**literature_kd(sym, key, s, c)) for sym in symbols]
    return KdResponse(soil_key=key, sand_pct=s, clay_pct=c, texture=texture, entries=entries)


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
    """Lê planilha climática (.xlsx/.xls/.csv, máx. 2 MB) -> 365 linhas.

    Porta handle_climate_upload do Gradio; erros viram 422 com as mensagens
    do Gradio ("Erro ao ler arquivo: ...").
    """
    name = file.filename or ""
    lname = name.lower()
    if not (lname.endswith(".xlsx") or lname.endswith(".xls") or lname.endswith(".csv")):
        raise HTTPException(
            status_code=422,
            detail=[{"field": "file", "message": "Formato não suportado. Envie .xlsx, .xls ou .csv."}],
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
    _excel_ok = bool(snapshot.get("excel_path"))
    _graphs_ok = os.path.exists(os.path.join(_jobs_root, job_id, "graphs.zip"))
    _steps_ok = os.path.exists(os.path.join(_jobs_root, job_id, "passo_a_passo.md"))
    return JobStatus(
        job_id=job_id,
        status=snapshot["status"],
        elapsed_s=round(now - snapshot["t0"], 1),
        result=snapshot["result"],
        error=snapshot["error"],
        has_excel=_excel_ok,
        has_report=snapshot["status"] == "done",
        has_graphs=_graphs_ok,
        has_steps=_steps_ok,
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


@app.get("/help", response_model=list[HelpEntry])
def field_help() -> list[HelpEntry]:
    """Textos de ajuda por campo (botão "?" da UI), iguais aos do Gradio.

    Mapeamento de campos igual ao Gradio (KEY_BY_HOST + data-helpkey):
    theta_r, theta_s, alpha, n, ks, bulk_density, disp, domain_depth,
    obs_depths, crop_name, root_depth, kc, fed_h1..h4, dose_tab, kd_tab,
    disp_tab, res_tab, release_type, release_days, placement_mode, z_top,
    z_bottom, fert_c0, fert_pulse, rain_mm, moisture, total_days, et0,
    evap, transp, app_day, print_days, window_start, window_end,
    water_source, water_series, water_upload.
    """
    from hydrus_core.field_help import FIELD_HELP

    return [
        HelpEntry(key=key, title=title, unit=unit, what=what, simulation=sim)
        for key, (title, unit, what, sim) in FIELD_HELP.items()
    ]


@app.get("/jobs/{job_id}/steps", response_model=StepsResponse)
def job_steps(job_id: str) -> StepsResponse:
    """Passo a passo da simulação (memória de cálculo), como o Gradio monta."""
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
        raise HTTPException(status_code=404, detail="passo a passo indisponível")
    md_path = os.path.join(_jobs_root, job_id, "passo_a_passo.md")
    if not os.path.exists(md_path):
        raise HTTPException(status_code=410, detail="Job expirado; rode a simulação novamente.")
    try:
        with open(md_path, encoding="utf-8") as f:
            return StepsResponse(steps_markdown=f.read())
    except FileNotFoundError:
        raise HTTPException(status_code=410, detail="Job expirado; rode a simulação novamente.")


@app.get("/jobs/{job_id}/graphs.zip")
def job_graphs_zip(job_id: str):
    """ZIP com todos os gráficos (1 painel por PNG), como o Gradio."""
    import os

    from fastapi.responses import FileResponse

    _cleanup_jobs()
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is not None and job.get("status") == "done":
            job["t_end"] = time.time()
        snapshot = dict(job) if job is not None else None
    if snapshot is None:
        raise HTTPException(status_code=410, detail="Job expirado; rode a simulação novamente.")
    if snapshot.get("status") != "done":
        raise HTTPException(status_code=404, detail="gráficos indisponíveis")
    zip_path = os.path.join(_jobs_root, job_id, "graphs.zip")
    if not os.path.exists(zip_path):
        raise HTTPException(status_code=410, detail="Job expirado; rode a simulação novamente.")
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=f"graficos_{job_id}.zip",
    )


def _validate(req: SimulateRequest) -> None:
    # soil_key: coberto pela validação central (validate_request retorna issue
    # em soil_choice; verificado que não lança exceção para solo desconhecido),
    # por isso sem checagem manual aqui para evitar mensagem duplicada.
    # crop_key/et0_series: verificado que validate_request retorna [] para esses
    # casos, então as checagens manuais abaixo são mantidas (não duplicam).
    # rain >730 dias e símbolo repetido: exclusivos da API, mantidos.
    errors: list[dict] = []
    if req.crop_key and req.crop_key != "custom" and req.crop_key not in CROP_DATABASE:
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
