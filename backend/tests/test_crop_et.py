"""T13 cultura editável + ET avançada: overrides, /crops, split E/T e validações 422."""

import numpy as np
from fastapi.testclient import TestClient

from app.main import app
from app.service import _build_crop


def _base_payload(**overrides) -> dict:
    payload = {
        "soil_key": "latossolo_medio",
        "crop_key": "soja",
        "total_days": 7,
        "rain_mm": 60.0,
        "solutes": [
            {
                "symbol": "K",
                "name": "Potássio",
                "dose_kg_ha": 60.0,
                "kd": 1.0,
            }
        ],
    }
    payload.update(overrides)
    return payload


def test_crops_returns_kc_and_feddes() -> None:
    with TestClient(app) as client:
        response = client.get("/crops")
    assert response.status_code == 200, response.text
    crops = response.json()
    assert isinstance(crops, list) and crops, crops
    for entry in crops:
        for field in ("key", "name", "root_depth_cm", "kc", "h1", "h2", "h3", "h4"):
            assert field in entry, (field, entry)
        assert entry["h1"] < 0 and entry["h2"] < 0 and entry["h3"] < 0 and entry["h4"] < 0
        assert entry["h1"] > entry["h2"] > entry["h3"] > entry["h4"], entry


def test_build_crop_applies_overrides_like_gradio() -> None:
    from app.schemas import SimulateRequest

    req = SimulateRequest(crop_key="soja", kc=0.5, h3=-100.0, root_depth_cm=20.0)
    crop = _build_crop(req)
    assert crop is not None
    assert crop.kc == 0.5
    assert crop.h3 == -100.0
    assert crop.root_depth_cm == 20.0
    # Não editados: valores do banco da soja.
    assert crop.h1 == -15.0 and crop.h4 == -12000.0
    assert crop.name == "Soja"


def test_build_crop_custom_name_marks_personalizado() -> None:
    from app.schemas import SimulateRequest

    req = SimulateRequest(crop_key="soja", crop_name="Soja RR custom")
    crop = _build_crop(req)
    assert crop is not None
    assert crop.name == "Soja RR custom"
    assert crop.stage == "Personalizado"


def test_build_crop_custom_key() -> None:
    from app.schemas import SimulateRequest

    req = SimulateRequest(
        crop_key="custom", crop_name="Milho safrinha",
        root_depth_cm=40.0, kc=1.1, h1=-15.0, h2=-30.0, h3=-500.0, h4=-8000.0,
    )
    crop = _build_crop(req)
    assert crop is not None
    assert crop.name == "Milho safrinha"
    assert crop.kc == 1.1 and crop.root_depth_cm == 40.0


def test_feddes_override_changes_uptake_response() -> None:
    """h3 mais raso (-100) antecipa o estresse: alpha(-200) cai de 1.0 para < 1."""
    from hydrus_core.crop import feddes_water_stress
    from app.schemas import SimulateRequest

    default = _build_crop(SimulateRequest(crop_key="soja"))
    stressed = _build_crop(SimulateRequest(crop_key="soja", h3=-100.0))
    h = np.array([-200.0])
    assert float(feddes_water_stress(h, default)[0]) == 1.0
    assert float(feddes_water_stress(h, stressed)[0]) < 1.0


def test_kc_override_changes_transp_water_balance() -> None:
    with TestClient(app) as client:
        base = client.post("/simulate", json=_base_payload())
        low = client.post("/simulate", json=_base_payload(kc=0.2))
    assert base.status_code == 200, base.text
    assert low.status_code == 200, low.text
    t_base = base.json()["water_balance"]["transp_mm"]
    t_low = low.json()["water_balance"]["transp_mm"]
    assert isinstance(t_base, float) and isinstance(t_low, float)
    assert t_low < t_base


def test_custom_crop_key_simulates_200() -> None:
    payload = _base_payload(
        crop_key="custom", crop_name="Milho safrinha", kc=1.1,
        h1=-15.0, h2=-30.0, h3=-500.0, h4=-8000.0,
    )
    with TestClient(app) as client:
        response = client.post("/simulate", json=payload)
    assert response.status_code == 200, response.text


def test_manual_et_split_changes_water_balance() -> None:
    with TestClient(app) as client:
        base = client.post("/simulate", json=_base_payload(et0_mm_day=4.0))
        manual = client.post(
            "/simulate", json=_base_payload(et0_mm_day=4.0, evap_mm_day=2.0, transp_mm_day=2.0)
        )
    assert base.status_code == 200, base.text
    assert manual.status_code == 200, manual.text
    wb_base = base.json()["water_balance"]
    wb_manual = manual.json()["water_balance"]
    assert wb_manual["evap_mm"] != wb_base["evap_mm"]
    assert wb_manual["transp_mm"] != wb_base["transp_mm"]


def test_crop_kc_zero_returns_422() -> None:
    with TestClient(app) as client:
        response = client.post("/simulate", json=_base_payload(kc=0.0))
    assert response.status_code == 422, response.text


def test_crop_feddes_out_of_order_returns_422() -> None:
    with TestClient(app) as client:
        response = client.post("/simulate", json=_base_payload(h1=-30.0, h2=-15.0))
    assert response.status_code == 422, response.text


def test_crop_h_positive_returns_422() -> None:
    with TestClient(app) as client:
        response = client.post("/simulate", json=_base_payload(h4=100.0))
    assert response.status_code == 422, response.text


def test_negative_evap_returns_422() -> None:
    with TestClient(app) as client:
        response = client.post("/simulate", json=_base_payload(evap_mm_day=-1.0))
    assert response.status_code == 422, response.text
