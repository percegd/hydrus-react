from fastapi.testclient import TestClient

import app.main as m

client = TestClient(m.app)
BASE = {"soil_key": "latossolo_medio", "crop_key": "soja", "total_days": 7, "rain_mm": 60}


def test_simbolo_repetido_retorna_422():
    body = dict(BASE, solutes=[{"symbol": "K", "name": "K", "dose_kg_ha": 30, "kd": 0.45},
                               {"symbol": "K", "name": "K2", "dose_kg_ha": 20, "kd": 0.45}])
    r = client.post("/simulate", json=body)
    assert r.status_code == 422
    assert any(e["field"] == "solutes" for e in r.json()["detail"])


def test_fila_cheia_retorna_429(monkeypatch):
    monkeypatch.setattr(m, "MAX_JOBS", 1)
    monkeypatch.setitem(m._jobs, "ativo", {"status": "running", "t0": 0, "t_end": None, "result": None, "error": None})
    body = dict(BASE, solutes=[{"symbol": "K", "name": "K", "dose_kg_ha": 30, "kd": 0.45}])
    r = client.post("/jobs", json=body)
    assert r.status_code == 429
