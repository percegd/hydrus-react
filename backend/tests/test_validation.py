"""Testes de validação das rotas POST /simulate e POST /jobs."""

from fastapi.testclient import TestClient

from app.main import app


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


def _assert_validation_detail(response) -> None:
    """422 de _validate: detail é lista de {field, message} não vazios."""
    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert isinstance(detail, list) and detail, detail
    for item in detail:
        assert isinstance(item, dict), item
        assert isinstance(item.get("field"), str) and item["field"].strip(), item
        assert isinstance(item.get("message"), str) and item["message"].strip(), item


def test_base_payload_returns_200() -> None:
    with TestClient(app) as client:
        response = client.post("/simulate", json=_base_payload())
    assert response.status_code == 200, response.text


def test_dose_zero_returns_422() -> None:
    payload = _base_payload(
        solutes=[{"symbol": "K", "name": "Potássio", "dose_kg_ha": 0.0, "kd": 1.0}]
    )
    with TestClient(app) as client:
        response = client.post("/simulate", json=payload)
    _assert_validation_detail(response)


def test_application_day_out_of_range_returns_422() -> None:
    payload = _base_payload(placement={"application_day": 400.0})
    with TestClient(app) as client:
        response = client.post("/simulate", json=payload)
    _assert_validation_detail(response)


def test_unknown_soil_key_returns_422() -> None:
    payload = _base_payload(soil_key="solo_inexistente")
    with TestClient(app) as client:
        response = client.post("/simulate", json=payload)
    _assert_validation_detail(response)


def test_unknown_crop_key_returns_422() -> None:
    payload = _base_payload(crop_key="cultura_inexistente")
    with TestClient(app) as client:
        response = client.post("/simulate", json=payload)
    _assert_validation_detail(response)


def test_et0_series_length_mismatch_returns_422() -> None:
    payload = _base_payload(et0_series=[4.0, 4.0, 4.0])
    with TestClient(app) as client:
        response = client.post("/simulate", json=payload)
    _assert_validation_detail(response)


def test_rain_series_too_long_returns_422() -> None:
    payload = _base_payload(rain_series=[0.0] * 731)
    with TestClient(app) as client:
        response = client.post("/simulate", json=payload)
    _assert_validation_detail(response)


def test_fertigation_zero_c0_returns_422() -> None:
    payload = _base_payload(
        placement={"mode": "fertigation", "fertigation_c0_mg_l": 0.0}
    )
    with TestClient(app) as client:
        response = client.post("/simulate", json=payload)
    _assert_validation_detail(response)


def test_jobs_with_dose_zero_returns_422() -> None:
    payload = _base_payload(
        solutes=[{"symbol": "K", "name": "Potássio", "dose_kg_ha": 0.0, "kd": 1.0}]
    )
    with TestClient(app) as client:
        response = client.post("/jobs", json=payload)
    _assert_validation_detail(response)
