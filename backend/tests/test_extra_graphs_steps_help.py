"""T15/T17/T18: gráficos extras, ZIP, passo a passo, ajuda e jobs expirados."""

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


def _wait_done(client: TestClient, job_id: str) -> dict:
    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        r = client.get(f"/jobs/{job_id}")
        assert r.status_code == 200, r.text
        st = r.json()
        if st["status"] in {"done", "failed"}:
            assert st["status"] == "done", st.get("error")
            return st
        time.sleep(0.5)
    raise AssertionError("job não concluiu a tempo")


def test_extra_plots_keys_and_zip_contents() -> None:
    with TestClient(app) as client:
        created = client.post("/jobs", json=_payload())
        assert created.status_code == 200, created.text
        job_id = created.json()["job_id"]
        st = _wait_done(client, job_id)
        assert st["has_graphs"] is True
        result = st["result"]
        extra = result.get("extra_plots") or []
        assert len(extra) >= 3, extra
        keys = [p["key"] for p in extra]
        assert "perfil_umidade" in keys
        assert any(k.startswith("perfil_") for k in keys), keys
        assert "avanco_tempo_umidade" in keys
        for p in extra:
            assert p["title"].strip()
            # Lazy: sem base64 embutido; galeria via URL.
            assert not (p.get("png_base64") or "").strip(), p["key"]
            assert (p.get("url") or "").strip(), p["key"]
            assert p["url"].endswith(f"/plots/{p['key']}.png"), p
        # Amostra de PNGs servidos por URL (lazy, gera sob demanda).
        for key in keys[:3]:
            pr = client.get(f"/jobs/{job_id}/plots/{key}.png")
            assert pr.status_code == 200, (key, pr.text[:200] if hasattr(pr, "text") else pr.status_code)
            assert pr.content[:8] == b"\x89PNG\r\n\x1a\n", key

        zr = client.get(f"/jobs/{job_id}/graphs.zip")
        assert zr.status_code == 200, zr.text
        assert "zip" in zr.headers.get("content-type", "")
        zf = zipfile.ZipFile(io.BytesIO(zr.content))
        names = [n for n in zf.namelist() if n.lower().endswith(".png")]
        assert len(names) >= 3, names
        # Um PNG por painel: cada arquivo deve ser um PNG válido e distinto.
        seen = set()
        for n in names:
            data = zf.read(n)
            assert data[:8] == b"\x89PNG\r\n\x1a\n"
            seen.add(n)
        assert len(seen) == len(names)


def test_water_only_extra_plots_moisture_only() -> None:
    payload = _payload(water_only=True, solutes=[])
    with TestClient(app) as client:
        created = client.post("/jobs", json=payload)
        assert created.status_code == 200, created.text
        job_id = created.json()["job_id"]
        st = _wait_done(client, job_id)
        extra = (st["result"] or {}).get("extra_plots") or []
        assert extra, "modo só-água deve ter gráficos de umidade"
        keys = [p["key"] for p in extra]
        assert "perfil_umidade" in keys
        assert "avanco_tempo_umidade" in keys
        for p in extra:
            assert not (p.get("png_base64") or "").strip(), p["key"]
            assert (p.get("url") or "").strip(), p["key"]


def test_steps_non_empty() -> None:
    with TestClient(app) as client:
        created = client.post("/jobs", json=_payload())
        assert created.status_code == 200, created.text
        job_id = created.json()["job_id"]
        _wait_done(client, job_id)
        r = client.get(f"/jobs/{job_id}/steps")
        assert r.status_code == 200, r.text
        md = r.json()["steps_markdown"]
        assert isinstance(md, str) and len(md.strip()) > 200


def test_help_entries() -> None:
    with TestClient(app) as client:
        r = client.get("/help")
        assert r.status_code == 200, r.text
        entries = r.json()
        assert isinstance(entries, list) and len(entries) >= 20
        by_key = {e["key"]: e for e in entries}
        for key in ("theta_r", "kd_tab", "water_source", "placement_mode", "release_type"):
            assert key in by_key, key
            e = by_key[key]
            assert e["title"].strip()
            assert e["what"].strip()
            assert "simulation" in e


def test_expired_job_endpoints() -> None:
    with TestClient(app) as client:
        for path in ("/jobs/nope123/steps", "/jobs/nope123/graphs.zip"):
            r = client.get(path)
            assert r.status_code in (404, 410), (path, r.status_code, r.text)
        r = client.get("/jobs/nope123")
        assert r.status_code == 404
