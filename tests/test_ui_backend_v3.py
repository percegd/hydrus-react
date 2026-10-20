"""UI/backend v3: ordem do catálogo, doses comerciais e títulos sem 'Solo 1D'."""

import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient

import backend.app.main as backend_main
from backend.app.fertilizers import FERTILIZER_CHOICES, list_fertilizers


def test_list_fertilizers_order_and_labels_match_choices() -> None:
    items = list_fertilizers()
    assert [f["key"] for f in items] == list(FERTILIZER_CHOICES.values())
    assert [f["label"] for f in items] == list(FERTILIZER_CHOICES.keys())


def test_dose_polialita_200() -> None:
    with TestClient(backend_main.app) as client:
        r = client.post("/fertilizers/dose", json={"fert_key": "polialita", "gross_dose": 200})
    assert r.status_code == 200, r.text
    d = r.json()["elemental_doses"]
    assert d["K"] == 23.2
    assert d["S"] == 38.0
    assert d["Ca"] == 24.0
    assert d["Mg"] == 7.2
    assert d["N"] == 0
    assert d["P"] == 0


def test_dose_map_100() -> None:
    with TestClient(backend_main.app) as client:
        r = client.post("/fertilizers/dose", json={"fert_key": "map", "gross_dose": 100})
    assert r.status_code == 200, r.text
    d = r.json()["elemental_doses"]
    assert d["P"] == 22.7
    assert d["N"] == 11.0


def test_dose_kcl_200() -> None:
    with TestClient(backend_main.app) as client:
        r = client.post("/fertilizers/dose", json={"fert_key": "kcl", "gross_dose": 200})
    assert r.status_code == 200, r.text
    assert r.json()["elemental_doses"]["K"] == 104.8


def test_no_solo_1d_in_figure_titles() -> None:
    from hydrus_core import visualizer as viz

    for fn_name in ("plot_nutrient_profile", "plot_breakthrough_curves", "plot_profiles_at_days"):
        src = inspect.getsource(getattr(viz, fn_name))
        assert "Solo 1D" not in src, f"{fn_name} ainda contém 'Solo 1D'"
