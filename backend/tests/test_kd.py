"""Kd de literatura por textura (port do Gradio default_literature_kd)."""

from fastapi.testclient import TestClient

from app.main import app


def test_kd_by_soil_key_returns_all_nutrients_with_source() -> None:
    with TestClient(app) as client:
        r = client.get("/kd", params={"soil_key": "latossolo_medio"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["texture"] == "medio"
    got = {e["symbol"]: e for e in body["entries"]}
    assert set(got) == {"N", "K", "P", "S", "Ca", "Mg"}
    assert got["K"]["kd"] == 0.45
    assert got["P"]["kd"] == 25.0
    for e in body["entries"]:
        assert e["citation"], f"sem fonte p/ {e['symbol']}"


def test_kd_texture_differs_sand_vs_clay() -> None:
    with TestClient(app) as client:
        sandy = client.get("/kd", params={"sand": 90, "clay": 5}).json()
        clayey = client.get("/kd", params={"sand": 15, "clay": 65}).json()
    assert sandy["texture"] == "arenoso"
    assert clayey["texture"] == "argiloso"
    ks = {e["symbol"]: e["kd"] for e in sandy["entries"]}
    kc = {e["symbol"]: e["kd"] for e in clayey["entries"]}
    assert ks["K"] == 0.20
    assert kc["K"] == 0.85


def test_kd_phosphorus_includes_langmuir() -> None:
    with TestClient(app) as client:
        r = client.get("/kd", params={"soil_key": "latossolo_medio", "symbol": "P"})
    assert r.status_code == 200, r.text
    entries = r.json()["entries"]
    assert len(entries) == 1
    assert entries[0]["symbol"] == "P"
    assert entries[0]["langmuir"] is not None
    assert entries[0]["langmuir"]["smax_mg_g"] > 0


def test_kd_pub_soils_use_column_values() -> None:
    with TestClient(app) as client:
        lva = client.get("/kd", params={"soil_key": "pub_lva_arenoso", "symbol": "K"}).json()
        nv = client.get("/kd", params={"soil_key": "pub_nv_argiloso", "symbol": "K"}).json()
    assert lva["entries"][0]["kd"] == 0.235
    assert "ESALQ" in lva["entries"][0]["citation"]
    assert nv["entries"][0]["kd"] == 0.5189


def test_kd_unknown_soil_404_and_bad_texture_422() -> None:
    with TestClient(app) as client:
        assert client.get("/kd", params={"soil_key": "xxx"}).status_code == 404
        assert client.get("/kd", params={"sand": 80, "clay": 30}).status_code == 422
