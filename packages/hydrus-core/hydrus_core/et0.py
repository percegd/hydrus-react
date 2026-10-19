"""ET0 de referência por FAO-56 Penman-Monteith.

Calcula a evapotranspiração de referência (ET0) a partir de variáveis
meteorológicas diárias, seguindo FAO Irrigation and Drainage Paper 56
(Allen et al., 1998), Eq. 6 (Penman-Monteith), com as rotinas intermediárias
de radiação (Eq. 21, 37-40) e pressão atmosférica.

Este módulo contém apenas a formulação física. Os dados meteorológicos reais
dos polos vivem em ``data/hub_climate.json`` e são carregados por
``core/hub_climate.py``.
"""

from __future__ import annotations

import numpy as np

# Constantes FAO-56
_GSC = 0.0820          # constante solar [MJ m-2 min-1]
_SIGMA = 4.903e-9      # Stefan-Boltzmann [MJ K-4 m-2 day-1]
_ALBEDO = 0.23         # cultura de referência (grama)
_C_N = 900.0           # coeficiente numérico FAO-56
_C_D = 0.34            # coeficiente do vento FAO-56


def _sat_vp(t: np.ndarray) -> np.ndarray:
    """Pressão de saturação do vapor (kPa) para temperatura em °C (FAO-56 Eq. 11)."""
    return 0.6108 * np.exp((17.27 * t) / (t + 237.3))


def _extraterrestrial_radiation(lat_deg: float, days: np.ndarray) -> np.ndarray:
    """Radiação extraterrestre Ra [MJ m-2 day-1] (FAO-56 Eq. 21)."""
    phi = np.radians(lat_deg)
    dr = 1.0 + 0.033 * np.cos(2.0 * np.pi / 365.0 * days)
    decl = 0.409 * np.sin(2.0 * np.pi / 365.0 * days - 1.39)
    x = np.clip(-np.tan(phi) * np.tan(decl), -1.0, 1.0)
    ws = np.arccos(x)
    ra = (24.0 * 60.0 / np.pi) * _GSC * dr * (
        ws * np.sin(phi) * np.sin(decl) + np.cos(phi) * np.cos(decl) * np.sin(ws)
    )
    return ra


def fao56_penman_monteith(tmax, tmin, rs, rh, wind, ps, elev_m, lat_deg) -> np.ndarray:
    """ET0 diária [mm/dia] por FAO-56 Penman-Monteith.

    Parâmetros (arrays de 365 dias):
        tmax, tmin : temperaturas máxima/mínima [°C]
        rs         : radiação solar de onda curta [MJ m-2 day-1]
        rh         : umidade relativa média [%]
        wind       : velocidade do vento a 2 m [m/s]
        ps         : pressão atmosférica de superfície [kPa]
        elev_m     : altitude [m]
        lat_deg    : latitude [graus]
    """
    n = len(np.atleast_1d(tmax))
    days = np.arange(1, n + 1)

    tmax = np.asarray(tmax, dtype=float)
    tmin = np.asarray(tmin, dtype=float)
    rs = np.asarray(rs, dtype=float)
    rh = np.asarray(rh, dtype=float)
    wind = np.asarray(wind, dtype=float)
    ps = np.asarray(ps, dtype=float)

    tmean = (tmax + tmin) / 2.0
    es = (_sat_vp(tmax) + _sat_vp(tmin)) / 2.0        # kPa
    ea = np.clip(rh, 1.0, 100.0) / 100.0 * es         # kPa

    # Pressão atmosférica (usa PS da NASA; fallback pela altitude)
    p = np.where(np.isfinite(ps) & (ps > 50.0), ps,
                 101.3 * ((293.0 - 0.0065 * elev_m) / 293.0) ** 5.26)
    gamma = 0.000665 * p                              # kPa/°C
    delta = (4098.0 * _sat_vp(tmean)) / (tmean + 237.3) ** 2  # kPa/°C

    ra = _extraterrestrial_radiation(lat_deg, days)
    rso = (0.75 + 2e-5 * elev_m) * ra
    rns = (1.0 - _ALBEDO) * rs
    ratio = np.clip(np.divide(rs, rso, out=np.zeros_like(rs), where=rso > 0), 0.0, 1.0)
    tmaxk = tmax + 273.16
    tmink = tmin + 273.16
    rnl = _SIGMA * ((tmaxk ** 4 + tmink ** 4) / 2.0) * (0.34 - 0.14 * np.sqrt(ea)) * (1.35 * ratio - 0.35)
    rn = rns - rnl                # G = 0 (diário)

    num = 0.408 * delta * rn + gamma * (_C_N / (tmean + 273.0)) * wind * (es - ea)
    den = delta + gamma * (1.0 + _C_D * wind)
    et0 = np.divide(num, den, out=np.zeros_like(num), where=den != 0)
    return np.clip(et0, 0.0, None)
