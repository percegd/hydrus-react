"""Partição do ET potencial na superfície.

O padrão reproduz o preenchimento típico do GUI do HYDRUS-1D:
rRoot = Kc·ET0 e rSoil = 0 quando há cultura (solo nu: rSoil = ET0).
Kc dual FAO-56, solo nu após a colheita e raiz crescente são opt-in.
"""

from hydrus_core import crop as _crop_mod


def potential_partition_cm(
    crop,
    et0_mm: float,
    *,
    use_dual_kc: bool = False,
    sched=None,
    day_index: int = 0,
    bare_after_harvest: bool = False,
) -> tuple:
    """Potenciais (Tp, Ep) em cm/dia — a mesma regra do passo do solver."""
    et0 = max(0.0, float(et0_mm))
    if crop is None:
        return 0.0, et0 / 10.0
    kc = max(0.0, float(getattr(crop, "kc", 0.0) or 0.0))
    if not use_dual_kc:
        return kc * et0 / 10.0, 0.0
    try:
        n = int(len(sched.get("kcb", []))) if isinstance(sched, dict) else 0
    except (TypeError, ValueError):
        n = 0
    if n <= 0:
        kcb = max(0.15, kc - 0.05)
        try:
            hh = float(getattr(crop, "height_m", None) or 1.0)
        except (TypeError, ValueError):
            hh = 1.0
        _fw, _km, ke = _crop_mod._dual_ke_few(kcb, hh)
        return kcb * et0 / 10.0, min(1.0, max(0.0, float(ke))) * et0 / 10.0
    i = max(0, min(int(day_index), n - 1))
    he = sched.get("hydrus_equiv") or {}
    try:
        tmin = float(he.get("tRMin") or 0.0)
    except (TypeError, ValueError):
        tmin = 0.0
    try:
        tharv = he.get("tRHarv")
        tharv = float(tharv) if tharv is not None else None
    except (TypeError, ValueError):
        tharv = None
    before = float(i) + 1e-9 < tmin
    after = tharv is not None and float(i) + 1e-9 >= tharv
    if before or (after and bare_after_harvest):
        return 0.0, et0 / 10.0
    try:
        active = bool(sched["active"][i])
    except Exception:
        active = True
    if after or not active:
        if bare_after_harvest:
            return 0.0, et0 / 10.0
        return kc * et0 / 10.0, 0.0
    try:
        kcb = float(sched["kcb"][i])
    except Exception:
        kcb = max(0.15, kc - 0.05)
    try:
        ke = float(sched["ke_max"][i])
    except Exception:
        try:
            hh = float(getattr(crop, "height_m", None) or 1.0)
        except (TypeError, ValueError):
            hh = 1.0
        _fw, _km, ke = _crop_mod._dual_ke_few(kcb, hh)
    return kcb * et0 / 10.0, min(1.0, max(0.0, float(ke))) * et0 / 10.0


def schedule_et_varies(sched, use_dual_kc: bool) -> bool:
    """True quando o Kcb do ciclo não é constante."""
    if not use_dual_kc or not isinstance(sched, dict):
        return False
    try:
        kcb = [float(v) for v in sched.get("kcb", [])]
    except (TypeError, ValueError):
        return False
    if len(kcb) < 2:
        return False
    return max(kcb) - min(kcb) > 1e-6
