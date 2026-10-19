"""Ponte backend -> validacao central do hydrus-core.

Converte SimulateRequest (backend/app/schemas.py) no payload dict esperado por
hydrus_core.input_validation.validate_payload (mesmas chaves que o Gradio usa
em /workspace/hydrus/app_gradio.py) e retorna lista de {field, message} apenas
para issues de severidade erro (avisos nao bloqueiam, quando houver o conceito).
"""

from __future__ import annotations

from typing import Any

from hydrus_core.input_validation import NUTRIENT_SYMBOLS, validate_payload

from .schemas import SimulateRequest


def _is_error_issue(issue: Any) -> bool:
    """Só severidade erro bloqueia. Sem conceito de severidade -> tudo é erro."""
    for attr in ("severity", "level", "kind"):
        if hasattr(issue, attr):
            try:
                val = str(getattr(issue, attr) or "error").strip().lower()
            except Exception:
                return True
            if val in ("error", "erro", "err", "blocking", "blocker", "fatal"):
                return True
            if val in ("warning", "warn", "aviso", "info", "information", "debug"):
                return False
            return True
    if getattr(issue, "is_warning", False) or getattr(issue, "warning", False):
        return False
    return True


def _release_label(release_type: str) -> str:
    rt = str(release_type or "immediate").strip().lower()
    if rt in ("controlled", "controlada", "lenta", "crf"):
        return "Controlada"
    return "Imediata"


def _placement_label(mode: str) -> str:
    m = str(mode or "surface").strip().lower()
    if m == "fertigation":
        return "Fertirrigação"
    if m in ("custom", "personalizada", "customizada"):
        return "Profundidade Personalizada"
    if m == "furrow":
        return "No Sulco de Plantio (5 a 10 cm)"
    return "A lanço / Superfície (0 a 2 cm)"


def build_payload(req: SimulateRequest) -> dict:
    """Monta o payload nas chaves do Gradio a partir do SimulateRequest."""
    from hydrus_core.crop import CROP_DATABASE
    from hydrus_core.soil_physics import SOIL_DATABASE

    p: dict = {}

    # Solo pelo soil_key (central valida soil_choice contra labels válidos).
    p["soil_choice"] = req.soil_key
    p["is_custom_soil"] = False
    try:
        p["_soil_labels"] = set(SOIL_DATABASE.keys())
    except Exception:
        pass

    # Cultura.
    if req.crop_key:
        p["crop_mode"] = "Com cultura"
        p["crop_name"] = req.crop_key
        try:
            crop = CROP_DATABASE.get(req.crop_key)
        except Exception:
            crop = None
        if crop is not None:
            try:
                p["crop_root_depth"] = float(crop.root_depth_cm)
            except (TypeError, ValueError):
                pass
            try:
                p["crop_kc"] = float(crop.kc)
            except (TypeError, ValueError):
                pass
        elif req.root_depth_cm is not None:
            p["crop_root_depth"] = float(req.root_depth_cm)
        if req.root_depth_cm is not None and "crop_root_depth" not in p:
            p["crop_root_depth"] = float(req.root_depth_cm)
    else:
        p["crop_mode"] = "Sem cultura (perfil nu)"

    # Domínio.
    p["domain_depth_cm"] = float(req.depth_cm)

    # Regime hídrico: chuva/série + ET0 + umidade + dia de aplicação.
    if req.rain_series:
        try:
            series = [float(v) for v in req.rain_series]
        except (TypeError, ValueError):
            series = []
        p["water_source"] = "Série climática"
        p["total_days"] = float(len(series))
        try:
            p["rain_mm"] = float(sum(series))
        except (TypeError, ValueError):
            p["rain_mm"] = float(req.rain_mm)
    else:
        p["water_source"] = "Lâmina de chuva/irrigação"
        p["rain_mm"] = float(req.rain_mm)
        p["total_days"] = float(req.total_days)
    p["initial_moisture_pct"] = float(req.initial_moisture_pct)
    if req.et0_series:
        try:
            vals = [float(v) for v in req.et0_series]
            p["et0_mm_day"] = float(sum(vals) / max(len(vals), 1))
        except (TypeError, ValueError):
            p["et0_mm_day"] = float(req.et0_mm_day)
    else:
        p["et0_mm_day"] = float(req.et0_mm_day)
    try:
        p["app_day"] = float(req.placement.application_day or 0.0)
    except (TypeError, ValueError):
        p["app_day"] = 0.0

    # Solutos: linhas NPK + 3 "Outro soluto" (mesmas chaves do Gradio).
    p["simulation_mode"] = "Água + nutrientes"
    custom_slots = ("x", "x2", "x3")
    custom_idx = 0
    overflow: list[dict] = []
    for s in req.solutes or []:
        sym = str(s.symbol or "").strip()
        upper = sym.upper()
        dose = float(s.dose_kg_ha)
        kd = s.kd
        disp = s.dispersivity_cm
        res = s.initial_residual_mg_dm3
        if upper in NUTRIENT_SYMBOLS:
            low = upper.lower()
            p[f"multi_{low}_active"] = True
            p[f"multi_{low}_dose"] = dose
            p[f"multi_{low}_kd"] = kd
            p[f"multi_{low}_disp"] = disp
            p[f"multi_{low}_res"] = res
        elif custom_idx < len(custom_slots):
            slot = custom_slots[custom_idx]
            custom_idx += 1
            p[f"multi_{slot}_active"] = True
            p[f"multi_{slot}_name"] = sym
            p[f"multi_{slot}_dose"] = dose
            p[f"multi_{slot}_kd"] = kd
            p[f"multi_{slot}_disp"] = disp
            p[f"multi_{slot}_res"] = res
        else:
            overflow.append({"symbol": sym, "dose": dose, "kd": kd, "disp": disp, "res": res})

    # Liberação (global no Gradio; usa o 1º soluto como referência).
    if req.solutes:
        first = req.solutes[0]
        p["release_type"] = _release_label(first.release_type)
        try:
            p["release_days"] = float(first.release_days or 60.0)
        except (TypeError, ValueError):
            p["release_days"] = 60.0

    # Posicionamento / fertirrigação.
    p["placement_mode"] = _placement_label(req.placement.mode)
    try:
        p["z_app_top_cm"] = float(req.placement.z_top_cm)
    except (TypeError, ValueError):
        pass
    try:
        p["z_app_bottom_cm"] = float(req.placement.z_bottom_cm)
    except (TypeError, ValueError):
        pass
    try:
        p["fert_c0_mg_l"] = float(req.placement.fertigation_c0_mg_l)
    except (TypeError, ValueError):
        pass
    try:
        p["fert_pulse_days"] = float(req.placement.fertigation_pulse_days)
    except (TypeError, ValueError):
        pass

    p["_overflow_solutes"] = overflow
    return p


def validate_request(req: SimulateRequest) -> list[dict]:
    """Valida o SimulateRequest via núcleo central; retorna [{field, message}]."""
    payload = build_payload(req)
    overflow = payload.pop("_overflow_solutes", [])
    soil_labels = payload.pop("_soil_labels", None)
    try:
        issues = validate_payload(payload, soil_labels=soil_labels)
    except TypeError:
        issues = validate_payload(payload)
    out: list[dict] = []
    for iss in issues or []:
        if not _is_error_issue(iss):
            continue
        field = str(getattr(iss, "field", "geral") or "geral")
        message = str(getattr(iss, "message", "") or "")
        if not message:
            continue
        out.append({"field": field, "message": message})
    # Solutos além dos 3 slots custom: mesmas regras físicas do núcleo.
    for extra in overflow:
        sym = str(extra.get("symbol") or "?")
        try:
            d = float(extra.get("dose"))
        except (TypeError, ValueError):
            out.append({"field": f"dose_{sym}", "message": f"Dose de {sym} deve ser numérica."})
            continue
        if d < 0:
            out.append({"field": f"dose_{sym}", "message": f"Dose de {sym} ({d:.1f} kg/ha) não pode ser negativa."})
        elif d == 0:
            out.append({"field": f"dose_{sym}", "message": f"{sym} marcado com dose 0 kg/ha. Informe a dose aplicada ou remova o soluto."})
        elif d > 10000:
            out.append({"field": f"dose_{sym}", "message": f"Dose de {sym} ({d:.0f} kg/ha) acima de 10000 kg/ha elementar: provável erro de digitação."})
        for key, label in (("kd", "Kd"), ("disp", "Dispersividade λ"), ("res", "Residual")):
            try:
                v = extra.get(key)
                if v is None or (isinstance(v, str) and not v.strip()):
                    continue
                f = float(v)
            except (TypeError, ValueError):
                out.append({"field": f"{key}_{sym}", "message": f"{label} de {sym} deve ser numérico."})
                continue
            if f < 0:
                out.append({"field": f"{key}_{sym}", "message": f"{label} de {sym} ({f}) não pode ser negativo."})
    # Séries diárias: valores fisicamente impossíveis (< 0 / NaN).
    try:
        if req.rain_series:
            for i, v in enumerate(req.rain_series):
                try:
                    f = float(v)
                except (TypeError, ValueError):
                    out.append({"field": "rain_series", "message": f"Série de chuva no dia {i + 1} deve ser numérica."})
                    break
                import math as _math

                if _math.isnan(f) or _math.isinf(f) or f < 0:
                    out.append({"field": "rain_series", "message": f"Série de chuva no dia {i + 1} ({v}) é fisicamente impossível: exige-se ≥ 0."})
                    break
        if req.et0_series:
            for i, v in enumerate(req.et0_series):
                try:
                    f = float(v)
                except (TypeError, ValueError):
                    out.append({"field": "et0_series", "message": f"Série de ET0 no dia {i + 1} deve ser numérica."})
                    break
                import math as _math

                if _math.isnan(f) or _math.isinf(f) or f < 0:
                    out.append({"field": "et0_series", "message": f"Série de ET0 no dia {i + 1} ({v}) é fisicamente impossível: exige-se ≥ 0."})
                    break
    except Exception:
        pass
    return out
