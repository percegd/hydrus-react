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

    # Solo pelo soil_key (central valida soil_choice contra labels válidos),
    # ou personalizado via custom_soil (Gradio is_custom_soil + Rosetta).
    if req.custom_soil is not None:
        p["soil_choice"] = req.soil_key or "custom"
        p["is_custom_soil"] = True
        try:
            p["sand_pct"] = float(req.custom_soil.sand_pct)
        except (TypeError, ValueError):
            p["sand_pct"] = req.custom_soil.sand_pct
        try:
            p["clay_pct"] = float(req.custom_soil.clay_pct)
        except (TypeError, ValueError):
            p["clay_pct"] = req.custom_soil.clay_pct
        for _attr, _key in (
            ("theta_r", "adv_theta_r"),
            ("theta_s", "adv_theta_s"),
            ("alpha", "adv_alpha"),
            ("n", "adv_n"),
            ("ks", "adv_ks"),
            ("bulk_density", "adv_bulk_density"),
        ):
            _v = getattr(req.custom_soil, _attr, None)
            if _v is not None:
                p[_key] = _v
    else:
        p["soil_choice"] = req.soil_key
        p["is_custom_soil"] = False
    try:
        p["_soil_labels"] = set(SOIL_DATABASE.keys())
    except Exception:
        pass

    # Cultura (Gradio crop params box: nome editável + raiz + Kc + Feddes h1..h4).
    # crop_key="custom" = cultura personalizada (nome + params dos campos).
    if req.crop_key:
        p["crop_mode"] = "Com cultura"
        if req.crop_key == "custom":
            p["crop_name"] = (str(req.crop_name).strip() if req.crop_name else "") or "Cultura Personalizada"
        else:
            p["crop_name"] = (str(req.crop_name).strip() if req.crop_name else "") or req.crop_key
        try:
            crop = CROP_DATABASE.get(req.crop_key)
        except Exception:
            crop = None
        # Base do banco (quando há) + overrides dos campos editáveis.
        if crop is not None:
            if req.crop_name and str(req.crop_name).strip():
                # Nome que casa com o banco mantém rótulo; senão é personalizada
                # (a regra de stage vive no service; aqui só repassa o nome).
                pass
            else:
                p["crop_name"] = crop.name
            base_root = float(crop.root_depth_cm)
            base_kc = float(crop.kc)
            base_h = (float(crop.h1), float(crop.h2), float(crop.h3), float(crop.h4))
        else:
            base_root, base_kc = 35.0, 1.0
            base_h = (-15.0, -30.0, -450.0, -12000.0)
        try:
            p["crop_root_depth"] = float(req.root_depth_cm) if req.root_depth_cm is not None else base_root
        except (TypeError, ValueError):
            p["crop_root_depth"] = req.root_depth_cm
        try:
            p["crop_kc"] = float(req.kc) if req.kc is not None else base_kc
        except (TypeError, ValueError):
            p["crop_kc"] = req.kc
        for _attr, _key, _fb in (
            ("h1", "crop_h1", base_h[0]),
            ("h2", "crop_h2", base_h[1]),
            ("h3", "crop_h3", base_h[2]),
            ("h4", "crop_h4", base_h[3]),
        ):
            _v = getattr(req, _attr, None)
            try:
                p[_key] = float(_v) if _v is not None else _fb
            except (TypeError, ValueError):
                p[_key] = _v
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
    # ET avançada (Gradio adv_et_toggle): 0 = derivar de ET0.
    try:
        p["evap_mm_day"] = float(req.evap_mm_day)
    except (TypeError, ValueError):
        p["evap_mm_day"] = req.evap_mm_day
    try:
        p["transp_mm_day"] = float(req.transp_mm_day)
    except (TypeError, ValueError):
        p["transp_mm_day"] = req.transp_mm_day
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

    # Janela de análise + dias de leitura (Gradio: validate_analysis_window).
    # print_days=None = ausente (API legada: marcos automáticos, sem erro);
    # lista vazia = texto vazio (Gradio bloqueia: "não pode ficar vazio").
    try:
        p["analysis_start_day"] = int(req.analysis_start_day)
    except (TypeError, ValueError):
        p["analysis_start_day"] = req.analysis_start_day
    try:
        p["analysis_end_day"] = int(req.analysis_end_day)
    except (TypeError, ValueError):
        p["analysis_end_day"] = req.analysis_end_day
    if req.print_days is not None:
        p["print_days_text"] = ", ".join(
            str(int(v) if float(v).is_integer() else str(float(v))) for v in req.print_days
        )

    # Solutos: linhas NPK + 3 "Outro soluto" (mesmas chaves do Gradio).
    # T5: modo "Somente água" não exige soluto (validate_nutrients só cobra
    # soluto com dose > 0 no modo "Água + nutrientes").
    p["simulation_mode"] = "Somente água" if req.water_only else "Água + nutrientes"
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
    # F1) posicionamento desconhecido (antes caía silenciosamente em superfície).
    try:
        _mode_raw = str((req.placement.mode if req.placement else "") or "")
        if _mode_raw.strip().lower() not in ("surface", "furrow", "custom", "fertigation"):
            out.append({"field": "placement.mode", "message": f"Posicionamento desconhecido: {_mode_raw}."})
    except Exception:
        pass
    # F2) modo Lâmina (sem rain_series) com dia da aplicação além do ensaio:
    # nenhum adubo entra no perfil (todos os % viram 0).
    try:
        if not req.rain_series and (req.solutes or []) and not (
            str((req.placement.mode if req.placement else "") or "").strip().lower() == "fertigation"
        ):
            _app = float(req.placement.application_day or 0.0)
            _td = float(req.total_days or 0.0)
            if _app >= _td:
                out.append({
                    "field": "placement.application_day",
                    "message": (
                        f"Dia da aplicação ({_app:g}) deve ser menor que a duração do ensaio "
                        f"({int(_td)} dias); com o valor atual nenhum adubo entra no perfil."
                    ),
                })
    except (TypeError, ValueError):
        pass
    return out
