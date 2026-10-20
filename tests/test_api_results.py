"""Resultados da API: mesmos PNGs do Gradio, embutidos em base64 no job."""

import base64
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)


def _payload(solutes):
    return {
        "soil_key": "latossolo_medio",
        "crop_key": "soja",
        "depth_cm": 200.0,
        "total_days": 30.0,
        "rain_mm": 100.0,
        "initial_moisture_pct": 20.0,
        "et0_mm_day": 4.0,
        "placement": {
            "mode": "surface",
            "z_top_cm": 0.0,
            "z_bottom_cm": 2.0,
            "fertigation_c0_mg_l": 20.0,
            "fertigation_pulse_days": 0.0,
            "application_day": 0.0,
        },
        "solutes": solutes,
    }


def _k():
    return {
        "symbol": "K",
        "name": "Potássio",
        "dose_kg_ha": 30.0,
        "kd": 0.45,
        "initial_residual_mg_dm3": 0.0,
        "dispersivity_cm": 20.0,
        "release_type": "immediate",
        "release_days": 60.0,
    }


def _n():
    return {
        "symbol": "N",
        "name": "Nitrato",
        "dose_kg_ha": 30.0,
        "kd": 0.0,
        "initial_residual_mg_dm3": 0.0,
        "dispersivity_cm": 20.0,
        "release_type": "immediate",
        "release_days": 60.0,
    }


def _run_job(payload, timeout_s=600):
    r = client.post("/jobs", json=payload)
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]
    t0 = time.time()
    while True:
        st = client.get(f"/jobs/{job_id}").json()
        assert st["status"] in ("queued", "running", "done", "failed"), st
        if st["status"] == "done":
            return job_id, st
        if st["status"] == "failed":
            raise AssertionError(f"job falhou: {st.get('error')}")
        assert time.time() - t0 < timeout_s, "job demorou demais"
        time.sleep(0.5)


def _assert_png_b64(value, label):
    assert isinstance(value, str) and value.startswith("iVBOR"), f"{label} não é PNG base64"
    raw = base64.b64decode(value)
    assert raw[:8] == b"\x89PNG\r\n\x1a\n", f"{label} sem assinatura PNG"


def _check_common(job_id, st, expect_gallery: int):
    res = st["result"]
    assert st["has_zip"] is True
    imgs = res["images"]
    _assert_png_b64(imgs["perfil"], "perfil")
    _assert_png_b64(imgs["btc"], "btc")
    _assert_png_b64(imgs["agua"], "agua")
    if imgs["evolucao"] is not None:
        _assert_png_b64(imgs["evolucao"], "evolucao")
    assert isinstance(imgs["galeria"], list) and len(imgs["galeria"]) == expect_gallery
    for g in imgs["galeria"]:
        assert g["symbol"] and g["name"]
        _assert_png_b64(g["png"], f"galeria {g['symbol']}")
    # Campos dos cartões do Gradio.
    for key in ("applied_mm", "eval_depth_cm", "target_depth_cm", "has_crop",
                "z_max_cm", "runoff_mm", "storage_mm"):
        assert key in res, f"faltando {key}"
    assert res["has_crop"] is True
    assert res["applied_mm"] == 100.0
    for s in res["solutes"]:
        for key in ("kd", "kd_eff", "initial_residual_mg_dm3", "leaching_ratio_pct"):
            assert key in s, f"soluto sem {key}"
    # Downloads.
    z = client.get(f"/jobs/{job_id}/graficos.zip")
    assert z.status_code == 200, z.text
    assert z.content[:4] == b"PK\x03\x04", "zip sem assinatura"
    x = client.get(f"/jobs/{job_id}/excel")
    assert x.status_code == 200, x.text
    assert len(x.content) > 0


def test_job_um_soluto_sem_galeria():
    job_id, st = _run_job(_payload([_k()]))
    _check_common(job_id, st, expect_gallery=0)


def test_job_dois_solutos_com_galeria():
    job_id, st = _run_job(_payload([_n(), _k()]))
    res = st["result"]
    assert {s["symbol"] for s in res["solutes"]} == {"N", "K"}
    _check_common(job_id, st, expect_gallery=2)
    syms = sorted(g["symbol"] for g in st["result"]["images"]["galeria"])
    assert syms == ["K", "N"]
