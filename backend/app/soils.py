"""Solo personalizado (Rosetta) e Kd de literatura por textura.

Portado de /workspace/hydrus/app_gradio.py:
- update_rosetta_parameters (Rosetta -> van Genuchten);
- get_soil_texture (textura arenoso/medio/argiloso);
- get_nutrient_literature_kd / compute_solute_kd_and_badge (Kd + citação);
- granulometria padrão da interface (Passo 1).
"""

from __future__ import annotations

from typing import Any

from hydrus_core.literature_database import get_kd_literature_data, get_langmuir_params
from hydrus_core.soil_physics import (
    RosettaUnavailableError,
    SoilParameters,
    classify_texture,
    estimate_ptf_rosetta,
)
from hydrus_core.soil_physics import SOIL_DATABASE

# Solo e granulometria padrão da interface (Passo 1 do Gradio).
DEFAULT_SOIL_KEY = "latossolo_medio"
DEFAULT_SAND_PCT = 60.0
DEFAULT_CLAY_PCT = 25.0
DEFAULT_BULK_DENSITY = 1.35

# Defaults dos campos editáveis (valores iniciais do Gradio, Passo 1).
DEFAULT_CUSTOM_FIELDS = {
    "theta_r": 0.1,
    "theta_s": 0.43,
    "alpha": 0.03,
    "n": 1.65,
    "ks": 80.0,
    "bulk_density": 1.3,
}

# Kd de coluna experimental (Gradio: get_nutrient_literature_kd casos especiais).
PUB_LVA_KD = {"K": 0.2350, "Ca": 2.0411, "Mg": 0.0000, "S": 0.0000, "N": 0.0000, "P": 5.0}
PUB_NV_KD = {"K": 0.5189, "Ca": 0.2289, "Mg": 0.1460, "S": 0.0332, "N": 0.0200, "P": 80.0}


def rosetta_params(sand: float, clay: float, bulk_density: float | None = None) -> dict[str, float]:
    """Port de update_rosetta_parameters: Rosetta -> van Genuchten (arredondado)."""
    bd = float(bulk_density) if bulk_density not in (None, "") else DEFAULT_BULK_DENSITY
    p = estimate_ptf_rosetta(float(sand or 60), float(clay or 25), bulk_density=bd)
    return {
        "theta_r": round(p.theta_r, 4),
        "theta_s": round(p.theta_s, 4),
        "alpha": round(p.alpha, 4),
        "n": round(p.n, 3),
        "ks": round(p.ks, 2),
        "bulk_density": round(p.bulk_density, 2),
    }


def get_soil_texture(
    soil_key: str, soil: Any = None, sand_pct: float = 60.0, clay_pct: float = 25.0
) -> str:
    """Port de get_soil_texture do Gradio."""
    if soil_key == "custom":
        return classify_texture(sand_pct, clay_pct)
    if soil is not None and (
        getattr(soil, "sand_pct", None) is not None or getattr(soil, "clay_pct", None) is not None
    ):
        return classify_texture(getattr(soil, "sand_pct", None), getattr(soil, "clay_pct", None))
    if soil_key in ["neossolo_arenoso", "pub_lva_arenoso"]:
        return "arenoso"
    if soil_key in ["latossolo_argiloso", "argila_pesada", "pub_nv_argiloso"]:
        return "argiloso"
    if soil is not None:
        if getattr(soil, "n", 1.5) > 1.8:
            return "arenoso"
        if getattr(soil, "n", 1.5) < 1.3 or getattr(soil, "theta_s", 0.4) > 0.48:
            return "argiloso"
    return "medio"


def texture_for(soil_key: str | None, sand: float | None, clay: float | None) -> str:
    """Textura p/ lookup de Kd (solo da lista ou granulometria custom)."""
    if soil_key and soil_key != "custom" and soil_key in SOIL_DATABASE:
        soil = SOIL_DATABASE[soil_key]
        return get_soil_texture(soil_key, soil, sand or 60.0, clay or 25.0)
    return classify_texture(sand if sand is not None else 60.0, clay if clay is not None else 25.0)


def literature_kd(sym: str, soil_key: str | None, sand: float | None, clay: float | None) -> dict:
    """Kd de literatura + citação do Gradio (default_literature_kd / _badge).

    Solos de coluna experimental (pub_*) usam os Kd ajustados; demais usam a
    tabela por textura. Soluto fora de N,K,P,S,Ca,Mg = traçador (Kd 0.20).
    """
    sym = str(sym or "").strip()
    key = soil_key or (None if (sand is not None or clay is not None) else DEFAULT_SOIL_KEY)
    if key is None:
        key = "custom"
    if sym not in ("N", "K", "P", "S", "Ca", "Mg"):
        return {
            "symbol": sym,
            "kd": 0.20,
            "citation": "HYDRUS-1D Ensaio Padrão (Laboratório)",
            "description": "Traçador / soluto de referência com adsorção linear no meio poroso.",
        }
    if key == "pub_lva_arenoso":
        return {
            "symbol": sym,
            "kd": float(PUB_LVA_KD.get(sym, 0.235)),
            "citation": "PUB Arthur / ESALQ (LVA Arenoso)",
            "description": "Ajustado em coluna experimental de Latossolo Vermelho-Amarelo.",
        }
    if key == "pub_nv_argiloso":
        return {
            "symbol": sym,
            "kd": float(PUB_NV_KD.get(sym, 0.5189)),
            "citation": "TCC Isabela / ESALQ (NV Argiloso)",
            "description": "Ajustado em coluna experimental de Nitossolo Vermelho Eutrófico.",
        }
    texture = texture_for(None if key == "custom" else key, sand, clay)
    entry = get_kd_literature_data(sym, texture)
    out = {
        "symbol": sym,
        "kd": float(entry.default_kd),
        "citation": entry.citation,
        "description": entry.description,
        "texture": texture,
    }
    if sym == "P":
        try:
            lg = get_langmuir_params("P", texture)
            out["langmuir"] = {
                "smax_mg_g": float(lg.smax_mg_g),
                "kl_cm3_mg": float(lg.kl_cm3_mg),
                "citation": lg.citation,
                "description": lg.description,
            }
        except KeyError:
            pass
    return out


def resolve_custom_soil(
    sand_pct: float,
    clay_pct: float,
    bulk_density: float | None = None,
    overrides: dict[str, float | None] | None = None,
) -> SoilParameters:
    """Solo personalizado: base Rosetta + overrides editáveis (Gradio run_wizard).

    Levanta RosettaUnavailableError se a Rosetta falhar (sem fallback).
    """
    base = estimate_ptf_rosetta(
        float(sand_pct), float(clay_pct),
        bulk_density=float(bulk_density) if bulk_density not in (None, "") else 1.35,
    )
    ov = overrides or {}

    def _pick(name: str, default: float) -> float:
        v = ov.get(name)
        if v is None or (isinstance(v, str) and not str(v).strip()):
            return float(default)
        return float(v)

    return SoilParameters(
        name=f"Solo Personalizado ({float(sand_pct):.0f}% Areia, {float(clay_pct):.0f}% Argila)",
        descr="Parâmetros físico-químicos do solo",
        theta_r=_pick("theta_r", base.theta_r),
        theta_s=_pick("theta_s", base.theta_s),
        alpha=_pick("alpha", base.alpha),
        n=_pick("n", base.n),
        ks=_pick("ks", base.ks),
        bulk_density=_pick("bulk_density", base.bulk_density),
        l=0.5,
    )


__all__ = [
    "DEFAULT_SOIL_KEY",
    "DEFAULT_SAND_PCT",
    "DEFAULT_CLAY_PCT",
    "DEFAULT_BULK_DENSITY",
    "DEFAULT_CUSTOM_FIELDS",
    "RosettaUnavailableError",
    "rosetta_params",
    "get_soil_texture",
    "texture_for",
    "literature_kd",
    "resolve_custom_soil",
]
