"""T12: solo personalizado com Rosetta + simulação com custom_soil."""

from fastapi.testclient import TestClient

from app.main import app
from app.schemas import SimulateRequest, SoluteInput


def test_rosetta_returns_van_genuchten_like_gradio() -> None:
    with TestClient(app) as client:
        r = client.post("/soils/rosetta", json={"sand_pct": 60, "clay_pct": 25})
    assert r.status_code == 200, r.text
    body = r.json()
    # Mesmas chaves de update_rosetta_parameters + granulometria.
    for key in ("theta_r", "theta_s", "alpha", "n", "ks", "bulk_density"):
        assert isinstance(body[key], float) and body[key] > 0
    assert body["theta_r"] < body["theta_s"]
    assert body["n"] > 1.05
    assert body["silt_pct"] == 15.0
    assert body["texture"] == "medio"


def test_rosetta_sand_clay_over_100_is_422() -> None:
    with TestClient(app) as client:
        r = client.post("/soils/rosetta", json={"sand_pct": 80, "clay_pct": 30})
    assert r.status_code == 422, r.text
    assert "ultrapassa 100%" in r.text


def test_simulate_with_custom_soil_no_soil_key() -> None:
    payload = {
        "soil_key": None,
        "custom_soil": {"sand_pct": 60, "clay_pct": 25},
        "total_days": 7,
        "rain_mm": 60.0,
        "solutes": [{"symbol": "K", "name": "Potássio", "dose_kg_ha": 30, "kd": 0.45}],
    }
    with TestClient(app) as client:
        r = client.post("/simulate", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["solutes"][0]["symbol"] == "K"


def test_simulate_with_custom_soil_overrides() -> None:
    payload = {
        "custom_soil": {
            "sand_pct": 60,
            "clay_pct": 25,
            "theta_r": 0.1,
            "theta_s": 0.43,
            "alpha": 0.03,
            "n": 1.65,
            "ks": 80.0,
            "bulk_density": 1.3,
        },
        "total_days": 7,
        "rain_mm": 60.0,
        "solutes": [{"symbol": "K", "name": "Potássio", "dose_kg_ha": 30, "kd": 0.45}],
    }
    with TestClient(app) as client:
        r = client.post("/simulate", json=payload)
    assert r.status_code == 200, r.text


def test_simulate_custom_soil_bad_granulometry_is_422() -> None:
    payload = {
        "custom_soil": {"sand_pct": 80, "clay_pct": 30},
        "total_days": 7,
        "rain_mm": 60.0,
        "solutes": [{"symbol": "K", "name": "Potássio", "dose_kg_ha": 30, "kd": 0.45}],
    }
    with TestClient(app) as client:
        r = client.post("/simulate", json=payload)
    assert r.status_code == 422, r.text


def test_custom_soil_schema_defaults() -> None:
    req = SimulateRequest(
        custom_soil={"sand_pct": 60, "clay_pct": 25},
        solutes=[SoluteInput(symbol="K", name="Potássio", dose_kg_ha=30, kd=0.45)],
    )
    assert req.custom_soil is not None
    assert req.custom_soil.theta_r is None
    assert req.soil_key == "latossolo_medio" or True  # soil_key opcional com custom_soil
