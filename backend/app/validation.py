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
    try:
        _moist_v = float(req.seasonal_initial_moisture_pct) if req.rain_series else float(req.initial_moisture_pct)
    except (TypeError, ValueError):
        _moist_v = float(req.initial_moisture_pct)
    p["initial_moisture_pct"] = _moist_v
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
    # F3) dia do plantio fora do intervalo [1, n_dias] (ciclo da cultura, modo série).
    try:
        if req.planting_day is not None:
            _pd = int(req.planting_day)
            _n_dias = len(req.rain_series) if req.rain_series else int(float(req.total_days or 0.0))
            if _n_dias < 1:
                _n_dias = 1
            if not (1 <= _pd <= _n_dias):
                out.append({
                    "field": "planting_day",
                    "message": (
                        f"Dia do plantio ({_pd}) fora do intervalo [1, {_n_dias} dias]: "
                        f"o plantio precisa cair dentro do período simulado."
                    ),
                })
    except (TypeError, ValueError):
        pass
    # F4) fertirrigação sem água no período de injeção (C0 = dose ÷ 0 é impossível).
    try:
        _is_fert_v = str((req.placement.mode if req.placement else "") or "").strip().lower() == "fertigation"
        if _is_fert_v and (req.solutes or []):
            from .service import _effective_window as _eff_win_v
            from .service import _fertigation_water_mm as _fert_w_mm_v

            if req.rain_series:
                _full_v = [max(0.0, float(v or 0.0)) for v in req.rain_series]
                _sw_v, _ew_v = _eff_win_v(req, len(_full_v))
                _series_v = _full_v[_sw_v - 1:_ew_v]
                _evs_v = [(float(d), 1.0, float(v)) for d, v in enumerate(_series_v) if v > 0.0]
                try:
                    _app_raw_v = float(req.placement.application_day or 0.0)
                except (TypeError, ValueError):
                    _app_raw_v = 0.0
                _app_eff_v = (_app_raw_v - _sw_v + 1) if _app_raw_v else 0.0
            else:
                try:
                    _rain_v = float(req.rain_mm)
                except (TypeError, ValueError):
                    _rain_v = 0.0
                _evs_v = [(0.5, 0.3, float(_rain_v))] if _rain_v > 0 else []
                try:
                    _app_eff_v = float(req.placement.application_day or 0.0)
                except (TypeError, ValueError):
                    _app_eff_v = 0.0
            try:
                _pulse_v = float(req.placement.fertigation_pulse_days or 0.0)
            except (TypeError, ValueError):
                _pulse_v = 0.0
            _w_v = _fert_w_mm_v(_evs_v, _app_eff_v, _pulse_v)
            if _w_v <= 0:
                out.append({
                    "field": "placement.fertigation_pulse_days",
                    "message": (
                        "Fertirrigação sem água no período de injeção: nenhuma lâmina irriga "
                        "na janela [dia da aplicação, +pulso] — C₀ = dose ÷ 0 é impossível. "
                        "Ajuste o dia da aplicação, a duração da injeção ou a série de chuva."
                    ),
                })
    except Exception:
        pass
    # v5 — Situação da cultura no início.
    try:
        from hydrus_core.crop import CROP_DATABASE as _CDB_v5
        _ck = str(getattr(req, "crop_key", "") or "")
        _crop_v5 = _CDB_v5.get(_ck) if _ck and _ck != "custom" else None
        _has_crop_v5 = bool(_ck and (_crop_v5 is not None or _ck == "custom"))
        if _has_crop_v5 and _ck != "custom":
            from hydrus_core import crop as _cm_v5
            try:
                _cyc_v5 = _cm_v5._resolve_cycle(_crop_v5)
                _len_v5 = getattr(_cyc_v5, "stage_lengths_days", None)
                _L_v5 = float(sum(float(v) for v in _len_v5)) if (_len_v5 and len(_len_v5) == 4) else 0.0
            except Exception:
                _L_v5 = 0.0
            _mode_v5 = str(getattr(req, "crop_start_mode", "") or "").strip().lower() or None
            if _mode_v5 not in (None, "", "planting", "established", "perennial"):
                out.append({"field": "crop_start_mode", "message": f"Modo de início desconhecido: {getattr(req, 'crop_start_mode')}."})
            _dap_v5 = getattr(req, "crop_age_dap", None)
            if _dap_v5 is not None:
                try:
                    _d = float(_dap_v5)
                except (TypeError, ValueError):
                    out.append({"field": "crop_age_dap", "message": "Idade no início (DAP) deve ser numérica."})
                    _d = None
                if _d is not None:
                    if _d < 0:
                        out.append({"field": "crop_age_dap", "message": f"DAP ({_d:g}) não pode ser negativo."})
                    elif _L_v5 > 0:
                        _ah_v5 = str(getattr(req, "after_harvest", "") or "").strip().lower()
                        _repeat_v5 = (_ah_v5 == "repeat") or ("cana" in _ck)
                        if not _repeat_v5 and _d > _L_v5:
                            out.append({"field": "crop_age_dap", "message": f"DAP ({_d:g}) além da duração do ciclo ({_L_v5:.0f} dias)."})
            _meas_v5 = getattr(req, "measured_root_depth_cm", None)
            if _meas_v5 is not None:
                try:
                    _m = float(_meas_v5)
                except (TypeError, ValueError):
                    out.append({"field": "measured_root_depth_cm", "message": "Raiz medida deve ser numérica."})
                    _m = None
                if _m is not None:
                    try:
                        _prof = float(req.depth_cm)
                    except (TypeError, ValueError):
                        _prof = 0.0
                    if not (_m > 0):
                        out.append({"field": "measured_root_depth_cm", "message": f"Raiz medida ({_m:g} cm) deve ser > 0."})
                    elif _prof > 0 and _m > _prof:
                        out.append({"field": "measured_root_depth_cm", "message": f"Raiz medida ({_m:g} cm) além da profundidade do perfil ({_prof:g} cm)."})
            _sl_v5 = getattr(req, "stage_lengths_days", None)
            if _sl_v5 is not None:
                try:
                    _lst = list(_sl_v5)
                except TypeError:
                    _lst = None
                if _lst is None or len(_lst) != 4:
                    out.append({"field": "stage_lengths_days", "message": "Durações dos estádios: informe 4 valores."})
                else:
                    for _v in _lst:
                        try:
                            _f = float(_v)
                        except (TypeError, ValueError):
                            out.append({"field": "stage_lengths_days", "message": "Durações dos estádios devem ser numéricas."})
                            break
                        if not (_f > 0):
                            out.append({"field": "stage_lengths_days", "message": f"Duração de estádio ({_v}) deve ser > 0."})
                            break
            for _fa, _fl in (("kcb_ini", "Kcb inicial"), ("kcb_mid", "Kcb médio"), ("kcb_end", "Kcb final")):
                _kv = getattr(req, _fa, None)
                if _kv is not None:
                    try:
                        _kf = float(_kv)
                    except (TypeError, ValueError):
                        out.append({"field": _fa, "message": f"{_fl} deve ser numérico."})
                        continue
                    if not (0 <= _kf <= 1.5):
                        out.append({"field": _fa, "message": f"{_fl} ({_kf:g}) fora de [0, 1.5]."})
            _rg_v5 = str(getattr(req, "root_growth_model", "linear") or "linear").strip().lower()
            if _rg_v5 not in ("linear", "logistic"):
                out.append({"field": "root_growth_model", "message": f"Crescimento da raiz desconhecido: {_rg_v5}."})
            _ah2 = str(getattr(req, "after_harvest", "") or "").strip().lower() or None
            if _ah2 not in (None, "", "bare", "repeat"):
                out.append({"field": "after_harvest", "message": f"Após a colheita desconhecido: {_ah2}."})
    except Exception:
        pass
    return out
