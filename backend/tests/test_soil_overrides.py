"""Ajustes hidráulicos sobre o solo da lista (sem trocar o solo pela Rosetta)."""

from fastapi.testclient import TestClient

from app.main import app
from app.schemas import SimulateRequest, SoilOverrides
from app.service import _resolve_soil
from hydrus_core.soil_physics import SOIL_DATABASE


def _water(ks: float | None = None) -> dict:
    payload = {
        "soil_key": "latossolo_medio",
        "crop_key": None,
        "total_days": 7,
        "rain_mm": 60.0,
        "water_only": True,
        "solutes": [],
    }
    if ks is not None:
        payload["soil_overrides"] = {"ks": ks}
    return payload


def test_override_changes_ks_and_keeps_catalog_object() -> None:
    catalog = SOIL_DATABASE["latossolo_medio"]
    original = catalog.ks
    soil = _resolve_soil(SimulateRequest(
        soil_key="latossolo_medio",
        crop_key=None,
        water_only=True,
        solutes=[],
        soil_overrides=SoilOverrides(ks=5.0),
    ))
    assert soil.ks == 5.0
    assert soil.theta_r == catalog.theta_r
    assert soil.n == catalog.n
    assert catalog.ks == original
    untouched = _resolve_soil(SimulateRequest(soil_key="latossolo_medio", crop_key=None, water_only=True, solutes=[]))
    assert untouched is catalog


def test_edited_ks_changes_drainage() -> None:
    with TestClient(app) as client:
        base = client.post("/simulate", json=_water())
        edited = client.post("/simulate", json=_water(5.0))
    assert base.status_code == 200, base.text
    assert edited.status_code == 200, edited.text
    assert base.json()["drainage_mm"] != edited.json()["drainage_mm"]
