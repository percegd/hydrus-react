"""T11: fertilizantes comerciais e misturas (port do Gradio)."""

from fastapi.testclient import TestClient

from app.fertilizers import BLEND_PRESETS, calculate_effective_dose, FertilizerDoseError
from app.main import app


def test_list_fertilizers_has_commercial_and_blends() -> None:
    with TestClient(app) as client:
        r = client.get("/fertilizers")
    assert r.status_code == 200, r.text
    body = r.json()
    keys = {f["key"] for f in body["commercial"]}
    for expected in ("kcl", "ureia", "map", "polialita", "kmag", "sulfato_amonio", "nitrato_amonio", "kcl_gesso", "direto"):
        assert expected in keys, f"faltando {expected}"
    kcl = next(f for f in body["commercial"] if f["key"] == "kcl")
    assert kcl["nutrient_pcts"]["K"] == 49.8
    assert "Cloreto de Potássio" in kcl["label"]
    blend_keys = {b["key"] for b in body["blend_presets"]}
    assert set(BLEND_PRESETS) <= blend_keys


def test_dose_kcl_matches_gradio_math() -> None:
    with TestClient(app) as client:
        r = client.post("/fertilizers/dose", json={"fert_key": "kcl", "gross_dose": 200})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["elemental_doses"]["K"] == 99.6
    assert body["nutrient_pcts"]["K"] == 49.8


def test_dose_single_nutrient_message_matches_gradio() -> None:
    dose, msg = calculate_effective_dose("kcl", 200, "K")
    assert dose == 99.6 or abs(dose - 99.6) < 1e-9
    assert "200 kg/ha" in msg and "99.6 kg/ha de K" in msg
    with TestClient(app) as client:
        r = client.post("/fertilizers/dose", json={"fert_key": "kcl", "gross_dose": 200, "nutrient_symbol": "K"})
    assert r.status_code == 200, r.text
    assert r.json()["message"] == msg


def test_dose_fertilizer_without_nutrient_is_422() -> None:
    try:
        calculate_effective_dose("kcl", 200, "N")
        raise AssertionError("deveria levantar")
    except FertilizerDoseError as exc:
        assert "não contém N" in str(exc)
    with TestClient(app) as client:
        r = client.post("/fertilizers/dose", json={"fert_key": "kcl", "gross_dose": 200, "nutrient_symbol": "N"})
    assert r.status_code == 422, r.text
    assert "não contém N" in r.text


def test_dose_direto_passes_through() -> None:
    with TestClient(app) as client:
        r = client.post("/fertilizers/dose", json={"fert_key": "direto", "gross_dose": 100, "nutrient_symbol": "K"})
    assert r.status_code == 200, r.text
    assert "Dose elementar direta" in r.json()["message"]


def test_dose_custom_pcts() -> None:
    with TestClient(app) as client:
        r = client.post(
            "/fertilizers/dose",
            json={"fert_key": "custom", "gross_dose": 200, "custom_pcts": {"N": 10, "K": 20, "P": 5}},
        )
    assert r.status_code == 200, r.text
    doses = r.json()["elemental_doses"]
    assert doses["N"] == 20.0
    assert doses["K"] == 40.0
    assert doses["P"] == 10.0
    assert doses["S"] == 0.0


def test_dose_blend_preset_npk() -> None:
    with TestClient(app) as client:
        r = client.post("/fertilizers/dose", json={"gross_dose": 100, "blend_preset": "NPK (blend)"})
    assert r.status_code == 200, r.text
    doses = r.json()["elemental_doses"]
    assert doses["N"] == 50.0
    assert doses["K"] == 50.0
    assert doses["P"] == 15.0


def test_dose_unknown_fertilizer_404_and_bad_dose_422() -> None:
    with TestClient(app) as client:
        assert client.post("/fertilizers/dose", json={"fert_key": "xxx", "gross_dose": 100}).status_code == 404
        assert client.post("/fertilizers/dose", json={"fert_key": "kcl", "gross_dose": 20000}).status_code == 422
        assert client.post("/fertilizers/dose", json={"fert_key": "kcl", "gross_dose": -5}).status_code == 422
