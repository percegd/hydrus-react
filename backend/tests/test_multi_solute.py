"""Testes de integração multi-soluto (laudo, PNGs e rota /simulate)."""

import base64

from fastapi.testclient import TestClient

from app.main import app
from app.schemas import SimulateRequest, SoluteInput
from app.service import execute_job

SOLUTES = [
    {"symbol": "N", "name": "Nitrogênio", "dose_kg_ha": 60.0, "kd": 0.0},
    {"symbol": "K", "name": "Potássio", "dose_kg_ha": 60.0, "kd": 1.0},
    {"symbol": "S", "name": "Enxofre", "dose_kg_ha": 60.0, "kd": 0.3},
]
PNG_MAGIC = b"\x89PNG"


def _request(**overrides) -> SimulateRequest:
    data = {
        "soil_key": "latossolo_medio",
        "crop_key": "soja",
        "total_days": 30,
        "rain_mm": 60.0,
        "solutes": [SoluteInput(**s) for s in SOLUTES],
    }
    data.update(overrides)
    return SimulateRequest(**data)


def _assert_png_base64(value: str) -> None:
    assert base64.b64decode(value).startswith(PNG_MAGIC)


def _assert_multi_solute_outputs(response, report: str) -> None:
    plots = response.plots_png_base64 or {}
    assert set(plots) == {"N", "K", "S"}
    for encoded in plots.values():
        _assert_png_base64(encoded)
    for solute in SOLUTES:
        assert solute["name"] in report or f"({solute['symbol']})" in report


def test_execute_job_multi_solute_30_days(tmp_path) -> None:
    response, _excel_path, report = execute_job(_request(), str(tmp_path))

    _assert_multi_solute_outputs(response, report)
    assert (tmp_path / "laudo.md").is_file()


def test_execute_job_multi_solute_365_days_rain_series(tmp_path) -> None:
    rain_series = [5.0 if day % 3 == 0 else 0.0 for day in range(365)]
    response, _excel_path, report = execute_job(
        _request(rain_series=rain_series), str(tmp_path)
    )

    _assert_multi_solute_outputs(response, report)


def test_simulate_post_multi_solute_returns_two_plots() -> None:
    payload = {
        "soil_key": "latossolo_medio",
        "crop_key": "soja",
        "total_days": 30,
        "rain_mm": 60.0,
        "solutes": SOLUTES[:2],
    }

    with TestClient(app) as client:
        response = client.post("/simulate", json=payload)

    assert response.status_code == 200, response.text
    plots = response.json()["plots_png_base64"]
    assert plots is not None
    assert len(plots) == 2
    assert set(plots) == {"N", "K"}
    for encoded in plots.values():
        _assert_png_base64(encoded)
