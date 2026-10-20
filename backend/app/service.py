"""Camada de serviço: traduz request HTTP -> hydrus-core -> resposta.

Regras de domínio (as mesmas do app legado):
- camada avaliada = raiz da cultura, ou perfil todo sem cultura;
- balanço em 3 vias: retido 0–raiz / abaixo no perfil / fundo (+ absorvido).
"""

import base64
import logging
import math
import os
import tempfile

import matplotlib

matplotlib.use("Agg")

from hydrus_core.crop import CROP_DATABASE
from hydrus_core.hydrus_solver import Hydrus1DSimulator, SimulationConfig
from hydrus_core.soil_physics import SOIL_DATABASE
from hydrus_core.visualizer import plot_nutrient_profile

from .schemas import SimulateRequest, SimulateResponse, SoluteBalance, WaterBalance
from .water_report import (
    seasonal_water_only_report,
    column_water_only_report,
)


def _peak_or_none(value) -> float | None:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) else v


def _is_seasonal(req: SimulateRequest) -> bool:
    """Modo sazonal como no Gradio: série diária (qualquer duração).

    Gradio: is_column = "Lâmina"/"evento único" em water_source; série ou
    upload (qualquer duração) segue o ramo sazonal (janela + relatório anual).
    """
    return bool(req.rain_series)


def _is_fertigation(req: SimulateRequest) -> bool:
    """True quando o posicionamento é fertirrigação."""
    try:
        return str((req.placement.mode if req.placement else None) or "surface").lower() == "fertigation"
    except Exception:
        return False


def _effective_dose(req: SimulateRequest, results, symbol: str, table_dose: float) -> float:
    """Dose efetiva p/ exibição e kg/ha.

    Em fertirrigação a massa realmente injetada é C₀ × água infiltrada
    durante o pulso (o solver ignora a dose da tabela); os % do solver são
    relativos a essa massa aplicada (nutrient_results[sym]["applied_kg_ha"]).
    Nos demais modos, a dose da tabela.
    """
    if _is_fertigation(req):
        try:
            d = (getattr(results, "nutrient_results", {}) or {}).get(symbol) or {}
            v = float(d.get("applied_kg_ha", table_dose))
            if v >= 0:
                return v
        except (TypeError, ValueError):
            pass
    try:
        return float(table_dose)
    except (TypeError, ValueError):
        return 0.0


def _default_print_days(total_days: float, seasonal: bool = False) -> list[float]:
    """Marcos de leitura padrão, iguais aos do Gradio (app_gradio.py).

    - Sazonal longo (>= 180 dias): frações (0.15, 0.35, 0.65, 1.0)
      (em 365 dias = 55, 128, 237, 365, o default da UI do Gradio);
    - Coluna ou sazonal curto: frações (0.25, 0.5, 0.75, 1.0).
    """
    try:
        td = float(total_days)
    except (TypeError, ValueError):
        td = 0.0
    if td <= 0:
        return []
    fracs = (0.15, 0.35, 0.65, 1.0) if (seasonal and td >= 180) else (0.25, 0.5, 0.75, 1.0)
    days = sorted({max(1.0, round(td * f)) for f in fracs})
    return [float(d) for d in days if 0.0 < float(d) <= td + 1e-9]


def _default_obs_depths(depth_cm: float, seasonal: bool) -> list[float] | None:
    """Nós de observação padrão do campo do Gradio ("10, 20, 30, 50").

    O Gradio usa o default "10, 20, 30, 50" em ambos os modos (coluna e
    série diária); aqui filtramos a 0 < d <= prof e ordenamos sem duplicatas.
    O parâmetro ``seasonal`` é mantido por compatibilidade de assinatura.
    """
    try:
        prof = float(depth_cm)
    except (TypeError, ValueError):
        return None
    out = sorted({float(d) for d in (10.0, 20.0, 30.0, 50.0) if 0.0 < float(d) <= prof})
    return out or None


def _effective_obs_depths(req: SimulateRequest, depth_cm: float) -> list[float] | None:
    """Nós de observação efetivos como no Gradio.

    Se o request informa obs_depths_cm não vazio, usa esses valores
    (filtrados a 0 < d <= depth_cm, ordenados, sem duplicatas); senão o
    default do campo do Gradio [10, 20, 30, 50] filtrado pela profundidade.
    """
    try:
        prof = float(depth_cm)
    except (TypeError, ValueError):
        return None
    raw = getattr(req, "obs_depths_cm", None)
    if raw:
        try:
            filt = sorted({float(d) for d in raw if 0.0 < float(d) <= prof})
        except (TypeError, ValueError):
            filt = []
        if filt:
            return filt
    return _default_obs_depths(prof, _is_seasonal(req))


def _storage_mm(results) -> float:
    """Δ armazenamento no perfil (θfinal − θinicial), como no Gradio."""
    try:
        import numpy as _np

        z = _np.asarray(getattr(results, "z", []), dtype=float)
        if z.size < 2:
            return 0.0
        d_z = float(z[1] - z[0])
        th = getattr(results, "theta_profiles", []) or []
        if len(th) < 2:
            return 0.0
        return float(_np.sum(_np.asarray(th[-1], dtype=float) - _np.asarray(th[0], dtype=float)) * d_z) * 10.0
    except Exception:
        return 0.0


def _effective_window(req: SimulateRequest, series_len: int) -> tuple[int, int]:
    """Janela de análise [sw, ew] com o clamp do Gradio (dias do ano, 1-based).

    Fora da série (lâmina), a janela é ignorada (validate_analysis_window).
    """
    try:
        sw = int(float(req.analysis_start_day or 1))
    except (TypeError, ValueError):
        sw = 1
    try:
        ew = int(float(req.analysis_end_day or 365))
    except (TypeError, ValueError):
        ew = 365
    sw = max(1, min(sw, max(series_len, 1)))
    ew = max(sw, min(ew, max(series_len, 1)))
    return sw, ew


def _effective_print_days(req: SimulateRequest, total_days: float, sw: int, ew: int) -> list[float]:
    """Dias de leitura (dias de ensaio) como no Gradio.

    - Série: dias de calendário convertidos (d − sw + 1); ausente = marcos
      por frações da duração (em 365 dias = 55, 128, 237, 365).
    - Lâmina: dias de ensaio diretos; ausente = marcos por frações.
    """
    if req.print_days is not None:
        if req.rain_series:
            conv = sorted({int(round(float(d))) - sw + 1 for d in (req.print_days or [])})
            return [float(d) for d in conv if 1 <= d <= int(float(total_days))]
        return [float(d) for d in (req.print_days or [])]
    return _default_print_days(total_days, _is_seasonal(req))


def _resolve_soil(req: SimulateRequest):
    """Solo da lista ou personalizado (Rosetta + overrides, como o Gradio)."""
    from .soils import resolve_custom_soil

    if req.custom_soil is not None:
        cs = req.custom_soil
        return resolve_custom_soil(
            sand_pct=float(cs.sand_pct),
            clay_pct=float(cs.clay_pct),
            bulk_density=(float(cs.bulk_density) if cs.bulk_density is not None else None),
            overrides={
                "theta_r": cs.theta_r,
                "theta_s": cs.theta_s,
                "alpha": cs.alpha,
                "n": cs.n,
                "ks": cs.ks,
                "bulk_density": cs.bulk_density,
            },
        )
    return SOIL_DATABASE[req.soil_key]


def _build_crop(req: SimulateRequest):
    """Cultura com overrides editáveis, exatamente como o Gradio (app_gradio.py).

    - crop_key no banco: parte dos valores do banco, aplicando overrides
      (crop_name, root_depth_cm, kc, h1..h4) quando informados;
    - crop_key="custom" (ou nome que não casa com o banco): cultura
      personalizada montada dos campos, com os defaults do Gradio
      (raiz 35 cm, kc 1.0, h1..h4 = -15/-30/-450/-12000);
    - stage "Literatura (Feddes/FAO-56)" quando o nome casa com o banco,
      senão "Personalizado" (mesma regra do Gradio).
    """
    from hydrus_core.crop import CROP_DATABASE, CropParameters
    import dataclasses

    key = req.crop_key
    if not key:
        return None
    if key == "custom":
        base = None
    else:
        base = CROP_DATABASE.get(key)
        if base is None:
            return None
    _name = (str(req.crop_name).strip() if req.crop_name else "") or (
        base.name if base else "Cultura Personalizada"
    )
    _db_match = next(
        (c for c in CROP_DATABASE.values() if c.name.strip().lower() == _name.lower()),
        None,
    )
    def _ov(value, fallback):
        return float(value) if value is not None else float(fallback)

    if base is not None:
        root = _ov(req.root_depth_cm, base.root_depth_cm)
        kc = _ov(req.kc, base.kc)
        h1 = _ov(req.h1, base.h1)
        h2 = _ov(req.h2, base.h2)
        h3 = _ov(req.h3, base.h3)
        h4 = _ov(req.h4, base.h4)
        # Preserva o ciclo FAO-56 / Kcb / demanda do banco (dataclasses.replace):
        # sem isso o schedule sazonal e o teto de absorção perderiam a cultura-mãe.
        _kw = dict(name=_name,
             stage=("Literatura (Feddes/FAO-56)" if _db_match else "Personalizado"),
             root_depth_cm=root, kc=kc, h1=h1, h2=h2, h3=h3, h4=h4)
        # Overrides v5 (substituem o banco quando fornecidos).
        try:
            _sl = getattr(req, "stage_lengths_days", None)
            if _sl is not None and len(list(_sl)) == 4:
                _kw["stage_lengths_days"] = tuple(float(v) for v in _sl)
        except Exception:
            pass
        for _a in ("kcb_ini", "kcb_mid", "kcb_end"):
            try:
                _v = getattr(req, _a, None)
                if _v is not None:
                    _kw[_a] = float(_v)
            except (TypeError, ValueError):
                pass
        return dataclasses.replace(base, **_kw)
    else:
        root = _ov(req.root_depth_cm, 35.0)
        kc = _ov(req.kc, 1.0)
        h1 = _ov(req.h1, -15.0)
        h2 = _ov(req.h2, -30.0)
        h3 = _ov(req.h3, -450.0)
        h4 = _ov(req.h4, -12000.0)
    return CropParameters(
        name=_name,
        stage=("Literatura (Feddes/FAO-56)" if _db_match else "Personalizado"),
        root_depth_cm=root,
        kc=kc,
        h1=h1,
        h2=h2,
        h3=h3,
        h4=h4,
    )


def _planting_cal_day(req: SimulateRequest) -> float:
    """Dia do plantio no calendário da série (None = dia da aplicação se > 0, senão dia 1)."""
    if req.planting_day is not None:
        try:
            return float(req.planting_day)
        except (TypeError, ValueError):
            pass
    try:
        _a = float(req.placement.application_day or 0.0)
    except (TypeError, ValueError):
        _a = 0.0
    return _a if _a > 0 else 1.0


_DAP_DEFAULTS = {"milho": 50.0, "soja": 60.0, "hortalicas": 60.0, "cana_de_acucar": 150.0}


def _resolve_crop_situation(req, crop, is_seasonal: bool) -> dict:
    """Defaults v5 da situação inicial (usado pelo service e pelo preview).

    - modo: café => perennial; demais => série: planting, Lâmina: established.
    - DAP default: milho 50, soja 60, hortalicas 60, cana 150; entradas de
      estádio usam o stage_offset_days delas (12/50/15/70).
    - after_harvest default: cana => repeat, demais => bare.
    - planting_day default = dia da aplicação (série) ou 1 (coluna).
    """
    from hydrus_core import crop as _cm
    _key = str(getattr(req, "crop_key", "") or "")
    _cyc = None
    try:
        _cyc = _cm._resolve_cycle(crop) if crop is not None else None
    except Exception:
        _cyc = None
    _lengths = getattr(_cyc, "stage_lengths_days", None) if _cyc is not None else None
    _has_cycle = bool(_lengths and len(_lengths) == 4)
    _is_cafe = (_key == "cafe") or bool(getattr(_cyc, "perennial", False))
    _is_cana = ("cana" in _key) or (getattr(_cyc, "cycle_key", "") == "cana_de_acucar")
    _mode_req = str(getattr(req, "crop_start_mode", None) or "").strip().lower() or None
    if _mode_req not in ("planting", "established", "perennial", None):
        _mode_req = None
    if _mode_req is None:
        if crop is None:
            mode = None
        elif _is_cafe:
            mode = "perennial"
        elif is_seasonal:
            mode = "planting"
        else:
            mode = "established"
    else:
        mode = _mode_req
    # Perennial sem dados no banco: aceita usando kc-0.05 (validação não barra).
    _L = float(sum(float(v) for v in _lengths)) if _has_cycle else 0.0
    _dap_req = getattr(req, "crop_age_dap", None)
    try:
        _dap_req_f = float(_dap_req) if _dap_req is not None else None
    except (TypeError, ValueError):
        _dap_req_f = None
    if mode == "established" and _has_cycle:
        if _dap_req_f is None:
            if _key in _DAP_DEFAULTS:
                dap = float(_DAP_DEFAULTS[_key])
            else:
                try:
                    dap = float(getattr(crop, "stage_offset_days", 0.0) or 0.0) or 0.0
                except (TypeError, ValueError):
                    dap = 0.0
                if not (dap > 0):
                    dap = min(50.0, _L / 2.0) if _L > 0 else 0.0
        else:
            dap = float(_dap_req_f)
    elif mode == "established":
        dap = float(_dap_req_f) if _dap_req_f is not None else 0.0
    else:
        dap = None
    _ah_req = str(getattr(req, "after_harvest", None) or "").strip().lower() or None
    if _ah_req not in ("bare", "repeat", None):
        _ah_req = None
    after_harvest = _ah_req or ("repeat" if _is_cana else "bare")
    _rg = str(getattr(req, "root_growth_model", "linear") or "linear").strip().lower()
    if _rg not in ("linear", "logistic"):
        _rg = "linear"
    try:
        _meas = float(getattr(req, "measured_root_depth_cm", None)) if getattr(req, "measured_root_depth_cm", None) is not None else None
    except (TypeError, ValueError):
        _meas = None
    try:
        _sl = getattr(req, "stage_lengths_days", None)
        _sl_t = tuple(float(v) for v in _sl) if _sl is not None else None
        if _sl_t is not None and len(_sl_t) != 4:
            _sl_t = None
    except (TypeError, ValueError):
        _sl_t = None
    _kcb = []
    for _a in ("kcb_ini", "kcb_mid", "kcb_end"):
        try:
            _v = getattr(req, _a, None)
            _kcb.append(float(_v) if _v is not None else None)
        except (TypeError, ValueError):
            _kcb.append(None)
    _kcb_t = tuple(_kcb) if any(v is not None for v in _kcb) else None
    # planting_rel (0-based): planting => planting_day - dia_inicial; established => -DAP.
    try:
        _plant_cal = float(_planting_cal_day(req))
    except Exception:
        _plant_cal = 1.0
    return {"mode": mode, "dap": dap, "after_harvest": after_harvest,
            "root_growth": _rg, "measured": _meas, "stage_lengths": _sl_t,
            "kcb": _kcb_t, "plant_cal": _plant_cal, "cycle_len": _L,
            "has_cycle": _has_cycle, "is_cafe": _is_cafe, "is_cana": _is_cana}


def _schedule_for_request(req, crop, total_days: float, sw: int):
    """Agenda v5 nos DOIS modos (série e Lâmina); None sem cultura/sem ciclo."""
    if crop is None:
        return None
    from hydrus_core.crop import crop_schedule as _cs
    import math as _mm
    _is_seas = _is_seasonal(req)
    _sit = _resolve_crop_situation(req, crop, _is_seas)
    _mode = _sit["mode"]
    if _mode is None:
        return None
    if not _sit["has_cycle"]:
        # Custom sem ciclo: comportamento atual (Kc cte, sem teto).
        return None
    try:
        _n = int(_mm.ceil(float(total_days))) + 1
    except (TypeError, ValueError):
        _n = int(float(total_days)) + 1
    _n = max(_n, 1)
    if _mode == "established":
        _dap = float(_sit["dap"] or 0.0)
        _rel = -_dap
    elif _mode == "perennial":
        _rel = 0.0
    else:
        try:
            _plant_cal = float(_sit["plant_cal"])
        except (TypeError, ValueError):
            _plant_cal = 1.0
        if _is_seas:
            _rel = _plant_cal - float(sw) + 1.0
        else:
            # Lâmina: planting_day é dia do ensaio (1-based) — relativo 0-based.
            try:
                _pd_req = float(req.planting_day) if req.planting_day is not None else 1.0
            except (TypeError, ValueError):
                _pd_req = 1.0
            _rel = _pd_req - 1.0
    # Kcb override parcial: completa com o banco.
    _kcb_arg = None
    if _sit["kcb"] is not None:
        try:
            from hydrus_core import crop as _cmm
            _cc = _cmm._resolve_cycle(crop)
            _fb = [(_cc.kcb_ini if _cc.kcb_ini is not None else crop.kcb_ini),
                   (_cc.kcb_mid if _cc.kcb_mid is not None else crop.kcb_mid),
                   (_cc.kcb_end if _cc.kcb_end is not None else crop.kcb_end)]
            _kcb_arg = tuple(float(_sit["kcb"][i]) if _sit["kcb"][i] is not None else float(_fb[i]) for i in range(3))
        except Exception:
            _kcb_arg = None
    try:
        sched = _cs(crop, _n, _rel, mode=_mode, after_harvest=_sit["after_harvest"],
                    root_growth=_sit["root_growth"], measured_root_cm=_sit["measured"],
                    stage_lengths=_sit["stage_lengths"], kcb=_kcb_arg)
    except Exception:
        return None
    # Escala Kcb pelo override de kc (req.kc ≠ banco).
    try:
        from hydrus_core.crop import CROP_DATABASE as _CDB
        from hydrus_core import crop as _cmod
        _base = _CDB.get(req.crop_key) if req.crop_key else None
        _kc_base = float(_base.kc) if _base is not None else None
    except (TypeError, ValueError):
        _kc_base = None
    try:
        _kc_req = float(req.kc) if req.kc is not None else None
    except (TypeError, ValueError):
        _kc_req = None
    if (_kc_base is not None and _kc_req is not None and _kc_base > 0
            and abs(_kc_req - _kc_base) > 1e-12):
        try:
            import numpy as _np
            _f = _kc_req / _kc_base
            _kcb_arr = _np.asarray(sched["kcb"], dtype=float) * _f
            sched["kcb"] = _kcb_arr
            try:
                _cyc2 = _cmod._resolve_cycle(crop)
                _h2 = _cyc2.height_m if getattr(_cyc2, "height_m", None) is not None else getattr(crop, "height_m", None)
                _h2 = float(_h2) if _h2 is not None else 1.0
            except (TypeError, ValueError):
                _h2 = 1.0
            _few = _np.empty_like(_kcb_arr); _kmx = _np.empty_like(_kcb_arr); _kex = _np.empty_like(_kcb_arr)
            for _i, _kv in enumerate(_kcb_arr):
                _fw, _km, _ke = _cmod._dual_ke_few(float(_kv), _h2)
                _few[_i], _kmx[_i], _kex[_i] = _fw, _km, _ke
            sched["few"], sched["kc_max"], sched["ke_max"] = _few, _kmx, _kex
        except Exception:
            pass
    sched["_situation"] = _sit
    sched["_plant_rel"] = float(_rel)
    return sched


def _crop_demands(crop) -> dict:
    """Demanda nutricional do ciclo (kg/ha por nutriente), via cultura ou mãe."""
    try:
        from hydrus_core import crop as _crop_mod

        _cyc = _crop_mod._resolve_cycle(crop)
    except Exception:
        _cyc = None
    for _src in (getattr(crop, "uptake_demand_kg_ha", None),
                 getattr(_cyc, "uptake_demand_kg_ha", None) if _cyc is not None else None):
        try:
            if _src:
                return {str(_k): float(_v) for _k, _v in dict(_src).items()}
        except (TypeError, ValueError):
            continue
    return {}


def _crop_citation(req: SimulateRequest, crop) -> str:
    """Citação da cultura p/ laudo/passos (raiz crescente quando há ciclo)."""
    if crop is None:
        return "Sem cultura: apenas evaporação do solo."
    _base = (f"Transpiração via Feddes (kc={float(crop.kc):.2f}) + Kc dual FAO-56 "
             f"(Tp=Kcb·ET0, Ep=Ke·ET0; Allen et al., 1998).")
    try:
        from hydrus_core import crop as _crop_mod

        _cyc = _crop_mod._resolve_cycle(crop)
        _lengths = getattr(_cyc, "stage_lengths_days", None)
        _per = bool(getattr(_cyc, "perennial", False))
    except Exception:
        _cyc, _lengths, _per = None, None, False
    if _per:
        _root_txt = f"raiz fixa em {float(crop.root_depth_cm):.0f} cm (cultura perene)"
    elif _lengths and len(_lengths) == 4:
        try:
            _rmin = crop.root_depth_min_cm if crop.root_depth_min_cm is not None else getattr(_cyc, "root_depth_min_cm", None)
            _rmin = float(_rmin)
        except (TypeError, ValueError):
            _rmin = float(crop.root_depth_cm)
        _root_txt = f"raiz crescente de {_rmin:.0f} a {float(crop.root_depth_cm):.0f} cm no ciclo"
    else:
        _root_txt = f"raiz fixa em {float(crop.root_depth_cm):.0f} cm"
    _cap_txt = (" Absorção limitada pela demanda nutricional do ciclo "
                "(Raij et al. 1997, Boletim 100 IAC; Embrapa; Malavolta 2006; teto pela demanda restante: "
                "extensão agronômica, não existe no HYDRUS-1D).") if _crop_demands(crop) else ""
    return f"{_base} {_root_txt}.{_cap_txt}"


def _cycle_info(req: SimulateRequest, crop) -> dict:
    """Plantio/colheita/estádios/Kcb + Kc dual + teto + situação inicial + HYDRUS-1D (laudo/Excel/passos)."""
    out = {"cycle_txt": "", "kc_dual_txt": "", "uptake_cap_txt": "",
           "planting_day_cal": None, "harvest_day_cal": None,
           "crop_start_txt": "", "hydrus_txt": ""}
    if crop is None:
        return out
    out["kc_dual_txt"] = ("Kc dual FAO-56 (Allen et al., 1998, cap. 7): "
                          "Tp = Kcb·ET0, Ep = Ke·ET0.")
    _dem = _crop_demands(crop)
    if _dem:
        _parts = ", ".join(f"{_k} {float(_v):.0f}" for _k, _v in sorted(_dem.items()))
        _cap_on = bool(getattr(req, "uptake_cap", True))
        _cap_extra = ("absorção limitada pela demanda (teto pela demanda restante; extensão agronômica, "
                      "não existe no HYDRUS-1D)") if _cap_on else "teto de absorção DESLIGADO pelo usuário"
        out["uptake_cap_txt"] = (
            f"Demanda da cultura no ciclo ({_parts} kg/ha de elemento; Raij et al. 1997, "
            f"Boletim 100 IAC; Embrapa; Malavolta 2006); {_cap_extra}.")
    else:
        if getattr(req, "crop_start_mode", None) or getattr(req, "crop_age_dap", None):
            out["crop_start_txt"] = ("Cultura personalizada (sem ciclo FAO-56 no banco): Kcb constante "
                                     "e sem teto de absorção; campos de situação ignorados.")
            return out
    try:
        from hydrus_core import crop as _crop_mod
        _cyc = _crop_mod._resolve_cycle(crop)
    except Exception:
        return out
    _is_seas = _is_seasonal(req)
    try:
        _sit = _resolve_crop_situation(req, crop, _is_seas)
    except Exception:
        _sit = {"mode": None}
    _mode = _sit.get("mode")
    _lengths = getattr(_cyc, "stage_lengths_days", None)
    try:
        _sl_ov = getattr(req, "stage_lengths_days", None)
        if _sl_ov is not None and len(list(_sl_ov)) == 4:
            _lengths = tuple(float(v) for v in _sl_ov)
    except Exception:
        pass
    _has_cyc = bool(_lengths and len(_lengths) == 4)
    # Situação no início (dia 1) via schedule.
    _stage1, _kcb1, _root1, _rootmax, _dap_eff, _harv_txt = "", "", "", "", "", ""
    _hyd_txt = ""
    try:
        _sw0 = 1
        if req.rain_series:
            _sw0, _ew0 = _effective_window(req, len(req.rain_series))
            _td0 = float(len(req.rain_series[_sw0 - 1:_ew0]))
        else:
            _td0 = float(req.total_days or 0.0)
        _sched0 = _schedule_for_request(req, crop, max(_td0, 1.0), _sw0)
        if _sched0 is not None:
            _stage1 = str((_sched0.get("stage") or [""])[0])
            _kcb1 = f"{float(_sched0['kcb'][0]):.2f}"
            _root1 = f"{float(_sched0['root_depth_cm'][0]):.0f}"
            try:
                import numpy as _npx
                _rootmax = f"{float(_npx.max(_npx.asarray(_sched0['root_depth_cm'], dtype=float))):.0f}"
            except Exception:
                _rootmax = f"{float(crop.root_depth_cm):.0f}"
            _he = _sched0.get("hydrus_equiv") or {}
            def _f(_v):
                try:
                    return f"{float(_v):.2f}"
                except (TypeError, ValueError):
                    return "—"
            try:
                _iroot_raw = _he.get("iRootIn")
                _iroot_int = int(_iroot_raw) if _iroot_raw is not None else None
            except (TypeError, ValueError):
                _iroot_int = None
            _lroot_on = bool(_he.get("lRoot"))
            _hcrit_txt = "hCritA = 10000 cm (|h| mínimo na superfície)"
            _rootdist_txt = ("distribuição radicular: triangular (máx. na superfície); "
                             "HYDRUS-1D usa Hoffman & van Genuchten 1983 (eq. 2.17) "
                             "quando a raiz varia — opção futura")
            if not _lroot_on:
                try:
                    _is_per_hyd = (_mode == "perennial") or (bool(getattr(_cyc, "perennial", False)) and not _has_cyc)
                except Exception:
                    _is_per_hyd = False
                if _is_per_hyd:
                    _root_hyd = (f"lRoot=False (zona radicular fixa), "
                                 f"xRMin={_f(_he.get('xRMin'))}, xRMax={_f(_he.get('xRMax'))}")
                else:
                    _root_hyd = (f"lRoot=False (zona radicular fixa), "
                                 f"tRMin={_f(_he.get('tRMin'))}, "
                                 f"xRMin={_f(_he.get('xRMin'))}, xRMax={_f(_he.get('xRMax'))}")
            elif _iroot_int == 1:
                _root_hyd = (f"lRoot=True, iRootIn=1 (tabela RootDepth(t) gerada pelo crescimento linear FAO-56), "
                             f"tRMin={_f(_he.get('tRMin'))}, tRHarv={_f(_he.get('tRHarv'))}, "
                             f"xRMin={_f(_he.get('xRMin'))}, xRMax={_f(_he.get('xRMax'))}")
                try:
                    _tper = _he.get("tRPeriod")
                    if _tper is not None:
                        _root_hyd += f", tRPeriod={_f(_tper)}"
                except Exception:
                    pass
            else:
                _root_hyd = (f"lRoot={bool(_he.get('lRoot'))}, iRootIn={_he.get('iRootIn')}, "
                             f"tRMin={_f(_he.get('tRMin'))}, tRHarv={_f(_he.get('tRHarv'))}, "
                             f"xRMin={_f(_he.get('xRMin'))}, xRMax={_f(_he.get('xRMax'))}, "
                             f"iRFak={_he.get('iRFak')}, tRMed={_f(_he.get('tRMed'))}, "
                             f"xRMed={_f(_he.get('xRMed'))}, tRPeriod={_f(_he.get('tRPeriod'))}, "
                             f"r={_f(_he.get('r'))} 1/d")
            _hyd_txt = (f"{_root_hyd}; {_hcrit_txt}; "
                        f"Feddes h1..h4=({float(crop.h1):.0f},{float(crop.h2):.0f},{float(crop.h3):.0f},{float(crop.h4):.0f}) cm; "
                        f"cRootMax = ∞ (absorção passiva total); teto de absorção pela demanda: "
                        f"extensão agronômica, não existe no HYDRUS-1D; "
                        f"{_rootdist_txt}. "
                        f"Fonte: Šimůnek et al. (2013) HYDRUS-1D v4.17, eq. 2.21-2.22, Tab. 12.4; FAO-56.")
    except Exception:
        pass
    if not _hyd_txt:
        try:
            _is_per_fb = (_mode == "perennial") or bool(getattr(_cyc, "perennial", False))
        except Exception:
            _is_per_fb = False
        if _is_per_fb:
            try:
                _rfix = float(crop.root_depth_cm)
            except (TypeError, ValueError):
                _rfix = 0.0
            _hyd_txt = (f"lRoot=False (zona radicular fixa), "
                        f"xRMin={_rfix:.0f}, xRMax={_rfix:.0f}; "
                        f"hCritA = 10000 cm (|h| mínimo na superfície); "
                        f"Feddes h1..h4=({float(crop.h1):.0f},{float(crop.h2):.0f},{float(crop.h3):.0f},{float(crop.h4):.0f}) cm; "
                        f"cRootMax = ∞ (absorção passiva total); teto de absorção pela demanda: "
                        f"extensão agronômica, não existe no HYDRUS-1D; "
                        f"distribuição radicular: triangular (máx. na superfície); "
                        f"HYDRUS-1D usa Hoffman & van Genuchten 1983 (eq. 2.17) "
                        f"quando a raiz varia — opção futura. "
                        f"Fonte: Šimůnek et al. (2013) HYDRUS-1D v4.17, eq. 2.21-2.22, Tab. 12.4; FAO-56.")
    if _mode == "perennial" or (bool(getattr(_cyc, "perennial", False)) and not _has_cyc):
        out["cycle_txt"] = (f"Cultura perene ({crop.name}): sem estádios — Kcb constante "
                            f"e absorção distribuída ao longo do ano.")
        _per_stage = _stage1 or "perene"
        if _kcb1:
            _per_kcb = _kcb1
        else:
            try:
                _km0 = getattr(crop, "kcb_mid", None)
                if _km0 is None:
                    _km0 = getattr(_cyc, "kcb_mid", None)
                if getattr(req, "kcb_mid", None) is not None:
                    _km0 = float(req.kcb_mid)
                if _km0 is None:
                    _km0 = max(0.15, float(crop.kc) - 0.05)
                _per_kcb = f"{float(_km0):.2f}"
            except (TypeError, ValueError):
                _per_kcb = "—"
        if _root1:
            _per_root = _root1
        else:
            try:
                _m0 = (_sit or {}).get("measured") if isinstance(_sit, dict) else None
                _per_root = f"{float(_m0 if _m0 is not None else float(crop.root_depth_cm)):.0f}"
            except (TypeError, ValueError):
                _per_root = "—"
        out["crop_start_txt"] = (f"modo perene adulta; estádio no dia 1 {_per_stage} (Kcb {_per_kcb}); "
                                 f"raiz no dia 1 {_per_root} cm (fixa).")
        out["hydrus_txt"] = _hyd_txt if _hyd_txt else ""
        return out
    if _has_cyc:
        _L = float(sum(float(v) for v in _lengths))
        _plant = _planting_cal_day(req)
        out["planting_day_cal"] = _plant
        _harv = _plant + _L - 1
        out["harvest_day_cal"] = _harv
        _ki = _cyc.kcb_ini if _cyc.kcb_ini is not None else getattr(crop, "kcb_ini", None)
        _km = _cyc.kcb_mid if _cyc.kcb_mid is not None else getattr(crop, "kcb_mid", None)
        _ke = _cyc.kcb_end if _cyc.kcb_end is not None else getattr(crop, "kcb_end", None)
        try:
            if getattr(req, "kcb_ini", None) is not None: _ki = float(req.kcb_ini)
            if getattr(req, "kcb_mid", None) is not None: _km = float(req.kcb_mid)
            if getattr(req, "kcb_end", None) is not None: _ke = float(req.kcb_end)
            _kcb_txt = f"Kcb {float(_ki):.2f}/{float(_km):.2f}/{float(_ke):.2f}"
        except (TypeError, ValueError):
            _kcb_txt = "Kcb por estádio"
        out["cycle_txt"] = (
            f"Ciclo FAO-56 (Allen et al., 1998): plantio dia {_plant:.0f}, colheita dia {_harv:.0f} "
            f"({_L:.0f} dias; estádios ini/des/med/fim {float(_lengths[0]):.0f}/{float(_lengths[1]):.0f}/"
            f"{float(_lengths[2]):.0f}/{float(_lengths[3]):.0f} dias; {_kcb_txt}).")
        # Bloco v5.
        try:
            _cropmax_s = f"{float(crop.root_depth_cm):.0f}"
        except (TypeError, ValueError):
            _cropmax_s = _rootmax or "—"
        _permax_s = _rootmax or _cropmax_s
        _log_note = ""
        try:
            if str((_sit or {}).get("root_growth")) == "logistic" and _has_cyc:
                _Llog = float(sum(float(v) for v in _lengths))
                _Lm = float(crop.root_depth_cm)
                _rmin_raw = (getattr(crop, "root_depth_min_cm", None)
                             if getattr(crop, "root_depth_min_cm", None) is not None
                             else getattr(_cyc, "root_depth_min_cm", None))
                try:
                    _L0 = float(_rmin_raw) if _rmin_raw is not None else float(_Lm)
                except (TypeError, ValueError):
                    _L0 = float(_Lm)
                _L0 = min(float(_L0), float(_Lm))
                _rlog = None
                try:
                    from hydrus_core import crop as _cm_log
                    _meas0 = (_sit or {}).get("measured")
                    if _meas0 is not None and _mode == "established":
                        try:
                            _tau0 = float((_sit or {}).get("dap") or 0.0)
                        except (TypeError, ValueError):
                            _tau0 = 0.0
                        _rlog = _cm_log._r_logistic_iRFak0(float(_L0), float(_Lm), float(_tau0), float(_meas0))
                    if _rlog is None and float(_Lm) > float(_L0) and _Llog > 0:
                        _rlog = _cm_log._r_logistic_iRFak1(float(_L0), float(_Lm), float(_Llog))
                    if _rlog is not None and float(_Lm) > float(_L0):
                        _harv = _cm_log._verhulst_root(float(_Llog), float(_L0), float(_Lm), float(_rlog))
                        _log_note = (f" Nota: no HYDRUS-1D a raiz logística só atinge xRMax em tempo infinito"
                                     f" (eq. 2.22); com 50% no meio do ciclo ela chega a ~{_harv:.0f} cm na colheita.")
                except Exception:
                    pass
        except Exception:
            _log_note = ""
        if _mode == "established":
            _dap = _sit.get("dap")
            try:
                _dap_s = f"{float(_dap):.0f}"
            except (TypeError, ValueError):
                _dap_s = "—"
            _rg_lbl = "Logístico Verhulst-Pearl (HYDRUS-1D)" if str(_sit.get("root_growth")) == "logistic" else "Linear (FAO-56)"
            _ah_lbl = "repetir o ciclo" if str(_sit.get("after_harvest")) == "repeat" else "solo nu"
            out["crop_start_txt"] = (f"estabelecida com {_dap_s} DAP; estádio no dia 1 {_stage1 or '—'} "
                                     f"(Kcb {_kcb1 or '—'}); raiz no dia 1 {_root1 or '—'} cm "
                                     f"(máx. no período {_permax_s} cm; máx. da cultura {_cropmax_s} cm); "
                                     f"crescimento {_rg_lbl}; após a colheita: {_ah_lbl}.{_log_note}")
        elif _mode == "planting":
            try:
                _pd_s = f"{float(_sit.get('plant_cal')):.0f}"
            except (TypeError, ValueError):
                _pd_s = "—"
            _rg_lbl = "Logístico Verhulst-Pearl (HYDRUS-1D)" if str(_sit.get("root_growth")) == "logistic" else "Linear (FAO-56)"
            _ah_lbl = "repetir o ciclo" if str(_sit.get("after_harvest")) == "repeat" else "solo nu"
            out["crop_start_txt"] = (f"plantio durante a simulação (dia {_pd_s}; solo nu antes); "
                                     f"estádio no dia 1 {_stage1 or '—'} (Kcb {_kcb1 or '—'}); raiz no dia 1 {_root1 or '—'} cm "
                                     f"(máx. no período {_permax_s} cm; máx. da cultura {_cropmax_s} cm); crescimento {_rg_lbl}; "
                                     f"após a colheita: {_ah_lbl}.{_log_note}")
        elif _mode == "perennial":
            _per_stage2 = _stage1 or "perene"
            out["crop_start_txt"] = (f"perene adulta; estádio no dia 1 {_per_stage2} (Kcb {_kcb1 or '—'}); "
                                     f"raiz no dia 1 {_root1 or '—'} cm (fixa).")
        if _hyd_txt:
            out["hydrus_txt"] = _hyd_txt
    else:
        out["cycle_txt"] = ("Cultura personalizada (sem ciclo FAO-56 no banco): "
                            "Kcb constante e sem teto de absorção.")
        if _mode:
            out["crop_start_txt"] = ("Cultura personalizada (sem ciclo FAO-56 no banco): Kcb constante "
                                     "e sem teto de absorção; campos de situação ignorados.")
    return out


def _seasonal_schedule(req: SimulateRequest, crop, total_days: float, sw: int):
    """Compat: agenda v5 (série). Mantida p/ chamadas antigas; usa _schedule_for_request."""
    try:
        return _schedule_for_request(req, crop, total_days, sw)
    except Exception:
        return None


def _fertigation_water_mm(water_events, app_day_eff: float, pulse_eff: float) -> float:
    """Lâmina [mm] dos eventos de água na janela [app, app+pulso].

    Pulso 0 = até o fim do ensaio; eventos parcialmente dentro da janela são
    prorrateados (mesma convenção temporal do Concentration Flux BC do solver:
    aplicação no fim do dia app, pulso contado a partir daí).
    """
    try:
        _a = float(app_day_eff)
    except (TypeError, ValueError):
        _a = 0.0
    try:
        _p = float(pulse_eff)
    except (TypeError, ValueError):
        _p = 0.0
    _end = (_a + _p) if _p > 0 else float("inf")
    _w = 0.0
    for _ev in (water_events or []):
        try:
            _s, _d, _m = float(_ev[0]), float(_ev[1]), float(_ev[2])
        except (TypeError, ValueError, IndexError):
            continue
        if _d <= 0 or _m <= 0:
            continue
        _ov = max(0.0, min(_s + _d, _end) - max(_s, _a))
        if _ov > 0:
            _w += _ov * (_m / _d)
    return float(_w)


def _run_core(req: SimulateRequest):
    """Executa o solver uma vez; retorna (results, soil, crop, root_depth, total_rain, total_days)."""
    soil = _resolve_soil(req)
    crop = _build_crop(req)
    root_depth = float(crop.root_depth_cm) if crop else float(req.depth_cm)
    water_only = bool(req.water_only)

    _pmode = (req.placement.mode or "surface")
    _ztop, _zbot = float(req.placement.z_top_cm), float(req.placement.z_bottom_cm)
    if _pmode == "furrow":
        _ztop, _zbot = 5.0, 10.0
    elif _pmode == "fertigation":
        _ztop, _zbot = 0.0, 0.0
    # Fertigation: C0 é calculado por nutriente (dose ÷ lâmina no período de
    # injeção) após a montagem dos eventos de água; o campo
    # fertigation_c0_mg_l do request é ignorado (compat). Pulse só vale aqui;
    # nos demais posicionamentos o solver recebe 0.0 e 0.0 (sem injeção).
    _is_fert = str(_pmode or "").lower() == "fertigation"
    try:
        _pulse_req = float(req.placement.fertigation_pulse_days)
    except (TypeError, ValueError):
        _pulse_req = 0.0
    _pulse_eff = float(_pulse_req) if _is_fert else 0.0
    nutrients = [
        {
            "symbol": s.symbol,
            "name": s.name,
            "dose_kg_ha": float(s.dose_kg_ha),
            "kd": float(s.kd),
            "initial_residual_mg_dm3": float(s.initial_residual_mg_dm3),
            "dispersivity_cm": float(s.dispersivity_cm),
            "release_type": (s.release_type or "immediate"),
            "release_days": float(s.release_days or 60.0),
            "placement_mode": _pmode,
            "z_app_top_cm": _ztop,
            "z_app_bottom_cm": _zbot,
            "fertigation_c0_mg_l": 0.0,
            "fertigation_pulse_days": _pulse_eff,
        }
        for s in (req.solutes or [])
    ]
    # T5: modo "Somente água": nenhum soluto é transportado (só Richards + ET),
    # como o Gradio (water_only no sim.run). Escalar de transporte com fallback
    # neutro (exigido numérico pelo solver mesmo sem solutos).
    _kd_scalar = float(nutrients[0]["kd"]) if nutrients else 0.0
    _disp_scalar = (
        float(nutrients[0]["dispersivity_cm"]) if nutrients else float(req.depth_cm) / 10.0
    )
    if req.rain_series:
        full = [max(0.0, float(v or 0.0)) for v in req.rain_series]
        sw, ew = _effective_window(req, len(full))
        series = full[sw - 1:ew]
        if req.et0_series:
            full_et0 = [max(0.0, float(v or 0.0)) for v in req.et0_series]
            et0_eff: object = full_et0[sw - 1:ew]
        else:
            et0_eff = float(req.et0_mm_day)
        try:
            _app_raw = float(req.placement.application_day or 0.0)
        except (TypeError, ValueError):
            _app_raw = 0.0
        app_day_eff = (_app_raw - sw + 1) if _app_raw else 0.0
        total_days = float(len(series))
        water_events = [(float(d), 1.0, float(v)) for d, v in enumerate(series) if v > 0.0]
        total_rain = float(sum(series))
    else:
        sw, ew = 1, int(float(req.total_days))
        et0_eff = ([max(0.0, float(v or 0.0)) for v in req.et0_series] if req.et0_series else float(req.et0_mm_day))
        app_day_eff = float(req.placement.application_day or 0.0)
        total_days = float(req.total_days)
        # Paridade Gradio (run_wizard_simulation, ramo is_column): UM único
        # evento no início (0.5, 0.3, lâmina), não espalhado por dia.
        try:
            _rain = float(req.rain_mm)
        except (TypeError, ValueError):
            _rain = 0.0
        water_events = [(0.5, 0.3, float(_rain))] if _rain > 0 else []
        total_rain = float(req.rain_mm)

    # C0 por nutriente a partir da dose: C0_i [mg/L] = dose_i[kg/ha]×100 / W_pulso[mm].
    # W=0 é barrado na validação (422); aqui fallback defensivo (sem injeção).
    if _is_fert:
        _W = _fertigation_water_mm(water_events, app_day_eff, _pulse_eff)
        for _n in nutrients:
            try:
                _nd = float(_n.get("dose_kg_ha", 0.0) or 0.0)
            except (TypeError, ValueError):
                _nd = 0.0
            _n["fertigation_c0_mg_l"] = float(_nd * 100.0 / _W) if _W > 0 else 0.0

    # v5: agenda do ciclo nos DOIS modos (série e Lâmina) quando há ciclo;
    # sem ciclo (custom) o solver usa Kc dual constante + sem teto (compat).
    _sched = _schedule_for_request(req, crop, total_days, sw)

    cfg = SimulationConfig(
        depth_cm=float(req.depth_cm),
        dz=1.0,
        total_days=total_days,
        target_depth_cm=root_depth,
    )
    sim = Hydrus1DSimulator(soil=soil, crop=crop, config=cfg)
    # Defaults iguais ao Gradio: dias de leitura por frações da duração e
    # nós de observação default do campo do Gradio [10, 20, 30, 50].
    _print_days_eff = _effective_print_days(req, total_days, sw, ew)
    _obs_depths = _effective_obs_depths(req, float(req.depth_cm))
    # Umidade inicial: no modo série, % do intervalo θr→CC informada em
    # seasonal_initial_moisture_pct (default 100% = capacidade de campo,
    # prática usual sem medição — Šimůnek et al. 2008); na Lâmina vale o campo atual.
    _seasonal = _is_seasonal(req)
    try:
        _init_moist_eff = float(req.seasonal_initial_moisture_pct) if _seasonal else float(req.initial_moisture_pct)
    except (TypeError, ValueError):
        _init_moist_eff = 100.0 if _seasonal else 80.0
    # ET avançada (Gradio adv_et_toggle, só no modo Lâmina): overrides manuais
    # evap_mm_day ("0 = derivar de ET0") / transp_mm_day ("0 = ET0·Kc").
    # No modo sazonal o Gradio ignora os campos (evap_cm_day=None); aqui igual.
    try:
        _e_override = float(req.evap_mm_day or 0.0)
    except (TypeError, ValueError):
        _e_override = 0.0
    try:
        _t_override = float(req.transp_mm_day or 0.0)
    except (TypeError, ValueError):
        _t_override = 0.0
    _evap_arg = (_e_override / 10.0) if (_e_override > 0 and not _is_seasonal(req)) else None
    _transp_arg = (_t_override if (_t_override > 0 and not _is_seasonal(req)) else None)
    results = sim.run(
        initial_moisture_pct=float(_init_moist_eff),
        fertilizer_dose_kg_ha=sum(n["dose_kg_ha"] for n in nutrients),
        water_events=water_events,
        et0_mm_day=et0_eff,
        kd=_kd_scalar,
        dispersivity_cm=_disp_scalar,
        nutrients=nutrients,
        application_day=float(app_day_eff),
        obs_depths_cm=(_obs_depths if _obs_depths else None),
        print_days=(_print_days_eff if _print_days_eff else None),
        water_only=water_only,
        evap_cm_day=_evap_arg,
        transpiration_mm_day=_transp_arg,
        crop_schedule=_sched,
        uptake_cap=bool(getattr(req, "uptake_cap", True)),
    )
    return results, soil, crop, root_depth, total_rain, total_days


def _balances(req: SimulateRequest, results) -> list[SoluteBalance]:
    def _f(_d: dict, _key: str, _fb: float = 0.0) -> float:
        try:
            return float((_d or {}).get(_key, _fb))
        except (TypeError, ValueError):
            return float(_fb)

    out: list[SoluteBalance] = []
    is_fert = _is_fertigation(req)
    for s in (req.solutes or []):
        d = (results.nutrient_results.get(s.symbol) or {})
        leach = float(d.get("leaching_ratio_pct", 0.0) or 0.0)
        bottom = float(d.get("leached_bottom_pct", 0.0) or 0.0)
        try:
            table_dose = float(s.dose_kg_ha)
        except (TypeError, ValueError):
            table_dose = 0.0
        try:
            cap = float(d.get("capsule_pct", 0.0) or 0.0)
        except (TypeError, ValueError):
            cap = 0.0
        _bottom_kg = _f(d, "leached_bottom_kg_ha", table_dose * bottom / 100.0)
        _leach_kg = _f(d, "leached_kg_ha", table_dose * leach / 100.0)
        _cap_kg = _f(d, "capsule_kg_ha", table_dose * cap / 100.0)
        _up_pct = _f(d, "uptaken_pct")
        try:
            _cap_c0 = d.get("fertigation_c0_mg_l", None)
            _cap_c0 = float(_cap_c0) if _cap_c0 is not None else None
        except (TypeError, ValueError):
            _cap_c0 = None
        try:
            _up_cap = d.get("uptake_cap_kg_ha", None)
            _up_cap = float(_up_cap) if _up_cap is not None else None
        except (TypeError, ValueError):
            _up_cap = None
        out.append(
            SoluteBalance(
                symbol=s.symbol,
                name=s.name,
                dose_kg_ha=_effective_dose(req, results, s.symbol, table_dose),
                retained_root_pct=float(d.get("retained_root_pct", 0.0) or 0.0),
                below_profile_pct=max(0.0, leach - bottom),
                bottom_pct=bottom,
                uptaken_pct=_up_pct,
                peak_depth_cm=_peak_or_none(d.get("peak_depth_cm")),
                dose_input_kg_ha=table_dose,
                is_fertigation=is_fert,
                capsule_pct=cap,
                input_kg_ha=_f(d, "input_kg_ha", table_dose),
                residual_kg_ha=_f(d, "residual_kg_ha"),
                retained_kg_ha=_f(d, "retained_kg_ha", table_dose * float(d.get("retained_root_pct", 0.0) or 0.0) / 100.0),
                below_kg_ha=max(0.0, _leach_kg - _bottom_kg),
                bottom_kg_ha=_bottom_kg,
                uptaken_kg_ha=_f(d, "uptaken_kg_ha", table_dose * _up_pct / 100.0),
                capsule_kg_ha=_cap_kg,
                uptake_cap_kg_ha=_up_cap,
                uptake_capped=bool(d.get("uptake_capped", False)),
                fertigation_c0_mg_l=(_cap_c0 if is_fert else None),
            )
        )
    return out


def _common_xmax(results) -> float | None:
    """Escala X comum: maior pico entre todos os solutos (proporção comparável, como no Gradio)."""
    try:
        import numpy as _np

        gx = 0.0
        for _d in (getattr(results, "nutrient_results", {}) or {}).values():
            try:
                gx = max(gx, float(_np.max(_np.asarray(_d.get("final_profile", [0.0]), dtype=float))))
            except Exception:
                continue
        return gx if gx > 0 else None
    except Exception:
        return None


def _plot_one_b64(results, soil, crop, root_depth: float, total_rain: float, dose_total: float,
                  symbol: str, name: str, release_type: str, release_days: float,
                  out_path: str, x_max: float | None = None) -> str:
    """Um gráfico de perfil por soluto, como a galeria por-soluto do Gradio."""
    plot_nutrient_profile(
        results=results,
        soil=soil,
        crop=crop,
        rain_mm=float(total_rain),
        fertilizer_kg_ha=float(dose_total),
        nutrient_symbol=symbol,
        nutrient_name=name,
        output_path=out_path,
        target_depth_cm=root_depth,
        solute_filter=symbol,
        include_moisture=False,
        banner=True,
        x_max=x_max,
        release_type=(release_type or "immediate"),
        release_days=float(release_days or 60.0),
    )
    with open(out_path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def _plots_b64(req: SimulateRequest, results, soil, crop, root_depth: float,
               total_rain: float, out_dir: str) -> dict[str, str]:
    """Gera um PNG de perfil por soluto (símbolo -> base64)."""
    dose_total = sum(float(s.dose_kg_ha) for s in req.solutes)
    x_max = _common_xmax(results)
    out: dict[str, str] = {}
    for s in req.solutes:
        out[s.symbol] = _plot_one_b64(
            results, soil, crop, root_depth, total_rain, dose_total,
            s.symbol, s.name, (s.release_type or "immediate"),
            float(s.release_days or 60.0),
            os.path.join(out_dir, f"perfil_{s.symbol}.png"),
            x_max,
        )
    return out


def _water_balance(req: SimulateRequest, results, total_rain: float, total_days: float) -> WaterBalance:
    """Balanço hídrico do período (lâmina, drenagem, Δ armazenamento,
    escoamento e ET), com os rótulos dinâmicos do Gradio."""
    is_seasonal = _is_seasonal(req)
    if is_seasonal:
        try:
            full_year = float(total_days) >= 360
        except (TypeError, ValueError):
            full_year = False
        applied_label = "Chuva Anual Total" if full_year else "Chuva no Período"
        drainage_label = "Drenagem Anual" if full_year else "Drenagem no Período"
    else:
        applied_label = "Lâmina Aplicada"
        drainage_label = "Drenagem no Fundo"
    try:
        evap_mm = float(getattr(results, "evap_cum_cm", 0.0) or 0.0) * 10.0
    except (TypeError, ValueError):
        evap_mm = None
    try:
        transp_mm = float(getattr(results, "transp_cum_cm", 0.0) or 0.0) * 10.0
    except (TypeError, ValueError):
        transp_mm = None
    return WaterBalance(
        applied_mm=float(total_rain),
        drainage_mm=float(getattr(results, "q_bottom_cum_cm", 0.0) or 0.0) * 10.0,
        storage_mm=float(_storage_mm(results)),
        runoff_mm=float(getattr(results, "runoff_cum_cm", 0.0) or 0.0) * 10.0,
        evap_mm=evap_mm,
        transp_mm=transp_mm,
        applied_label=applied_label,
        drainage_label=drainage_label,
    )


def _water_plot_b64(results, soil, crop, root_depth: float, out_path: str) -> str:
    """Gráfico do perfil de umidade θ(z), como o modo só-água do Gradio."""
    from hydrus_core.visualizer import plot_water_profile

    plot_water_profile(
        results=results,
        output_path=out_path,
        soil=soil,
        root_depth_cm=(float(crop.root_depth_cm) if crop else None),
        crop=crop,
    )
    with open(out_path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def _nutrients_list(req: SimulateRequest) -> list[dict]:
    return [{"symbol": s.symbol, "name": s.name} for s in (req.solutes or [])]


def _release_info(req: SimulateRequest) -> tuple[str, float]:
    first = (req.solutes or [None])[0]
    rel_type = ((first.release_type if first is not None else None) or "immediate")
    try:
        rel_days = float((first.release_days if first is not None else None) or 60.0)
    except (TypeError, ValueError):
        rel_days = 60.0
    return rel_type, rel_days


def build_screen_images(req: SimulateRequest, results, soil, crop, root_depth: float,
                        total_rain: float, out_dir: str) -> dict:
    """Gera as imagens estáticas da tela de Resultados (iguais às do Gradio).

    Grava os PNGs em ``<out_dir>/tela`` com nomes fixos (``perfil.png``,
    ``btc.png``, ``evolucao.png``, ``galeria_<SIMBOLO_SEGURO>.png``) usando
    as mesmas chamadas do ``run_wizard_simulation`` do Gradio (caminho
    sazonal e coluna). Cada gráfico roda num try/except isolado (falha de
    um não derruba os outros). Retorna ``{"perfil": "perfil" | None, "btc":
    ..., "evolucao": ..., "galeria": [{"symbol", "name", "key"}]}``.
    """
    import logging as _logging

    _log = _logging.getLogger(__name__)
    try:
        from .graphs import _safe_sym
    except Exception:  # fallback sem import circular
        import re as _re

        def _safe_sym(s: str) -> str:
            return _re.sub(r"[^A-Za-z0-9_-]", "_", str(s))

    tela_dir = os.path.join(out_dir, "tela")
    try:
        os.makedirs(tela_dir, exist_ok=True)
    except OSError as exc:
        _log.warning("screen: não foi possível criar diretório tela: %s", exc)
        return {"perfil": None, "btc": None, "evolucao": None, "galeria": []}

    water_only = bool(getattr(req, "water_only", False))
    solutes = list(getattr(req, "solutes", None) or [])
    try:
        dose_total = float(sum(float(s.dose_kg_ha) for s in solutes))
    except (TypeError, ValueError):
        dose_total = 0.0
    rel_type, rel_days = _release_info(req)
    first_sym = solutes[0].symbol if solutes else None
    first_name = solutes[0].name if solutes else "Água"
    try:
        x_max = _common_xmax(results)
    except Exception:
        x_max = None

    perfil_key: str | None = None
    btc_key: str | None = None
    evolucao_key: str | None = None
    galeria: list[dict] = []

    # 1) Perfil principal — seção "Distribuição em Profundidade C(z)".
    try:
        p = os.path.join(tela_dir, "perfil.png")
        if water_only:
            from hydrus_core.visualizer import plot_water_profile

            plot_water_profile(
                results=results,
                output_path=p,
                soil=soil,
                root_depth_cm=(float(crop.root_depth_cm) if crop else None),
                crop=crop,
            )
        else:
            plot_nutrient_profile(
                results=results,
                soil=soil,
                crop=crop,
                rain_mm=float(total_rain),
                fertilizer_kg_ha=float(dose_total),
                nutrient_symbol=first_sym,
                nutrient_name=first_name,
                output_path=p,
                release_type=rel_type,
                release_days=float(rel_days),
                target_depth_cm=float(root_depth),
            )
        if os.path.isfile(p):
            perfil_key = "perfil"
    except Exception as exc:
        _log.warning("screen: falha ao gerar perfil.png: %s", exc)

    # 2) Séries temporais — seção "Séries Temporais nos Nós de Observação".
    try:
        from hydrus_core.visualizer import plot_breakthrough_curves

        p = os.path.join(tela_dir, "btc.png")
        plot_breakthrough_curves(
            results=results,
            nutrient_symbol=(first_sym if not water_only else None),
            output_path=p,
            crop=crop,
        )
        if os.path.isfile(p):
            btc_key = "btc"
    except Exception as exc:
        _log.warning("screen: falha ao gerar btc.png: %s", exc)

    # 3) Evolução temporal — seção "Evolução Temporal do Perfil".
    try:
        if getattr(results, "print_profiles", None):
            from hydrus_core.visualizer import plot_profiles_at_days

            p = os.path.join(tela_dir, "evolucao.png")
            plot_profiles_at_days(
                results=results,
                soil=soil,
                nutrient_symbol=(first_sym if not water_only else None),
                nutrient_name=(first_name if not water_only else "Água"),
                output_path=p,
            )
            if os.path.isfile(p):
                evolucao_key = "evolucao"
    except Exception as exc:
        _log.warning("screen: falha ao gerar evolucao.png: %s", exc)

    # 4) Galeria "Por Soluto" — só quando há mais de 1 soluto.
    try:
        if not water_only and len(solutes) > 1:
            for s in solutes:
                try:
                    sym = str(s.symbol)
                    name = str(s.name)
                    key = f"galeria_{_safe_sym(sym)}"
                    p = os.path.join(tela_dir, f"{key}.png")
                    plot_nutrient_profile(
                        results=results,
                        soil=soil,
                        crop=crop,
                        rain_mm=float(total_rain),
                        fertilizer_kg_ha=float(dose_total),
                        nutrient_symbol=sym,
                        nutrient_name=name,
                        output_path=p,
                        release_type=rel_type,
                        release_days=float(rel_days),
                        target_depth_cm=float(root_depth),
                        solute_filter=sym,
                        include_moisture=False,
                        banner=False,
                        x_max=x_max,
                    )
                    if os.path.isfile(p):
                        galeria.append({"symbol": sym, "name": name, "key": key})
                except Exception as exc:
                    _log.warning("screen: falha na galeria %s: %s", s, exc)
    except Exception as exc:
        _log.warning("screen: falha ao gerar galeria por-soluto: %s", exc)

    try:
        import matplotlib.pyplot as _plt

        _plt.close("all")
    except Exception:
        pass
    return {"perfil": perfil_key, "btc": btc_key, "evolucao": evolucao_key, "galeria": galeria}


def build_extra_plots(req: SimulateRequest, results, soil, crop, root_depth: float,
                       total_rain: float, out_dir: str) -> tuple[list[dict], list[dict]]:
    """Gráficos extras (1 PNG por painel) como o Gradio; retorna (encoded, files)."""
    from .graphs import build_graph_files, encode_files

    dose_total = sum(float(s.dose_kg_ha) for s in (req.solutes or []))
    rel_type, rel_days = _release_info(req)
    graphs_dir = os.path.join(out_dir, "graphs")
    files = build_graph_files(
        results, soil, crop, float(total_rain), float(dose_total),
        rel_type, float(rel_days), float(root_depth), graphs_dir,
        _nutrients_list(req), water_only=bool(req.water_only),
    )
    return encode_files(files), files


def build_steps_markdown(req: SimulateRequest, results, soil, crop, root_depth: float,
                          total_rain: float, total_days: float) -> str:
    """Passo a passo via hydrus_core.explanatory_pipeline, como o Gradio monta."""
    from hydrus_core.explanatory_pipeline import generate_simulation_step_by_step

    params = _sim_params(req, results, soil, crop, root_depth, total_rain, total_days)
    step_md, _step_html = generate_simulation_step_by_step(params)
    return step_md


def run_simulation(req: SimulateRequest, with_plot: bool = True) -> SimulateResponse:
    results, soil, crop, root_depth, total_rain, total_days = _run_core(req)
    water_only = bool(req.water_only)
    plot_b64: str | None = None
    plots_b64: dict[str, str] | None = None
    extra: list[dict] = []
    if with_plot:
        with tempfile.TemporaryDirectory() as tmp:
            if water_only:
                # Galeria vazia no modo só-água (Gradio: _solute_gallery_out = []).
                plots_b64 = {}
                plot_b64 = _water_plot_b64(
                    results, soil, crop, root_depth, os.path.join(tmp, "perfil_agua.png")
                )
            else:
                plots_b64 = _plots_b64(req, results, soil, crop, root_depth, total_rain, tmp)
                plot_b64 = plots_b64.get(req.solutes[0].symbol)
            try:
                extra, _files = build_extra_plots(req, results, soil, crop, root_depth, total_rain, tmp)
            except Exception:
                extra = []
    return SimulateResponse(
        drainage_mm=float(results.q_bottom_cum_cm) * 10.0,
        solutes=_balances(req, results),
        plot_png_base64=plot_b64,
        plots_png_base64=plots_b64,
        extra_plots=extra,
        profiles=_profiles_payload(results),
        water_only=water_only,
        water_balance=_water_balance(req, results, total_rain, total_days),
    )


def expected_extra_plots(req: SimulateRequest, results) -> list[dict]:
    """Descritores {key,title} dos gráficos extras sem renderizar (resposta imediata)."""
    from .graphs import expected_descriptors

    return expected_descriptors(results, _nutrients_list(req), water_only=bool(req.water_only))


def _extra_plots_with_urls(descriptors: list[dict], job_id: str) -> list[dict]:
    out: list[dict] = []
    for d in descriptors:
        try:
            key = str(d.get("key"))
            title = str(d.get("title"))
        except Exception:
            continue
        if not key:
            continue
        out.append({"key": key, "title": title, "url": f"/jobs/{job_id}/plots/{key}.png"})
    return out


def ensure_extra_files(job_dir: str, lazy_ctx: dict) -> list[dict]:
    """Gera PNGs extras + graphs.zip sob demanda (sem re-solver); idempotente.

    Retorna a lista de files [{key,title,path}]. Se o zip já existe, não
    reconstrói. Chamar com o lock do job (thread-safe).
    """
    from .graphs import build_graph_files, write_zip

    zip_path = os.path.join(job_dir, "graphs.zip")
    graphs_dir = os.path.join(job_dir, "graphs")
    if os.path.exists(zip_path):
        # Lista a partir do esperado + arquivos existentes (títulos do esperado).
        try:
            req = lazy_ctx["req"]
            results = lazy_ctx["results"]
            expected = expected_extra_plots(req, results)
        except Exception:
            expected = []
        files: list[dict] = []
        for d in expected:
            key = str(d.get("key"))
            title = str(d.get("title"))
            # Localiza o PNG correspondente no graphs_dir ou job_dir.
            found = None
            try:
                for base in (graphs_dir, job_dir):
                    if not os.path.isdir(base):
                        continue
                    for fn in os.listdir(base):
                        if not fn.lower().endswith(".png"):
                            continue
                        # Nome do arquivo contém a chave ou vice-versa (best-effort).
                        if key.replace("_", "") in fn.replace("_", "").replace("-", "") or fn[:-4].endswith(key[-12:]):
                            found = os.path.join(base, fn)
                            break
                    if found:
                        break
            except OSError:
                found = None
            # Fallback: procura qualquer PNG cujo basename case com o padrão
            # de build_graph_files (01_*, perfil_*, avanco_*, evolucao_*).
            if found is not None and os.path.isfile(found):
                files.append({"key": key, "title": title, "path": found})
        if files:
            return files
        # Zip existe mas não mapeamos arquivos: segue para rebuild abaixo.
    req = lazy_ctx["req"]
    results = lazy_ctx["results"]
    soil = lazy_ctx["soil"]
    crop = lazy_ctx["crop"]
    root_depth = float(lazy_ctx["root_depth"])
    total_rain = float(lazy_ctx["total_rain"])
    dose_total = sum(float(s.dose_kg_ha) for s in (req.solutes or []))
    rel_type, rel_days = _release_info(req)
    os.makedirs(graphs_dir, exist_ok=True)
    files = build_graph_files(
        results, soil, crop, float(total_rain), float(dose_total),
        rel_type, float(rel_days), float(root_depth), graphs_dir,
        _nutrients_list(req), water_only=bool(req.water_only),
    )
    try:
        if files:
            write_zip(files, zip_path)
    except Exception:
        pass
    return files


def ensure_steps_file(job_dir: str, lazy_ctx: dict) -> str:
    """Gera passo_a_passo.md sob demanda (sem re-solver); idempotente."""
    md_path = os.path.join(job_dir, "passo_a_passo.md")
    try:
        if os.path.exists(md_path):
            with open(md_path, encoding="utf-8") as f:
                content = f.read()
            if content.strip():
                return content
    except OSError:
        pass
    req = lazy_ctx["req"]
    results = lazy_ctx["results"]
    soil = lazy_ctx["soil"]
    crop = lazy_ctx["crop"]
    root_depth = float(lazy_ctx["root_depth"])
    total_rain = float(lazy_ctx["total_rain"])
    total_days = float(lazy_ctx["total_days"])
    try:
        steps_md = build_steps_markdown(req, results, soil, crop, root_depth, total_rain, total_days)
    except Exception:
        steps_md = ""
    try:
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(steps_md)
    except OSError:
        pass
    return steps_md


def execute_job_fast(
    req: SimulateRequest, job_dir: str, job_id: str | None = None
) -> tuple[SimulateResponse, str, str, dict]:
    """Caminho rápido do job: solve + perfis principais + excel + laudo.

    NÃO gera PNGs extras, graphs.zip nem passo_a_passo.md (lazy, sob demanda
    no GET /plots/{key}.png, /graphs.zip e /steps). Resolve o solver uma
    única vez; o contexto lazy permite gerar os extras sem re-solver.
    """
    os.makedirs(job_dir, exist_ok=True)
    _jid = job_id or os.path.basename(job_dir)
    results, soil, crop, root_depth, total_rain, total_days = _run_core(req)
    water_only = bool(req.water_only)
    # Imagens estáticas da tela de Resultados (iguais às do Gradio).
    try:
        screen_files = build_screen_images(req, results, soil, crop, root_depth, total_rain, job_dir)
    except Exception:
        screen_files = {"perfil": None, "btc": None, "evolucao": None, "galeria": []}
    # Caminho rápido: sem base64 por-soluto legado (compat: campos vazios).
    plots_b64: dict[str, str] = {}
    plot_b64: str | None = None
    # Compat: mantém perfil.png na raiz do job copiando tela/perfil.png.
    try:
        import shutil

        src_png = os.path.join(job_dir, "tela", "perfil.png")
        if os.path.exists(src_png):
            shutil.copyfile(src_png, os.path.join(job_dir, "perfil.png"))
    except Exception:
        pass
    try:
        descriptors = expected_extra_plots(req, results)
    except Exception:
        descriptors = []
    extra = _extra_plots_with_urls(descriptors, _jid)
    from .schemas import ScreenGalleryItem, ScreenImages

    def _screen_url(name: str | None) -> str | None:
        return f"/jobs/{_jid}/tela/{name}.png" if name else None

    try:
        _gal = []
        for g in (screen_files.get("galeria") or []):
            try:
                _gal.append(
                    ScreenGalleryItem(
                        symbol=str(g.get("symbol")),
                        name=str(g.get("name")),
                        url=f"/jobs/{_jid}/tela/{str(g.get('key'))}.png",
                    )
                )
            except Exception:
                continue
        screen = ScreenImages(
            perfil=_screen_url(screen_files.get("perfil")),
            btc=_screen_url(screen_files.get("btc")),
            evolucao=_screen_url(screen_files.get("evolucao")),
            galeria=_gal,
        )
    except Exception:
        screen = None
    resp = SimulateResponse(
        drainage_mm=float(results.q_bottom_cum_cm) * 10.0,
        solutes=_balances(req, results),
        plot_png_base64=plot_b64,
        plots_png_base64=plots_b64,
        extra_plots=extra,
        profiles=_profiles_payload(results),
        water_only=water_only,
        water_balance=_water_balance(req, results, total_rain, total_days),
        screen=screen,
    )
    excel_path = build_excel(req, results, soil, crop, root_depth, total_rain, total_days, job_dir)
    report_md = build_report(req, results, soil, crop, root_depth, total_rain, total_days)
    with open(os.path.join(job_dir, "laudo.md"), "w", encoding="utf-8") as f:
        f.write(report_md)
    lazy_ctx = {
        "req": req,
        "results": results,
        "soil": soil,
        "crop": crop,
        "root_depth": float(root_depth),
        "total_rain": float(total_rain),
        "total_days": float(total_days),
    }
    return resp, excel_path, report_md, lazy_ctx


def execute_job(req: SimulateRequest, job_dir: str) -> tuple[SimulateResponse, str, str]:
    """Roda uma vez e gera response + Excel + laudo no diretório do job.

    Compat (testes diretos/bench): caminho rápido, sem PNGs extras embutidos;
    extra_plots contém apenas {key,title,url} (sem base64). Os extras podem
    ser materializados via ensure_extra_files/ensure_steps_file com o
    contexto lazy de execute_job_fast (sem re-solver).
    """
    resp, excel_path, report_md, _lazy = execute_job_fast(
        req, job_dir, job_id=os.path.basename(job_dir)
    )
    return resp, excel_path, report_md


def _profiles_payload(results, max_pts: int = 200) -> dict:
    """Perfil final por soluto p/ gráfico interativo (amostrado)."""
    import numpy as _np

    z = _np.asarray(results.z, dtype=float)
    n = len(z)
    step = max(1, n // max_pts)
    idx = list(range(0, n, step))
    if idx[-1] != n - 1:
        idx.append(n - 1)
    out: dict = {"z": [float(z[i]) for i in idx], "solutes": {}}
    for sym, d in (getattr(results, "nutrient_results", {}) or {}).items():
        prof = _np.asarray(d.get("final_profile", []), dtype=float)
        if len(prof) == n:
            out["solutes"][sym] = {
                "name": str(d.get("name", sym)),
                "c": [float(prof[i]) for i in idx],
            }
    return out


def _sim_params(req: SimulateRequest, results, soil, crop, root_depth: float, total_rain: float, total_days: float) -> dict:
    """Params p/ Excel e laudo (mesmas chaves do Gradio sazonal).

    Inclui os defaults do Gradio para o modo seasonal: print_days por
    frações da duração e janela de análise = período todo.
    """
    water_only = bool(req.water_only)
    solutes = list(req.solutes or [])
    # B) dose efetiva: em fertirrigação, massa injetada (applied_kg_ha).
    _nr_raw = getattr(results, "nutrient_results", {}) or {}
    _eff_by_sym: dict[str, float] = {}
    for s in solutes:
        try:
            _td = float(s.dose_kg_ha)
        except (TypeError, ValueError):
            _td = 0.0
        _eff_by_sym[s.symbol] = _effective_dose(req, results, s.symbol, _td)
    dose_total = float(sum(_eff_by_sym.values()))
    first = solutes[0] if solutes else None
    # Cópia de nutrient_results com dose_kg_ha efetiva (não muta o solver).
    nr: dict = {}
    for _sym, _d in _nr_raw.items():
        try:
            _cp = dict(_d)
        except Exception:
            continue
        if _sym in _eff_by_sym:
            _cp["dose_kg_ha"] = float(_eff_by_sym[_sym])
        nr[_sym] = _cp
    prim = (nr.get(first.symbol, {}) or {}) if first is not None else {}
    z = getattr(results, "z", [0.0])
    try:
        prof_depth = float(max(z))
    except Exception:
        prof_depth = float(req.depth_cm)
    is_multi = len(solutes) > 1
    is_seasonal = _is_seasonal(req)
    if req.rain_series:
        _sw, _ew = _effective_window(req, len(req.rain_series))
    else:
        _sw, _ew = 1, int(float(total_days))
    _print_days_eff = _effective_print_days(req, total_days, _sw, _ew)
    _n_win = int(float(total_days))
    # Rótulo da janela como no Gradio sazonal (sw/ew efetivos vs ano cheio).
    _win_txt = f"{_sw}–{_ew}" if (_sw > 1 or _ew < 365) else "ano cheio (1–365)"
    _pmode = (req.placement.mode or "surface")
    _ptop, _pbot = float(req.placement.z_top_cm), float(req.placement.z_bottom_cm)
    if _pmode == "furrow":
        _ptop, _pbot = 5.0, 10.0
    elif _pmode == "fertigation":
        _ptop, _pbot = 0.0, 0.0
    try:
        _peak_raw = prim.get("peak_depth_cm", 0.0)
        _peak = float(_peak_raw if _peak_raw is not None else 0.0)
    except (TypeError, ValueError):
        _peak = 0.0
    if req.et0_series:
        try:
            _full_et0 = [max(0.0, float(v or 0.0)) for v in req.et0_series]
            # Média na janela de análise efetiva (como a série usada no solver).
            _et0_vals = _full_et0[_sw - 1:_ew] if req.rain_series else _full_et0
            _et0_mean = float(sum(_et0_vals) / max(len(_et0_vals), 1))
        except (TypeError, ValueError):
            _et0_mean = float(req.et0_mm_day)
    else:
        _et0_mean = float(req.et0_mm_day)
    try:
        _evap_day = float(getattr(results, "evap_cum_cm", 0.0) or 0.0) * 10.0 / max(float(total_days), 1.0)
        _transp_day = float(getattr(results, "transp_cum_cm", 0.0) or 0.0) * 10.0 / max(float(total_days), 1.0)
    except (TypeError, ValueError):
        _evap_day, _transp_day = 0.0, 0.0
    rel_type = ((first.release_type if first is not None else None) or "immediate")
    _nutr_name = first.name if first is not None else "Somente Água"
    _nutr_sym = first.symbol if first is not None else "water_only"
    # D) Etapa 1 do passo a passo: nome/garantia só do catálogo quando o
    # modal originou as doses; senão "Dose Direta do Elemento" (100%).
    try:
        _first_eff = float(_eff_by_sym.get(first.symbol, dose_total)) if first is not None else 0.0
    except (TypeError, ValueError):
        _first_eff = float(dose_total)
    _fert_name, _fert_label, _gross, _dose_note = (
        "Dose Direta do Elemento", "Dose Direta do Elemento", _first_eff,
        f"{_first_eff:.1f} kg/ha de {_nutr_name}" if first is not None else "—",
    )
    try:
        _freq = getattr(req, "fertilizer", None)
        if (
            _freq is not None and first is not None
            and not _is_fertigation(req) and not water_only
        ):
            from hydrus_core.literature_database import COMMERCIAL_FERTILIZERS as _COMM
            from .fertilizers import fertilizer_nutrient_pcts as _pcts_fn

            _fk = str(_freq.fert_key or "")
            _gd = float(_freq.gross_dose or 0.0)
            _cat = _COMM.get(_fk) if _fk else None
            _pcts = _pcts_fn(_fk) if _fk else {}
            _teor = float((_pcts or {}).get(first.symbol, 0.0) or 0.0)
            if _cat and _teor > 0:
                _nm = str(_cat.get("name", _fk) or _fk)
                _fert_name, _fert_label, _gross = _nm, _nm, _gd
                _dose_note = f"{_gd:.0f} kg/ha de {_nm}"
    except Exception:
        pass
    params = {
        "sim_type": ("seasonal" if is_seasonal else "column"),
        "mode_label": (
            f"Simulação Série Hídrica ({_n_win} dias, janela {_win_txt})"
            if is_seasonal else "column"
        ),
        "nutrient_label": (
            "Somente Água" if water_only
            else ("Formulação Multi-Nutriente" if is_multi else _nutr_name)
        ),
        "nutrient_symbol": _nutr_sym,
        "fertilizer_label": _fert_label,
        "fertilizer_name": _fert_name,
        "gross_dose": _gross,
        "elemental_dose": dose_total,
        "soil_name": soil.name,
        "soil_citation": f"Solo {soil.name}",
        "theta_r": float(soil.theta_r),
        "theta_s": float(soil.theta_s),
        "alpha": float(soil.alpha),
        "n": float(soil.n),
        "ks": float(soil.ks),
        "bulk_density": float(soil.bulk_density),
        "kd": float(first.kd) if first is not None else 0.0,
        "kd_citation": "Referência para a textura (ajustável; não calibrado)",
        "dispersivity": float(first.dispersivity_cm) if first is not None else float(req.depth_cm) / 10.0,
        "crop_name": (crop.name if crop else "Perfil de solo nu (sem cultura)"),
        "crop_citation": _crop_citation(req, crop),
        "root_depth_cm": float(root_depth),
        "h1": float(crop.h1 if crop else 0.0),
        "h2": float(crop.h2 if crop else 0.0),
        "h3": float(crop.h3 if crop else 0.0),
        "h4": float(crop.h4 if crop else 0.0),
        "rain_mm": float(total_rain),
        "total_days": float(total_days),
        # Umidade efetiva: série usa seasonal_initial_moisture_pct (default 100% = CC).
        "initial_moisture_pct": float(req.seasonal_initial_moisture_pct if is_seasonal else req.initial_moisture_pct),
        "leaching_pct": float(prim.get("leaching_ratio_pct", 0.0) or 0.0),
        "retained_pct": float(prim.get("retained_root_pct", 0.0) or 0.0),
        "leaching_ratio_pct": float(prim.get("leaching_ratio_pct", 0.0) or 0.0),
        "retained_root_pct": float(prim.get("retained_root_pct", 0.0) or 0.0),
        "uptaken_pct": float(prim.get("uptaken_pct", 0.0) or 0.0),
        "peak_depth_cm": _peak,
        "q_bottom_cm": float(getattr(results, "q_bottom_cum_cm", 0.0) or 0.0),
        "active_depth_cm": float(_pbot - _ptop) if _pbot > _ptop else 0.0,
        "placement_top_cm": float(_ptop),
        "placement_bottom_cm": float(_pbot),
        "dose_note": _dose_note,
        "release_type": rel_type,
        "release_days": float((first.release_days if first is not None else None) or 60.0),
        "release_label": (
            "Liberação Controlada / Lenta (Polímero / CRF)"
            if rel_type == "controlled" else "Convencional (Solubilização Instantânea)"
        ),
        "is_multi_nutr": bool(is_multi),
        "nutrient_results": nr,
        "water_only": bool(water_only),
        "profile_depth_cm": float(prof_depth),
        "storage_mm": float(_storage_mm(results)),
        "runoff_mm": float(getattr(results, "runoff_cum_cm", 0.0) or 0.0) * 10.0,
        "drainage_mm": float(getattr(results, "q_bottom_cum_cm", 0.0) or 0.0) * 10.0,
        "evap_mm_day": float(_evap_day),
        "transp_mm_day": float(_transp_day),
        "et0_mm_day": float(_et0_mean),
        "obs_depths_cm": list(getattr(results, "obs_depths_cm", []) or []),
        # Janela de análise efetiva + dias de leitura (dias de ensaio).
        "print_days": list(_print_days_eff),
        "analysis_start_day": int(_sw),
        "analysis_end_day": int(_ew),
        "window_label": _win_txt,
    }
    # Ciclo da cultura / Kc dual / teto (laudo, Excel e passo a passo).
    try:
        _cyc_info = _cycle_info(req, crop)
    except Exception:
        _cyc_info = {}
    for _k in ("cycle_txt", "kc_dual_txt", "uptake_cap_txt", "crop_start_txt", "hydrus_txt"):
        params[_k] = str((_cyc_info or {}).get(_k, "") or "")
    for _k in ("planting_day_cal", "harvest_day_cal"):
        params[_k] = (_cyc_info or {}).get(_k)
    return params


def _seasonal_results_for_excel(req: SimulateRequest, results, soil, crop, root_depth: float,
                                total_rain: float, total_days: float):
    """Cópia de results com os atributos que _export_seasonal_sheets lê.

    O exportador sazonal espera perfis indexados por dia
    (dicts dia -> perfil): print_days, theta_profiles (dict),
    conc_total_profiles, além de metadados (nutrient_symbol, soil_name…).
    O solver devolve theta_profiles como lista e print_profiles como
    dict dia -> {"theta", "c_total"}; aqui convertemos sem mutar o
    objeto original (o laudo usa as listas).
    """
    import copy

    first = (req.solutes or [None])[0]
    sym = first.symbol if first is not None else "water_only"
    if req.rain_series:
        _sw0, _ew0 = _effective_window(req, len(req.rain_series))
    else:
        _sw0, _ew0 = 1, int(float(total_days))
    print_days = _effective_print_days(req, total_days, _sw0, _ew0)
    pp = getattr(results, "print_profiles", None) or {}
    try:
        _z = getattr(results, "z", None)
        n_z = len(_z) if _z is not None else 0
    except TypeError:
        n_z = 0
    theta_d: dict = {}
    tot_d: dict = {}
    for d in print_days:
        snap = pp.get(float(d))
        if snap is None:
            snap = pp.get(int(d))
        if not isinstance(snap, dict):
            continue
        th = snap.get("theta")
        try:
            if th is not None and len(th) == n_z:
                theta_d[d] = th
        except TypeError:
            pass
        cmap = snap.get("c_total") or {}
        arr = cmap.get(sym)
        try:
            if arr is not None and len(arr) == n_z:
                tot_d[d] = arr
        except TypeError:
            pass
    # Fallback: dia final usa o perfil final do nutriente.
    try:
        nr = getattr(results, "nutrient_results", {}) or {}
        final_prof = (nr.get(sym) or {}).get("final_profile")
        if print_days and final_prof is not None and len(final_prof) == n_z:
            last = print_days[-1]
            tot_d.setdefault(last, final_prof)
    except (TypeError, ValueError):
        pass
    try:
        res = copy.copy(results)
    except Exception:
        res = results
        return res
    try:
        res.print_days = list(print_days)
        res.theta_profiles = dict(theta_d)
        res.conc_total_profiles = dict(tot_d)
        if not hasattr(res, "conc_aq_profiles"):
            res.conc_aq_profiles = {}
        if not hasattr(res, "conc_profiles"):
            res.conc_profiles = {}
        res.nutrient_symbol = sym
        res.soil_name = getattr(res, "soil_name", None) or soil.name
        res.nutrient_name = getattr(res, "nutrient_name", None) or (first.name if first is not None else "Somente Água")
        res.kd_used = getattr(res, "kd_used", None) or (float(first.kd) if first is not None else 0.0)
        res.root_depth_cm = getattr(res, "root_depth_cm", None) or float(root_depth)
        res.total_rain_mm = getattr(res, "total_rain_mm", None) or float(total_rain)
    except Exception:
        pass
    return res


def build_excel(req: SimulateRequest, results, soil, crop, root_depth: float,
                total_rain: float, total_days: float, job_dir: str) -> str:
    from hydrus_core.export_excel import export_soil_profile_excel

    out = os.path.join(job_dir, "perfil.xlsx")
    mode = "seasonal" if _is_seasonal(req) else "column"
    params = _sim_params(req, results, soil, crop, root_depth, total_rain, total_days)
    res_for_excel = (
        _seasonal_results_for_excel(req, results, soil, crop, root_depth, total_rain, total_days)
        if mode == "seasonal" else results
    )
    return export_soil_profile_excel(
        res_for_excel, out,
        sim_params=params,
        mode=mode,
    )


def _report_hydro(req: SimulateRequest, results, total_days: float) -> tuple[float, float, float, float, float]:
    """Hidro-args extras do laudo coluna, iguais aos do Gradio (runoff/storage/ET)."""
    try:
        storage = float(_storage_mm(results))
    except Exception:
        storage = 0.0
    try:
        runoff = float(getattr(results, "runoff_cum_cm", 0.0) or 0.0) * 10.0
    except (TypeError, ValueError):
        runoff = 0.0
    try:
        evap_day = float(getattr(results, "evap_cum_cm", 0.0) or 0.0) * 10.0 / max(float(total_days), 1.0)
        transp_day = float(getattr(results, "transp_cum_cm", 0.0) or 0.0) * 10.0 / max(float(total_days), 1.0)
    except (TypeError, ValueError):
        evap_day, transp_day = 0.0, 0.0
    if req.et0_series:
        try:
            et0_vals = [max(0.0, float(v or 0.0)) for v in req.et0_series]
            et0_mean = float(sum(et0_vals) / max(len(et0_vals), 1))
        except (TypeError, ValueError):
            et0_mean = float(req.et0_mm_day)
    else:
        et0_mean = float(req.et0_mm_day)
    return storage, runoff, evap_day, transp_day, et0_mean


def _report_active_depth(req: SimulateRequest) -> float:
    _pmode = (req.placement.mode or "surface")
    _ptop, _pbot = float(req.placement.z_top_cm), float(req.placement.z_bottom_cm)
    if _pmode == "furrow":
        _ptop, _pbot = 5.0, 10.0
    elif _pmode == "fertigation":
        _ptop, _pbot = 0.0, 0.0
    return float(_pbot - _ptop) if _pbot > _ptop else 0.0


def _seasonal_solute_report(req: SimulateRequest, results, soil, crop, root_depth: float,
                            total_rain: float, total_days: float) -> str:
    """Laudo sazonal com solutos — texto literal do Gradio (caminho série diária).

    O Gradio NÃO usa generate_advanced_report neste modo; monta o bloco
    abaixo (mesmos títulos, rótulos, negritos, ordem e formatação numérica).
    O passo a passo é concatenado pelo frontend, não faz parte do laudo.
    """
    import math as _math

    if req.rain_series:
        _sw, _ew = _effective_window(req, len(req.rain_series))
        _full_len = len(req.rain_series)
    else:
        _sw, _ew = 1, int(float(total_days))
        _full_len = int(float(total_days))
    _n_win = int(float(total_days))
    _win_txt = f"{_sw}–{_ew}" if (_sw > 1 or _ew < 365) else "ano cheio (1–365)"
    _base_source = getattr(req, "series_source_label", None) or "Série climática do polo (NASA POWER)"
    if (_sw > 1 or _ew < _full_len):
        source_label = f"{_base_source} (janela de análise: dias {_sw}–{_ew})"
    else:
        source_label = _base_source

    try:
        _zmax = float(max(getattr(results, "z", [0.0])))
    except Exception:
        try:
            _zmax = float(req.depth_cm)
        except (TypeError, ValueError):
            _zmax = 0.0
    prof_depth = float(_zmax)
    drainage_mm = float(getattr(results, "q_bottom_cum_cm", 0.0) or 0.0) * 10.0
    storage_mm = float(_storage_mm(results))
    if crop is not None:
        try:
            crop_txt = f"{crop.name} (kc={float(crop.kc):.2f}, raiz {float(crop.root_depth_cm):.0f} cm)"
        except (TypeError, ValueError):
            crop_txt = f"{crop.name}"
    else:
        crop_txt = "Perfil de solo nu (sem cultura)"
    try:
        _cyc_rep = _cycle_info(req, crop)
    except Exception:
        _cyc_rep = {}
    _cycle_line = str((_cyc_rep or {}).get("cycle_txt", "") or "")
    _kc_dual_line = str((_cyc_rep or {}).get("kc_dual_txt", "") or "")
    _cap_dem_line = str((_cyc_rep or {}).get("uptake_cap_txt", "") or "")
    _start_line = str((_cyc_rep or {}).get("crop_start_txt", "") or "")
    _hyd_line = str((_cyc_rep or {}).get("hydrus_txt", "") or "")
    _cyc_block = ""
    if _cycle_line:
        _cyc_block += f"\n* **Ciclo da cultura:** {_cycle_line}"
    if _kc_dual_line:
        _cyc_block += f"\n* **Partição da ET:** {_kc_dual_line}"
    if _cap_dem_line:
        _cyc_block += f"\n* **Teto de absorção:** {_cap_dem_line}"
    if _start_line:
        _cyc_block += f"\n* **Cultura no início:** {_start_line}"
    if _hyd_line:
        _cyc_block += f"\n* **Parâmetros equivalentes no HYDRUS-1D:** {_hyd_line}"

    _pm = str((req.placement.mode if req.placement else None) or "surface").lower()
    if _pm == "furrow":
        placement_label = "No Sulco de Plantio (5 a 10 cm)"
    elif _pm == "custom":
        try:
            _ct = float(req.placement.z_top_cm)
        except (TypeError, ValueError):
            _ct = 0.0
        try:
            _cb = float(req.placement.z_bottom_cm)
        except (TypeError, ValueError):
            _cb = 0.0
        placement_label = f"Profundidade Personalizada ({_ct:.0f} a {_cb:.0f} cm)"
    elif _pm == "fertigation":
        try:
            _pu = float(req.placement.fertigation_pulse_days or 0.0)
        except (TypeError, ValueError):
            _pu = 0.0
        _pulse_txt = "contínuo" if _pu <= 0 else f"{_pu:.1f} d"
        placement_label = f"Fertirrigação Líquida (C₀ calculado por nutriente = dose ÷ lâmina no período de injeção, pulso = {_pulse_txt})"
    else:
        placement_label = "A lanço / Superfície (0 a 2 cm)"

    try:
        _app_raw = float(req.placement.application_day or 0.0) if req.placement else 0.0
    except (TypeError, ValueError):
        _app_raw = 0.0
    _app_cal = int(round(_app_raw)) if _app_raw else 0

    _nr = getattr(results, "nutrient_results", {}) or {}

    def _kgf(_dd: dict, _key: str, _fb: float = 0.0) -> float:
        try:
            return float((_dd or {}).get(_key, _fb))
        except (TypeError, ValueError):
            return float(_fb)

    nutrients_list = [
        {
            "symbol": str(s.symbol),
            "name": str(s.name),
            "dose_kg_ha": _effective_dose(req, results, str(s.symbol), float(s.dose_kg_ha)),
            "kd": float(s.kd),
        }
        for s in (req.solutes or [])
    ]
    elemental_dose = float(sum(n["dose_kg_ha"] for n in nutrients_list)) if nutrients_list else 0.0
    # Massa injetada via fertirrigação (C0 calculado por nutriente; aplicada ≈ dose).
    _fert_note_txt = ""
    if _is_fertigation(req) and nutrients_list:
        _c0_parts = []
        for _n in nutrients_list:
            try:
                _c0v = float(((_nr.get(_n["symbol"]) or {}).get("fertigation_c0_mg_l", 0.0)) or 0.0)
            except (TypeError, ValueError):
                _c0v = 0.0
            _c0_parts.append(f"{_n['symbol']} C₀ = {_c0v:.1f} mg/L")
        _fert_note_txt = (
            f"\n* **Massa injetada via fertirrigação:** **{elemental_dose:.1f} kg/ha** "
            f"({'; '.join(_c0_parts)} — C₀ calculado por nutriente = dose ÷ lâmina no período de injeção; "
            f"a massa injetada real ≈ dose, menos o que escoar)"
        )
    try:
        _root_seas = float(crop.root_depth_cm) if crop is not None else float(prof_depth)
    except (TypeError, ValueError):
        _root_seas = float(prof_depth)
    is_multi_nutr = len(nutrients_list) > 1

    if is_multi_nutr:
        _sp_map = {"N": "NO₃⁻", "K": "K⁺", "S": "SO₄²⁻", "Ca": "Ca²⁺", "Mg": "Mg²⁺", "P": "H₂PO₄⁻"}
        _sp_list = ", ".join(            f"{n['symbol']} como {_sp_map.get(n['symbol'], n['symbol'])}" for n in nutrients_list
        )
        solutes_header_txt = (f"* **Formulação:** **{len(nutrients_list)} solutos** "
                              f"({', '.join(n['symbol'] for n in nutrients_list)}) | "
                              f"**Dose total:** **{elemental_dose:.0f} kg/ha**\n"
                              f"* **Espécies simuladas (fixas, sem transformações):** {_sp_list}")

        def _bloco_soluto(n):
            _dd = (_nr.get(n['symbol']) or {})
            _rt = float(_dd.get('retained_root_pct', 0.0) or 0.0)
            _lq = float(_dd.get('leaching_ratio_pct', 0.0) or 0.0)
            try:
                _bt = float(_dd.get('leached_bottom_pct', 0.0) or 0.0)
            except (TypeError, ValueError):
                _bt = 0.0
            _bw = max(0.0, _lq - _bt)
            try:
                _up = float(_dd.get('uptaken_pct', 0.0) or 0.0)
            except (TypeError, ValueError):
                _up = 0.0
            try:
                _cp = float(_dd.get('capsule_pct', 0.0) or 0.0)
            except (TypeError, ValueError):
                _cp = 0.0
            _inp = _kgf(_dd, 'input_kg_ha', float(n['dose_kg_ha']))
            _res = _kgf(_dd, 'residual_kg_ha')
            _dose_txt = (f"dose {float(n['dose_kg_ha']):.1f} + residual {_res:.1f} kg/ha"
                         if _res > 0.005 else f"dose {float(n['dose_kg_ha']):.1f} kg/ha")
            _line = (f"* **{n['symbol']}** — {_dose_txt} | Kd {float(n['kd']):.4f} cm³/g | "
                    f"retido {_rt:.1f}% ({_kgf(_dd, 'retained_kg_ha', _inp * _rt / 100.0):.1f} kg/ha) | "
                    f"abaixo no perfil {_bw:.1f}% | fundo {_bt:.1f}%")
            if _up > 0.05:
                _cap_txt = ""
                if bool(_dd.get('uptake_capped')):
                    _cap_txt = " (limitada pela marcha de absorção da cultura em parte do período"
                    try:
                        _capv = _dd.get('uptake_cap_kg_ha', None)
                        if _capv is not None:
                            _cap_txt += f"; teto no período: {float(_capv):.1f} kg/ha"
                    except (TypeError, ValueError):
                        pass
                    _cap_txt += ")"
                _line += f" | absorvido {_up:.1f}% ({_kgf(_dd, 'uptaken_kg_ha', _inp * _up / 100.0):.1f} kg/ha){_cap_txt}"
            if _cp > 0.05:
                _line += f" | no grânulo {_cp:.1f}%"
            return _line
        solutes_block_txt = "\n".join(_bloco_soluto(n) for n in nutrients_list)
    else:
        _n0 = nutrients_list[0] if nutrients_list else {"symbol": "", "name": "", "dose_kg_ha": 0.0, "kd": 0.0}
        nutr_sym = str(_n0.get("symbol") or "")
        nutr_display_name = str(_n0.get("name") or nutr_sym)
        _dd0 = (_nr.get(nutr_sym) or {})
        ret_root_pct = float((_dd0.get("retained_root_pct", 0.0)) or 0.0)
        retained_pct = float(ret_root_pct)
        retained_kg = _kgf(_dd0, "retained_kg_ha", elemental_dose * retained_pct / 100.0)
        leached_pct = float((_dd0.get("leaching_ratio_pct", 0.0)) or 0.0)
        uptaken_pct = float((_dd0.get("uptaken_pct", 0.0)) or 0.0)
        uptaken_kg = _kgf(_dd0, "uptaken_kg_ha", elemental_dose * uptaken_pct / 100.0)
        _res0 = _kgf(_dd0, "residual_kg_ha")
        _dose0_txt = (f"**{elemental_dose:.0f} kg/ha** (dose {float(_n0.get('dose_kg_ha', elemental_dose)):.0f} + residual {_res0:.1f})"
                      if _res0 > 0.005 else f"**{elemental_dose:.0f} kg/ha**")
        peak_cm = _dd0.get("peak_depth_cm", None)
        try:
            _ret_prof_s = float((_dd0.get("retained_profile_pct", float(getattr(results, "retained_profile_pct", 0.0)))) or 0.0)
        except (TypeError, ValueError):
            try:
                _ret_prof_s = float(getattr(results, "retained_profile_pct", 0.0))
            except (TypeError, ValueError):
                _ret_prof_s = 0.0
        ret_deep_pct = max(0.0, _ret_prof_s - ret_root_pct)
        _ret_prof_kg = _kgf(_dd0, "retained_profile_kg_ha", elemental_dose * _ret_prof_s / 100.0)
        _ret_deep_kg = max(0.0, _ret_prof_kg - retained_kg)
        if crop is not None and float(getattr(crop, "root_depth_cm", 0.0) or 0.0) < prof_depth and ret_root_pct > 0:
            ret_str = (
                f"* **Retido na camada avaliada (0–{_root_seas:.0f} cm):** **{ret_root_pct:.1f}%** ({retained_kg:.1f} kg/ha)\n"
                f"  * *Em subsuperfície ({_root_seas:.0f}–{prof_depth:.0f} cm):* **{ret_deep_pct:.1f}%** ({_ret_deep_kg:.1f} kg/ha)"
            )
        else:
            ret_str = f"* **Retido no perfil (0–{prof_depth:.0f} cm):** **{retained_pct:.1f}%** ({retained_kg:.1f} kg/ha)"
        solutes_header_txt = (f"* **Nutriente avaliado:** {nutr_display_name} ({nutr_sym}) | "
                              f"Dose: {_dose0_txt}")
        _capped_s0 = ""
        if bool(_dd0.get("uptake_capped")):
            _capped_s0 = " (limitada pela marcha de absorção da cultura em parte do período"
            try:
                _capv0 = _dd0.get("uptake_cap_kg_ha", None)
                if _capv0 is not None:
                    _capped_s0 += f"; teto no período: {float(_capv0):.1f} kg/ha"
            except (TypeError, ValueError):
                pass
            _capped_s0 += ")"
        _upt_line_s = (f"\n* **Absorvido pela cultura (limitado pela demanda):** **{uptaken_pct:.1f}%** ({uptaken_kg:.1f} kg/ha){_capped_s0}"
                       if float(uptaken_pct or 0.0) > 0.05 else "")
        try:
            _bot_s = float(((_nr.get(nutr_sym) or {}).get("leached_bottom_pct", 0.0)) or 0.0)
        except (TypeError, ValueError):
            _bot_s = 0.0
        _below_s = max(0.0, float(leached_pct or 0.0) - _bot_s)
        _peak_txt = (
            'indefinido' if peak_cm is None or (isinstance(peak_cm, float) and _math.isnan(float(peak_cm)))
            else f'{float(peak_cm):.1f} cm'
            if peak_cm is not None else 'indefinido'
        )
        try:
            # cobre NaN não-float (ex.: numpy) como o Gradio
            if peak_cm is not None and _math.isnan(float(peak_cm)):
                _peak_txt = 'indefinido'
            elif peak_cm is not None:
                _peak_txt = f'{float(peak_cm):.1f} cm'
            else:
                _peak_txt = 'indefinido'
        except (TypeError, ValueError):
            _peak_txt = 'indefinido'
        try:
            _cap_s = float(((_nr.get(nutr_sym) or {}).get("capsule_pct", 0.0)) or 0.0)
        except (TypeError, ValueError):
            _cap_s = 0.0
        _cap_line_s = (f"\n* **Ainda no grânulo (não liberado):** **{_cap_s:.1f}%** ({_kgf(_dd0, 'capsule_kg_ha', elemental_dose * _cap_s / 100.0):.1f} kg/ha)"
                       if float(_cap_s or 0.0) > 0.05 else "")
        _below_kg_s = _kgf(_dd0, "leached_kg_ha", elemental_dose * leached_pct / 100.0) - _kgf(_dd0, "leached_bottom_kg_ha", elemental_dose * _bot_s / 100.0)
        _bot_kg_s = _kgf(_dd0, "leached_bottom_kg_ha", elemental_dose * _bot_s / 100.0)
        solutes_block_txt = (f"{ret_str}\n"
                             f"* **Abaixo da camada no perfil ({_root_seas:.0f}–{prof_depth:.0f} cm):** **{_below_s:.1f}%** ({max(0.0, _below_kg_s):.1f} kg/ha)\n"
                             f"* **Atravessou o fundo ({prof_depth:.0f} cm):** **{_bot_s:.1f}%** ({_bot_kg_s:.1f} kg/ha)"
                             f"{_upt_line_s}{_cap_line_s}\n"
                             f"* **Profundidade do pico máximo:** **{_peak_txt}**")

    try:
        _eS = float(getattr(results, "evap_cum_cm", 0.0) or 0.0) * 10.0
        _tS = float(getattr(results, "transp_cum_cm", 0.0) or 0.0) * 10.0
        _roS = float(getattr(results, "runoff_cum_cm", 0.0) or 0.0) * 10.0
        _clS = float(total_rain) - (_eS + _tS + float(drainage_mm) + _roS + float(storage_mm))
        _hydro_seas = (
            f"* **Evapotranspiração real (E+T):** **{_eS + _tS:.1f} mm** (E {_eS:.1f} + T {_tS:.1f} mm)\n"
            f"* **Escoamento superficial:** **{_roS:.1f} mm**\n"
            f"* **Δ Armazenamento no perfil (θfinal−θinicial):** **{float(storage_mm):+.1f} mm**\n"
            f"* **Resíduo de fechamento hídrico (P−E−T−D−RO−ΔS):** **{_clS:+.2f} mm**\n"
        )
    except Exception:
        _hydro_seas = ""
    _scope_seas = (
        "\n\n> ℹ️ **Escopo e limites:** cada soluto representa uma **espécie química fixa** "
        "(N como NO₃⁻, K como K⁺, S como SO₄²⁻); o modelo **não simula transformações químicas**. "
        "Kd de **referência bibliográfica** para a textura do solo, ajustáveis — **não calibrados** "
        "para este talhão. Absorção **pela cultura (limitada pela demanda nutricional do ciclo)**. "
        "Uso recomendado: **comparação entre manejos/cenários**, não previsão garantida."
    )
    report = f"""### Laudo de Simulação — Série Hídrica ({_n_win} dias, janela {_win_txt})

#### 1. Cenário Hídrico
* **Fonte da série:** {source_label}
* **Precipitação no período:** **{float(total_rain):.1f} mm**
* **Solo:** {soil.name} | **Cultura:** {crop_txt}{_cyc_block}
{solutes_header_txt}{_fert_note_txt}
* **Domínio do perfil:** **0 a {prof_depth:.0f} cm**

#### 2. Balanço de Massa ao Longo de {_n_win} Dias
* **Drenagem profunda acumulada:** **{float(drainage_mm):.1f} mm**
{_hydro_seas}{solutes_block_txt}
* **Método de aplicação:** {placement_label} | **Dia da aplicação (calendário):** {_app_cal}{_scope_seas}
""".strip()
    return report


def build_report(req: SimulateRequest, results, soil, crop, root_depth: float,
                 total_rain: float, total_days: float) -> str:
    """Laudo multi-soluto via hydrus_core.agronomic_report (o core já cobre N solutos).

    Usa as mesmas funções do Gradio (generate_advanced_report / generate_column_report);
    como results.nutrient_results contém todos os solutos, o comparativo multi-nutriente
    e o cabeçalho multi-soluto são gerados pelo core sem texto novo.
    """
    from hydrus_core.agronomic_report import generate_advanced_report, generate_column_report
    from hydrus_core.explanatory_pipeline import generate_simulation_step_by_step

    if bool(req.water_only):
        # Laudo do modo "somente água": balanço hídrico (texto portado do Gradio)
        # + passo a passo do core (que já cobre water_only).
        params = _sim_params(req, results, soil, crop, root_depth, total_rain, total_days)
        storage, runoff, evap_day, transp_day, _et0 = _report_hydro(req, results, total_days)
        if _is_seasonal(req):
            if req.rain_series:
                _sw_r, _ew_r = _effective_window(req, len(req.rain_series))
            else:
                _sw_r, _ew_r = 1, int(float(total_days))
            _n_win_r = int(float(total_days))
            _win_txt_r = f"{_sw_r}–{_ew_r}" if (_sw_r > 1 or _ew_r < 365) else "ano cheio (1–365)"
            _full_len = len(req.rain_series) if req.rain_series else _n_win_r
            _win_suffix = (
                f" (janela de análise: dias {_sw_r}–{_ew_r})"
                if (_sw_r > 1 or _ew_r < _full_len) else ""
            )
            base = seasonal_water_only_report(
                soil=soil, crop=crop, prof_depth=float(params["profile_depth_cm"]),
                total_rain=float(total_rain), n_win=_n_win_r, win_txt=_win_txt_r,
                source_label=f"Série diária informada pelo usuário{_win_suffix}",
                drainage_mm=float(params["drainage_mm"]), runoff_mm=float(runoff),
                storage_mm=float(storage),
                obs_depths_cm=list(getattr(results, "obs_depths_cm", []) or []),
            )
        else:
            z = getattr(results, "z", [0.0])
            try:
                prof_depth = float(max(z))
            except Exception:
                prof_depth = float(req.depth_cm)
            base = column_water_only_report(
                soil=soil, crop=crop, col_depth=float(prof_depth),
                rain_mm=float(total_rain), total_days=float(total_days),
                initial_moisture_pct=float(req.initial_moisture_pct),
                evap_mm_day=float(evap_day), transp_mm_day=float(transp_day),
                drainage_mm=float(getattr(results, "q_bottom_cum_cm", 0.0) or 0.0) * 10.0,
                runoff_mm=float(runoff), storage_mm=float(storage),
                obs_depths_cm=list(getattr(results, "obs_depths_cm", []) or []),
            )
        step_md, step_html = generate_simulation_step_by_step(params)
        return f"{base}\n\n---\n\n{step_md}"

    first = (req.solutes or [None])[0]
    # B) dose efetiva em fertirrigação; resultados copiados com dose efetiva.
    _eff_total = 0.0
    for s in (req.solutes or []):
        try:
            _eff_total += float(_effective_dose(req, results, str(s.symbol), float(s.dose_kg_ha)))
        except (TypeError, ValueError):
            continue
    dose_total = float(_eff_total)
    active_depth = _report_active_depth(req)
    if _is_seasonal(req):
        # Paridade Gradio: laudo sazonal com solutos é o bloco literal do
        # Gradio (sem generate_advanced_report; passo a passo vai no frontend).
        return _seasonal_solute_report(req, results, soil, crop, root_depth, total_rain, total_days)
    z = getattr(results, "z", [0.0])
    try:
        prof_depth = float(max(z))
    except Exception:
        prof_depth = float(req.depth_cm)
    storage, runoff, evap_day, transp_day, et0_mean = _report_hydro(req, results, total_days)
    # Cópia com doses efetivas p/ o laudo de coluna (não muta o solver).
    import copy as _copy
    try:
        res_rep = _copy.copy(results)
        _nr_rep = {}
        for _sym, _d in ((getattr(results, "nutrient_results", {}) or {}).items()):
            try:
                _cd = dict(_d)
            except Exception:
                continue
            for s in (req.solutes or []):
                if str(s.symbol) == str(_sym):
                    try:
                        _cd["dose_kg_ha"] = float(_effective_dose(req, results, str(_sym), float(s.dose_kg_ha)))
                    except (TypeError, ValueError):
                        pass
            _nr_rep[_sym] = _cd
        res_rep.nutrient_results = _nr_rep
    except Exception:
        res_rep = results
    _rep = generate_column_report(
        results=res_rep, soil=soil, rain_mm=float(total_rain),
        fertilizer_dose_kg_ha=dose_total, target_depth_cm=float(root_depth),
        column_height_cm=float(prof_depth), nutrient_symbol=first.symbol,
        nutrient_name=first.name, kd_used=float(first.kd),
        release_type=(first.release_type or "immediate"),
        release_days=float(first.release_days or 60.0),
        total_days=float(total_days),
        active_depth_cm=float(active_depth),
        runoff_mm=float(runoff),
        storage_mm=float(storage),
        evap_mm_day=float(evap_day),
        transp_mm_day=float(transp_day),
        et0_mm_day=float(et0_mean),
        is_fertigation=bool(_is_fertigation(req)),
    )
    if _is_fertigation(req):
        try:
            _nr_rep_c0 = getattr(results, "nutrient_results", {}) or {}
            _c0_parts_r = []
            for _s in (req.solutes or []):
                try:
                    _c0v_r = float(((_nr_rep_c0.get(str(_s.symbol)) or {}).get("fertigation_c0_mg_l", 0.0)) or 0.0)
                except (TypeError, ValueError):
                    _c0v_r = 0.0
                _c0_parts_r.append(f"{_s.symbol} C₀ = {_c0v_r:.1f} mg/L")
            _c0_txt_r = "; ".join(_c0_parts_r) if _c0_parts_r else "C₀ calculado por nutriente"
        except Exception:
            _c0_txt_r = "C₀ calculado por nutriente"
        _fert_line = (f"\n* **Massa injetada via fertirrigação:** **{dose_total:.1f} kg/ha** "
                      f"({_c0_txt_r} = dose ÷ lâmina no período de injeção; "
                      f"a massa injetada real ≈ dose, menos o que escoar)")
        # Insere após a linha de Regime Hídrico quando presente.
        if "Regime Hídrico:" in _rep:
            _lines = _rep.splitlines()
            _out_l = []
            _done = False
            for _ln in _lines:
                _out_l.append(_ln)
                if (not _done) and _ln.startswith("* **Regime Hídrico:"):
                    _out_l.append(f"* **Massa injetada via fertirrigação:** **{dose_total:.1f} kg/ha** ({_c0_txt_r} = dose ÷ lâmina no período de injeção; a massa injetada real ≈ dose, menos o que escoar)")
                    _done = True
            _rep = "\n".join(_out_l)
        else:
            _rep = f"{_rep}{_fert_line}"
    try:
        _ci = _cycle_info(req, crop)
    except Exception:
        _ci = {}
    _extra = ""
    if str((_ci or {}).get("crop_start_txt", "") or ""):
        _extra += f"\n* **Cultura no início:** {str((_ci or {}).get('crop_start_txt', ''))}"
    if str((_ci or {}).get("hydrus_txt", "") or ""):
        _extra += f"\n* **Parâmetros equivalentes no HYDRUS-1D:** {str((_ci or {}).get('hydrus_txt', ''))}"
    if _extra:
        _rep = f"{_rep}\n{_extra}"
    return _rep
