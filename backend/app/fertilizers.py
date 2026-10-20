"""Lógica de fertilizantes comerciais e misturas, portada do app legado.

Origem: /workspace/hydrus/app_gradio.py
- FERTILIZER_CHOICES (rótulos do dropdown fert_choice);
- calculate_effective_dose (~linha 411);
- apply_blend_preset (presets de mistura / fertilizante personalizado);
- extração de teores % por nutriente (apply_commercial_fertilizer).

Não há física do solver aqui: só conversão dose bruta -> dose elementar.
"""

from __future__ import annotations

from hydrus_core.literature_database import COMMERCIAL_FERTILIZERS

# Rótulos do dropdown fert_choice do Gradio -> chave do COMMERCIAL_FERTILIZERS.
# "Dose Direta do Elemento (Personalizado)" = dose elementar direta ("direto").
FERTILIZER_CHOICES: dict[str, str] = {
    "Polialita / Polissulfato (11.6% K, 19% S, 12% Ca, 3.6% Mg)": "polialita",
    "Cloreto de Potássio - KCl (52.4% K)": "kcl",
    "KCl + Gesso Agrícola (26.2% K, 10% Ca, 8% S)": "kcl_gesso",
    "Ureia Convencional ou Protegida (45% N)": "ureia",
    "K-Mag / Sulpomag (18% K, 11% Mg, 22% S)": "kmag",
    "MAP - Fosfato Monoamônico (22.7% P + 11% N)": "map",
    "Sulfato de Amônio (21% N + 24% S)": "sulfato_amonio",
    "Nitrato de Amônio (33% N)": "nitrato_amonio",
    "Dose Direta do Elemento (Personalizado)": "direto",
}

NUTRIENT_ORDER = ("N", "K", "P", "S", "Ca", "Mg")


def fertilizer_nutrient_pcts(fert_key: str) -> dict[str, float]:
    """Teores elementares % por nutriente (port de apply_commercial_fertilizer)."""
    pcts = {s: 0.0 for s in NUTRIENT_ORDER}
    fert = COMMERCIAL_FERTILIZERS.get(fert_key) or {}
    for level, pct_key in (
        ("primary_nutrient", "nutrient_pct"),
        ("secondary_nutrient", "secondary_pct"),
        ("tertiary_nutrient", "tertiary_pct"),
        ("quaternary_nutrient", "quaternary_pct"),
    ):
        sym = fert.get(level)
        if sym in pcts:
            try:
                pcts[sym] = float(fert.get(pct_key, 0.0) or 0.0)
            except (TypeError, ValueError):
                pcts[sym] = 0.0
    return pcts


def fertilizer_display_name(fert_key: str) -> str:
    if fert_key == "direto":
        return "Dose Direta do Elemento"
    return (COMMERCIAL_FERTILIZERS.get(fert_key) or {}).get("name", fert_key)


# Presets de mistura do Gradio (apply_blend_preset): nome -> % por nutriente.
# Mesma ordem de retorno do Gradio: (N, K, P, S, Ca, Mg) com flags de ativação
# (teor > 0 = linha ativa na tabela).
BLEND_PRESETS: dict[str, dict[str, float]] = {
    "Polissulfato (blend)": {"N": 0.0, "K": 25.0, "P": 0.0, "S": 40.0, "Ca": 25.0, "Mg": 8.0},
    "MAP (blend)": {"N": 22.0, "K": 0.0, "P": 45.0, "S": 0.0, "Ca": 0.0, "Mg": 0.0},
    "K-Mag (blend)": {"N": 0.0, "K": 36.0, "P": 0.0, "S": 44.0, "Ca": 0.0, "Mg": 22.0},
    "Sulfato de Amônio (blend)": {"N": 42.0, "K": 0.0, "P": 0.0, "S": 48.0, "Ca": 0.0, "Mg": 0.0},
    "NPK (blend)": {"N": 50.0, "K": 50.0, "P": 15.0, "S": 0.0, "Ca": 0.0, "Mg": 0.0},
    "KCl (blend)": {"N": 0.0, "K": 100.0, "P": 0.0, "S": 0.0, "Ca": 0.0, "Mg": 0.0},
}


def blend_preset_pcts(preset_name: str) -> dict[str, float] | None:
    """Retorna os teores % do preset, com match parcial como no Gradio ("in")."""
    if preset_name in BLEND_PRESETS:
        return dict(BLEND_PRESETS[preset_name])
    for key in BLEND_PRESETS:
        base = key.split(" (")[0]
        if base in str(preset_name) or str(preset_name) in key:
            return dict(BLEND_PRESETS[key])
    return None


def resolve_nutrient_symbol(label: str) -> str:
    """Port de resolve_nutrient_symbol do Gradio (símbolo a partir do rótulo)."""
    if not label:
        return "K"
    if label in ["K", "N", "Ca", "Mg", "S", "P"]:
        return label
    if "Potássio" in label or "K+" in label:
        return "K"
    if "Cálcio" in label or "Ca2+" in label:
        return "Ca"
    if "Magnésio" in label or "Mg2+" in label:
        return "Mg"
    if "Enxofre" in label or "Sulfato" in label:
        return "S"
    if "Fósforo" in label or "Fosfato" in label:
        return "P"
    if "Nitrogênio" in label or "Nitrato" in label:
        return "N"
    return str(label).strip() or "K"


class FertilizerDoseError(ValueError):
    """Dose bruta inválida ou fertilizante sem o nutriente (vira 422 na API)."""


def calculate_effective_dose(fert_key: str, gross_dose: float, nutr_sym: str) -> tuple[float, str]:
    """Port fiel de calculate_effective_dose (app_gradio.py ~411).

    Retorna (dose_elementar_kg_ha, mensagem). Levanta FertilizerDoseError quando
    o adubo não contém o nutriente (no Gradio: gr.Error com a mesma mensagem).
    """
    nutr_sym = resolve_nutrient_symbol(nutr_sym)
    if fert_key == "direto":
        return gross_dose, f"Dose elementar direta: {gross_dose:.1f} kg/ha de {nutr_sym}"

    fert = COMMERCIAL_FERTILIZERS.get(fert_key)
    if not fert:
        return gross_dose, f"{gross_dose:.1f} kg/ha"

    pct = 0.0
    if fert.get("primary_nutrient") == nutr_sym:
        pct = fert.get("nutrient_pct", 0.0)
    elif fert.get("secondary_nutrient") == nutr_sym:
        pct = fert.get("secondary_pct", 0.0)
    elif fert.get("tertiary_nutrient") == nutr_sym:
        pct = fert.get("tertiary_pct", 0.0)
    elif fert.get("quaternary_nutrient") == nutr_sym:
        pct = fert.get("quaternary_pct", 0.0)

    if pct > 0:
        elemental = gross_dose * (pct / 100.0)
        msg = (
            f"Dose bruta de {gross_dose:.0f} kg/ha de {fert['name']} contém "
            f"{elemental:.1f} kg/ha de {nutr_sym} líquido ({pct:.1f}% de teor)."
        )
        return elemental, msg
    else:
        raise FertilizerDoseError(
            f"O adubo '{fert['name']}' não contém {nutr_sym} (teor 0%). "
            "Informe a dose elementar direta ou escolha um fertilizante fonte do nutriente."
        )


def elemental_doses_for_pcts(pcts: dict[str, float], gross_dose: float) -> dict[str, float]:
    """Dose elementar por nutriente a partir de teores % (comercial, blend ou custom)."""
    return {
        sym: round(float(gross_dose) * (float(pcts.get(sym, 0.0) or 0.0) / 100.0), 4)
        for sym in NUTRIENT_ORDER
    }


def list_fertilizers() -> list[dict]:
    """Catálogo p/ GET /fertilizers: comerciais + rótulos Gradio + blend presets.

    Ordem = FERTILIZER_CHOICES (polialita primeiro, direto por último),
    mesmos rótulos do Gradio.
    """
    out: list[dict] = []
    for label, key in FERTILIZER_CHOICES.items():
        if key == "direto":
            out.append(
                {
                    "key": "direto",
                    "label": "Dose Direta do Elemento (Personalizado)",
                    "name": "Dose Direta do Elemento",
                    "nutrient_pcts": {s: 0.0 for s in NUTRIENT_ORDER},
                    "descr": "Dose elementar direta, sem conversão por teor.",
                }
            )
            continue
        fert = COMMERCIAL_FERTILIZERS.get(key) or {}
        if not fert:
            continue
        out.append(
            {
                "key": key,
                "label": label,
                "name": fert.get("name", key),
                "nutrient_pcts": fertilizer_nutrient_pcts(key),
                "descr": fert.get("descr", ""),
            }
        )
    return out


def list_blend_presets() -> list[dict]:
    return [{"key": k, "label": k, "nutrient_pcts": dict(v)} for k, v in BLEND_PRESETS.items()]
