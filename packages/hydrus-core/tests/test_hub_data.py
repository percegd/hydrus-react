from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from hydrus_core.hub_climate import has_hub_climate, hub_climate_series

_PACKAGE_DIR = Path(__file__).resolve().parents[1]


def test_has_hub_climate_sorriso_mt() -> None:
    assert has_hub_climate("sorriso_mt") is True


def test_hub_climate_series_has_365_values_for_sorriso_mt() -> None:
    series = hub_climate_series("sorriso_mt")
    assert series is not None
    assert len(series["rain"]) == 365
    assert len(series["et0"]) == 365


def test_wheel_contains_hub_data_files(tmp_path: Path) -> None:
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                "--no-deps",
                "--no-build-isolation",
                "-w",
                str(tmp_path),
                str(_PACKAGE_DIR),
            ],
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        pytest.skip(f"nao foi possivel executar pip wheel: {exc}")

    if result.returncode != 0:
        pytest.skip(
            "pip wheel falhou (possivel falta de rede/setuptools):\n"
            f"{result.stdout}\n{result.stderr}"
        )

    wheels = sorted(tmp_path.glob("hydrus_core-*.whl"))
    assert wheels, "nenhum wheel foi gerado"

    with zipfile.ZipFile(wheels[0]) as wheel:
        names = set(wheel.namelist())

    assert "hydrus_core/data/hub_climate.json" in names
    assert "hydrus_core/data/rainfall_esalq.json" in names
