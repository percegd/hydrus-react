"""API Hydrus — FastAPI fina sobre o hydrus-core."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from hydrus_core.crop import CROP_DATABASE
from hydrus_core.soil_physics import SOIL_DATABASE

from .schemas import SimulateRequest, SimulateResponse
from .service import run_simulation

app = FastAPI(title="Hydrus API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    if req.soil_key not in SOIL_DATABASE:
        raise HTTPException(status_code=422, detail=f"soil_key desconhecido: {req.soil_key}")
    if req.crop_key and req.crop_key not in CROP_DATABASE:
        raise HTTPException(status_code=422, detail=f"crop_key desconhecido: {req.crop_key}")
    # Fase 1: síncrono (casos curtos). Fase 2: fila + progresso p/ séries anuais.
    return run_simulation(req)
