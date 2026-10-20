"""Tela de Resultados (Gradio): imagens estáticas servidas pelo backend."""

import time

from fastapi.testclient import TestClient

from app.main import app

POLL_TIMEOUT_S = 240
POLL_INTERVAL_S = 0.5


def _payload(**overrides) -> dict:
    payload = {
        "soil_key": "latossolo_medio",
        "crop_key": "soja",
        "total_days": 30,
        "rain_mm": 60.0,
        "solutes": [
            {"symbol": "N", "name": "Nitrogênio", "dose_kg_ha": 60.0, "kd": 0.0},
            {"symbol": "K", "name": "Potássio", "dose_kg_ha": 60.0, "kd": 1.0},
        ],
    }
    payload.update(overrides)
    return payload


def _wait_for_done(client: TestClient, job_id: str) -> dict:
    deadline = time.monotonic() + POLL_TIMEOUT_S
    status = None
    while time.monotonic() < deadline:
        response = client.get(f"/jobs/{job_id}")
        assert response.status_code == 200, response.text
        status = response.json()
        if status["status"] in {"done", "failed"}:
            break
        time.sleep(POLL_INTERVAL_S)
    assert status is not None, "job não retornou status"
    assert status["status"] == "done", f"job terminou com status {status['status']}: {status.get('error')}"
    return status


def test_screen_images_n_k() -> None:
    with TestClient(app) as client:
        created = client.post("/jobs", json=_payload())
        assert created.status_code == 200, created.text
        job_id = created.json()["job_id"]
        status = _wait_for_done(client, job_id)
        screen = (status["result"] or {}).get("screen")
        assert screen is not None, status["result"]
        assert screen.get("perfil"), screen
        assert screen.get("btc"), screen
        galeria = screen.get("galeria") or []
        assert len(galeria) == 2, galeria
        assert {g["symbol"] for g in galeria} == {"N", "K"}
        urls = [screen["perfil"], screen["btc"]]
        if screen.get("evolucao"):
            urls.append(screen["evolucao"])
        urls.extend(g["url"] for g in galeria)
        for url in urls:
            assert url.startswith(f"/jobs/{job_id}/tela/"), url
            assert url.endswith(".png"), url
            r = client.get(url)
            assert r.status_code == 200, (url, r.text[:200] if hasattr(r, "text") else r.status_code)
            assert r.headers.get("content-type", "").startswith("image/png"), url
            assert r.content[:8] == b"\x89PNG\r\n\x1a\n", url
        # Nome inválido (fora de [A-Za-z0-9_-]) -> 404.
        bad = client.get(f"/jobs/{job_id}/tela/invalido!.png")
        assert bad.status_code == 404, bad.text


def test_screen_images_water_only() -> None:
    payload = _payload(water_only=True, solutes=[])
    with TestClient(app) as client:
        created = client.post("/jobs", json=payload)
        assert created.status_code == 200, created.text
        job_id = created.json()["job_id"]
        status = _wait_for_done(client, job_id)
        screen = (status["result"] or {}).get("screen")
        assert screen is not None, status["result"]
        assert screen.get("perfil"), screen
        assert (screen.get("galeria") or []) == [], screen
        r = client.get(screen["perfil"])
        assert r.status_code == 200, r.text
        assert r.headers.get("content-type", "").startswith("image/png")
        assert r.content[:8] == b"\x89PNG\r\n\x1a\n"
