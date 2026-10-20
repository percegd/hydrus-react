"""UI/backend v3: ordem do catálogo, doses comerciais e títulos sem 'Solo 1D'."""

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
    assert d["S"] == 38.4
    assert d["Ca"] == 24.4
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
    assert r.json()["elemental_doses"]["K"] == 99.6


def test_no_solo_1d_anywhere_in_repo() -> None:
    """Zero ocorrências de 'solo 1d' (case-insensitive) no repo.

    Varre core, backend/app, frontend/app, frontend/components e frontend/lib
    (fora de node_modules/.next): UI, laudo, passo a passo, títulos de gráfico,
    downloads/HTML/Excel, comentários de CSS e strings do backend/core.
    """
    import re

    roots = [
        ROOT / "packages" / "hydrus-core",
        ROOT / "backend" / "app",
        ROOT / "frontend" / "app",
        ROOT / "frontend" / "components",
        ROOT / "frontend" / "lib",
    ]
    pattern = re.compile(r"solo\s*1d", re.IGNORECASE)
    hits: list[str] = []
    skip_dirs = {"node_modules", ".next", "__pycache__", ".git"}
    for base in roots:
        assert base.is_dir(), f"diretório ausente: {base}"
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            if any(part in skip_dirs for part in path.parts):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for i, line in enumerate(text.splitlines(), 1):
                if pattern.search(line):
                    hits.append(f"{path.relative_to(ROOT)}:{i}: {line.strip()[:120]}")
    assert not hits, "ocorrências de 'Solo 1D' ainda presentes:\n" + "\n".join(hits)
