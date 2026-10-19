"""PERFORMANCE: long-poll ?wait=, plots lazy por URL, sem base64 no job."""

import io
import time
import zipfile

from fastapi.testclient import TestClient

from app.main import app


def _payload(**overrides):
    payload = {
        "soil_key": "latossolo_medio",
        "crop_key": "soja",
        "total_days": 7,
        "rain_mm": 60.0,
        "solutes": [
            {"symbol": "K", "name": "Potássio", "dose_kg_ha": 30.0, "kd": 0.45},
        ],
    }
    payload.update(overrides)
    return payload


def test_longpoll_returns_done_within_wait() -> None:
    with TestClient(app) as client:
        created = client.post("/jobs", json=_payload())
        assert created.status_code == 200, created.text
        job_id = created.json()["job_id"]
        t0 = time.monotonic()
        r = client.get(f"/jobs/{job_id}?wait=25")
        dt = time.monotonic() - t0
        assert r.status_code == 200, r.text
        st = r.json()
        assert st["status"] == "done", st
        assert st["result"] is not None
        assert dt < 25.0, dt


def test_wait_zero_is_immediate() -> None:
    with TestClient(app) as client:
        created = client.post("/jobs", json=_payload())
        assert created.status_code == 200, created.text
        job_id = created.json()["job_id"]
        t0 = time.monotonic()
        r = client.get(f"/jobs/{job_id}?wait=0")
        dt = time.monotonic() - t0
        assert r.status_code == 200, r.text
        st = r.json()
        assert st["status"] in ("queued", "running", "done"), st
        assert dt < 5.0, dt
        # Drena o job para não vazar thread entre testes.
        deadline = time.monotonic() + 240
        while time.monotonic() < deadline:
            rr = client.get(f"/jobs/{job_id}?wait=25")
            assert rr.status_code == 200, rr.text
            if rr.json()["status"] in ("done", "failed"):
                assert rr.json()["status"] == "done", rr.json().get("error")
                break


def _wait_done(client: TestClient, job_id: str) -> dict:
    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        r = client.get(f"/jobs/{job_id}?wait=25")
        assert r.status_code == 200, r.text
        st = r.json()
        if st["status"] in ("done", "failed"):
            assert st["status"] == "done", st.get("error")
            return st
    raise AssertionError("job não concluiu a tempo")


def test_plots_endpoint_valid_200_invalid_404() -> None:
    with TestClient(app) as client:
        created = client.post("/jobs", json=_payload())
        assert created.status_code == 200, created.text
        job_id = created.json()["job_id"]
        st = _wait_done(client, job_id)
        extra = (st["result"] or {}).get("extra_plots") or []
        assert extra, "job deve listar gráficos extras"
        key = extra[0]["key"]
        ok = client.get(f"/jobs/{job_id}/plots/{key}.png")
        assert ok.status_code == 200, (key, ok.status_code)
        assert ok.headers.get("content-type", "").startswith("image/png"), ok.headers
        assert ok.content[:8] == b"\x89PNG\r\n\x1a\n"
        bad = client.get(f"/jobs/{job_id}/plots/chave_inexistente_xyz.png")
        assert bad.status_code == 404, (bad.status_code, bad.text[:200])
        traversal = client.get(f"/jobs/{job_id}/plots/..%2Flaudo.png")
        assert traversal.status_code in (404, 422), traversal.status_code


def test_graphs_zip_has_one_png_per_panel() -> None:
    with TestClient(app) as client:
        created = client.post("/jobs", json=_payload())
        assert created.status_code == 200, created.text
        job_id = created.json()["job_id"]
        _wait_done(client, job_id)
        zr = client.get(f"/jobs/{job_id}/graphs.zip")
        assert zr.status_code == 200, zr.text
        zf = zipfile.ZipFile(io.BytesIO(zr.content))
        names = [n for n in zf.namelist() if n.lower().endswith(".png")]
        assert len(names) >= 3, names
        assert len(set(names)) == len(names), "um PNG por painel (sem duplicatas)"
        for n in names:
            assert zf.read(n)[:8] == b"\x89PNG\r\n\x1a\n", n


def test_result_json_has_no_extra_plot_base64() -> None:
    with TestClient(app) as client:
        created = client.post("/jobs", json=_payload())
        assert created.status_code == 200, created.text
        job_id = created.json()["job_id"]
        st = _wait_done(client, job_id)
        extra = (st["result"] or {}).get("extra_plots") or []
        assert extra, "job deve listar gráficos extras"
        for p in extra:
            assert p.get("key"), p
            assert p.get("title"), p
            assert (p.get("url") or "").endswith(f"/plots/{p['key']}.png"), p
            assert not (p.get("png_base64") or ""), f"job não deve embutir base64: {p['key']}"
