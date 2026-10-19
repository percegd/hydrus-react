"""Climatologia real dos polos agrícolas (chuva + ET0).

Carrega ``data/hub_climate.json`` — dados diários reais da NASA POWER para uma
série de anos, dos quais cada cenário usa **um ano observado** (escolhido pela
precipitação anual). A ET0 é calculada por FAO-56 Penman-Monteith
(``core/et0.py``) a partir das variáveis meteorológicas do MESMO ano.

Ver ``scripts/fetch_hub_climate.py`` para (re)gerar o arquivo de dados.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Optional

import numpy as np

from hydrus_core.et0 import fao56_penman_monteith

_DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "hub_climate.json")


@lru_cache(maxsize=1)
def _load() -> dict:
    try:
        with open(_DATA_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def has_hub_climate(hub_key: str) -> bool:
    return hub_key in _load()


def hub_mean_annual_mm(hub_key: str) -> Optional[float]:
    """Precipitação média anual observada (NASA POWER) do polo, ou None."""
    data = _load().get(hub_key)
    if not data:
        return None
    val = data.get("mean_annual_mm")
    return float(val) if val is not None else None


def hub_climate_series(hub_key: str, scenario: str = "medio") -> Optional[dict]:
    """Série diária (365 dias) do polo/cenário: chuva real e ET0 calculada.

    Retorna ``{"rain": np.ndarray, "et0": np.ndarray, "year": int}`` ou ``None``
    se os dados do polo/cenário não estiverem disponíveis.
    """
    data = _load().get(hub_key)
    if not data:
        return None
    scen = (data.get("scenarios") or {}).get(scenario)
    if not scen:
        return None
    try:
        rain = np.asarray(scen["rain"], dtype=float)
        et0 = fao56_penman_monteith(
            tmax=scen["tmax"], tmin=scen["tmin"], rs=scen["rs"],
            rh=scen["rh"], wind=scen["wind"], ps=scen["ps"],
            elev_m=float(data.get("elev_m") or 0.0),
            lat_deg=float(data["lat"]),
        )
    except (KeyError, TypeError, ValueError):
        return None
    return {"rain": np.round(rain, 1), "et0": np.round(np.asarray(et0, dtype=float), 2),
            "year": int(scen.get("year", 0))}
