"""
Crop Database and Root Water/Nutrient Uptake Module (Feddes et al. 1978).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np

@dataclass
class CropParameters:
    name: str
    stage: str
    root_depth_cm: float    # Profundidade efetiva do sistema radicular [cm]
    kc: float               # Coeficiente de cultivo
    h1: float = -10.0       # Ponto de anaerobiose [cm]
    h2: float = -25.0       # Limiar de aeração ótima [cm]
    h3: float = -500.0      # Limiar de início de estresse hídrico [cm]
    h4: float = -8000.0     # Ponto de murcha permanente [cm]
    # Ciclo FAO-56 e demanda (opcionais; None = sem ciclo/sem teto, comportamento antigo)
    cycle_key: Optional[str] = None  # cultura-mãe do ciclo (estádios herdam)
    stage_lengths_days: Optional[Tuple[float, float, float, float]] = None  # Lini, Ldev, Lmid, Llate
    kcb_ini: Optional[float] = None
    kcb_mid: Optional[float] = None
    kcb_end: Optional[float] = None
    height_m: Optional[float] = None  # altura média (FAO-56 Tab. 12)
    perennial: bool = False
    root_depth_min_cm: Optional[float] = None  # raiz no plantio (cresce até root_depth_cm)
    stage_offset_days: float = 0.0  # dias desde o plantio p/ entradas de estádio fixo / modo coluna
    uptake_demand_kg_ha: Optional[Dict[str, float]] = None  # demanda total por ciclo (kg/ha elemento)

# Limiares de Feddes por cultura/estádio (faixas de Feddes et al. 1978 /
# Wesseling 1991; h3 varia com a demanda evaporativa e o estádio).
# h4 (murcha) e h1 (anaerobiose) diferem por tolerância da cultura:
# hortaliças sensíveis murcham cedo (~-5000), grãos ~-8000, cana/café
# toleram até ~-12000/-15000. Valores iniciais por classe — calibre localmente
# (todos editáveis na UI, passo 1, seção Cultura).
#
# Ciclo e Kcb dual (FAO-56, Allen et al. 1998: Tab. 11 durações, Tab. 17 Kcb,
# Tab. 12 Kc/altura). Demandas em kg/ha de elemento por ciclo (ordem de
# grandeza, calibre localmente): milho 9 t/ha (Coelho & França, Embrapa Milho e
# Sorgo; Raij et al. 1997 Bol. 100 IAC); soja 3,5 t/ha (Embrapa Soja; N solo 30%
# do total 290 via absorção, resto FBN Hungria et al. 2001); cana 100 t/ha
# (Orlando Filho 1983; Malavolta 2006); café adulto ~30 sc/ha + vegetação anual
# (Malavolta 1993; Matiello et al. 2010); tomate ~80 t/ha (Raij et al. 1997;
# Alvarenga 2013). Marcha de absorção sigmoidal (Karlen et al. 1988; Bender et
# al. 2013 milho; Bender et al. 2015 soja; Malavolta 2006).
CROP_DATABASE = {
    "milho": CropParameters(
        name="Milho",
        stage="Desenvolvimento",
        root_depth_cm=40.0,
        kc=1.05,
        h1=-15.0,
        h2=-30.0,
        h3=-450.0,
        h4=-8000.0,
        cycle_key="milho",
        stage_lengths_days=(20.0, 35.0, 40.0, 30.0),  # 125 d, trópicos úmidos (FAO-56 Tab. 11)
        kcb_ini=0.15, kcb_mid=1.15, kcb_end=0.50,  # FAO-56 Tab. 17
        height_m=2.0,  # FAO-56 Tab. 12
        perennial=False,
        root_depth_min_cm=15.0,
        stage_offset_days=45.0,
        uptake_demand_kg_ha={"N": 200.0, "P": 40.0, "K": 160.0, "Ca": 35.0, "Mg": 30.0, "S": 22.0},
    ),
    "soja": CropParameters(
        name="Soja",
        stage="Desenvolvimento",
        root_depth_cm=35.0,
        kc=1.0,
        h1=-15.0,
        h2=-30.0,
        h3=-450.0,
        h4=-12000.0,
        cycle_key="soja",
        stage_lengths_days=(20.0, 25.0, 60.0, 25.0),  # 130 d; FAO-56 Tab. 11 adapt. cultivares BR ~120-130 d (Embrapa Soja)
        kcb_ini=0.15, kcb_mid=1.10, kcb_end=0.30,
        height_m=0.8,
        perennial=False,
        root_depth_min_cm=10.0,
        stage_offset_days=45.0,
        uptake_demand_kg_ha={"N": 87.0, "P": 23.0, "K": 110.0, "Ca": 43.0, "Mg": 23.0, "S": 54.0},
    ),
    "milho_inicial": CropParameters(
        name="Milho (Estágio Vegetativo Inicial - V3/V4)",
        stage="V3/V4",
        root_depth_cm=25.0,
        kc=0.5,
        h1=-15.0,
        h2=-30.0,
        h3=-400.0,
        h4=-8000.0,
        cycle_key="milho",  # herda ciclo do milho
        stage_lengths_days=(20.0, 35.0, 40.0, 30.0),
        kcb_ini=0.15, kcb_mid=1.15, kcb_end=0.50,
        height_m=2.0,
        perennial=False,
        root_depth_min_cm=15.0,
        stage_offset_days=12.0,
        uptake_demand_kg_ha={"N": 200.0, "P": 40.0, "K": 160.0, "Ca": 35.0, "Mg": 30.0, "S": 22.0},
    ),
    "milho_desenvolvimento": CropParameters(
        name="Milho (Desenvolvimento / Florescimento - V8/VT)",
        stage="V8/VT",
        root_depth_cm=60.0,
        kc=1.2,
        h1=-15.0,
        h2=-30.0,
        h3=-500.0,
        h4=-8000.0,
        cycle_key="milho",
        stage_lengths_days=(20.0, 35.0, 40.0, 30.0),
        kcb_ini=0.15, kcb_mid=1.15, kcb_end=0.50,
        height_m=2.0,
        perennial=False,
        root_depth_min_cm=15.0,
        stage_offset_days=50.0,
        uptake_demand_kg_ha={"N": 200.0, "P": 40.0, "K": 160.0, "Ca": 35.0, "Mg": 30.0, "S": 22.0},
    ),
    "soja_inicial": CropParameters(
        name="Soja (V2/V3)",
        stage="V2/V3",
        root_depth_cm=20.0,
        kc=0.4,
        h1=-15.0,
        h2=-30.0,
        h3=-400.0,
        h4=-12000.0,
        cycle_key="soja",
        stage_lengths_days=(20.0, 25.0, 60.0, 25.0),
        kcb_ini=0.15, kcb_mid=1.10, kcb_end=0.30,
        height_m=0.8,
        perennial=False,
        root_depth_min_cm=10.0,
        stage_offset_days=15.0,
        uptake_demand_kg_ha={"N": 87.0, "P": 23.0, "K": 110.0, "Ca": 43.0, "Mg": 23.0, "S": 54.0},
    ),
    "soja_desenvolvimento": CropParameters(
        name="Soja (R1/R5 - Enchimento)",
        stage="R1/R5",
        root_depth_cm=50.0,
        kc=1.15,
        h1=-15.0,
        h2=-30.0,
        h3=-500.0,
        h4=-12000.0,
        cycle_key="soja",
        stage_lengths_days=(20.0, 25.0, 60.0, 25.0),
        kcb_ini=0.15, kcb_mid=1.10, kcb_end=0.30,
        height_m=0.8,
        perennial=False,
        root_depth_min_cm=10.0,
        stage_offset_days=70.0,
        uptake_demand_kg_ha={"N": 87.0, "P": 23.0, "K": 110.0, "Ca": 43.0, "Mg": 23.0, "S": 54.0},
    ),
    "cana_de_acucar": CropParameters(
        name="Cana-de-açúcar (Cana-planta ou soca estabelecida)",
        stage="Pleno vigor",
        root_depth_cm=80.0,
        kc=1.25,
        h1=-15.0,
        h2=-30.0,
        h3=-600.0,
        h4=-15000.0,
        cycle_key="cana_de_acucar",
        stage_lengths_days=(30.0, 50.0, 225.0, 60.0),  # 365 d; cana-soca FAO-56 Tab. 11 ajust. 12 meses
        kcb_ini=0.15, kcb_mid=1.20, kcb_end=0.70,
        height_m=3.0,
        perennial=False,  # ciclo anual da soca (reinicia a cada 365 d)
        root_depth_min_cm=20.0,
        stage_offset_days=120.0,
        uptake_demand_kg_ha={"N": 140.0, "P": 20.0, "K": 170.0, "Ca": 85.0, "Mg": 45.0, "S": 40.0},
    ),
    "cafe": CropParameters(
        name="Café Adulto",
        stage="Produção",
        root_depth_cm=70.0,
        kc=0.95,
        h1=-15.0,
        h2=-30.0,
        h3=-600.0,
        h4=-12000.0,
        cycle_key="cafe",
        stage_lengths_days=None,  # perene: sem estádios, Kcb constante
        kcb_ini=0.90, kcb_mid=0.90, kcb_end=0.90,  # FAO-56 Tab. 17 café sem cobertura 0,85-0,90
        height_m=2.5,
        perennial=True,
        root_depth_min_cm=70.0,  # raiz fixa
        stage_offset_days=0.0,
        uptake_demand_kg_ha={"N": 150.0, "P": 12.0, "K": 150.0, "Ca": 40.0, "Mg": 20.0, "S": 15.0},
    ),
    "hortalicas": CropParameters(
        name="Hortaliças / Olerícolas (Alface/Tomate)",
        stage="Desenvolvimento",
        root_depth_cm=25.0,
        kc=1.05,
        h1=-10.0,
        h2=-20.0,
        h3=-300.0,
        h4=-5000.0,
        cycle_key="hortalicas",
        stage_lengths_days=(30.0, 40.0, 40.0, 25.0),  # 135 d; tomate ref. FAO-56 Tab. 11
        kcb_ini=0.15, kcb_mid=1.10, kcb_end=0.70,
        height_m=0.6,
        perennial=False,
        root_depth_min_cm=10.0,
        stage_offset_days=30.0,
        uptake_demand_kg_ha={"N": 200.0, "P": 30.0, "K": 330.0, "Ca": 120.0, "Mg": 30.0, "S": 40.0},
    )
}


def _logistic_f(tau: float, L: float) -> float:
    """Fração acumulada logística normalizada F(tau) em [0,1] (marcha sigmoidal)."""
    if L <= 0:
        return 0.0
    if tau <= 0:
        return 0.0
    if tau >= L:
        return 1.0
    import math as _m
    f0 = 1.0 / (1.0 + _m.exp(0.5 / 0.1))
    fL = 1.0 / (1.0 + _m.exp(-0.5 / 0.1))
    f = 1.0 / (1.0 + _m.exp(-(tau - 0.5 * L) / (0.1 * L)))
    denom = max(fL - f0, 1e-12)
    return float(np.clip((f - f0) / denom, 0.0, 1.0))


def _kcb_from_stage(tau: float, Lini: float, Ldev: float, Lmid: float, Llate: float,
                    kcb_ini: float, kcb_mid: float, kcb_end: float) -> float:
    """Kcb por estádio: cte ini, linear até mid em dev, cte mid, linear até end em late (FAO-56 Cap. 6 eq. 66)."""
    if tau < 0:
        return float(kcb_ini)
    if tau < Lini:
        return float(kcb_ini)
    if tau < Lini + Ldev:
        frac = (tau - Lini) / max(Ldev, 1e-12)
        return float(kcb_ini + frac * (kcb_mid - kcb_ini))
    if tau < Lini + Ldev + Lmid:
        return float(kcb_mid)
    if tau < Lini + Ldev + Lmid + Llate:
        frac = (tau - Lini - Ldev - Lmid) / max(Llate, 1e-12)
        return float(kcb_mid + frac * (kcb_end - kcb_mid))
    return float(kcb_end)


def _dual_ke_few(kcb: float, height_m: float):
    """Ke máximo e few do Kc dual (FAO-56 Cap. 7 eq. 72/76, sem correção climática)."""
    kc_max = max(1.2, float(kcb) + 0.05)
    if float(kcb) <= 0.15:
        fc = 0.0
    else:
        denom = max(kc_max - 0.15, 1e-12)
        fc = ((float(kcb) - 0.15) / denom) ** (1.0 + 0.5 * float(height_m))
        fc = float(np.clip(fc, 0.0, 0.99))
    few = 1.0 - fc
    ke = min(kc_max - float(kcb), few * kc_max)
    ke = float(np.clip(ke, 0.0, 1.0))  # teto 1,0 p/ continuidade com solo nu (Ep=ET0)
    return few, kc_max, ke


def _resolve_cycle(crop: CropParameters) -> CropParameters:
    """Devolve a definição do ciclo (cultura-mãe via cycle_key, senão a própria)."""
    try:
        key = (crop.cycle_key or "").strip() if crop.cycle_key else ""
    except Exception:
        key = ""
    if key and key in CROP_DATABASE:
        return CROP_DATABASE[key]
    return crop


def _verhulst_root(tau: float, L0: float, Lm: float, r: float) -> float:
    """Raiz Verhulst-Pearl (HYDRUS-1D eq. 2.21-2.22): L(tau)=Lm*f_r, f_r=L0/(L0+(Lm-L0)e^{-r tau}).

    TODO: distribuição vertical Hoffman & van Genuchten (1983) eq. 2.17 — hoje
    usamos a triangular `root_distribution` (máximo na superfície, 0 na base).
    """
    import math as _m
    if Lm <= 0:
        return 0.0
    if tau <= 0:
        return float(L0)
    try:
        _e = _m.exp(-float(r) * float(tau))
    except OverflowError:
        _e = 0.0
    _den = float(L0) + (float(Lm) - float(L0)) * _e
    if _den <= 1e-12:
        return float(Lm)
    return float(float(Lm) * float(L0) / _den)


def _r_logistic_iRFak1(L0: float, Lm: float, L: float) -> float:
    """r pelo critério iRFak=1: 50% de (Lm+L0) no meio do ciclo.

    Com Lm*f_r(L/2)=(Lm+L0)/2 e f_r=L0/(L0+(Lm-L0)e^{-r L/2)}:
    e^{-r L/2}=L0/(Lm+L0) => r=ln((Lm+L0)/L0)/(L/2).
    """
    import math as _m
    if L <= 0 or L0 <= 0 or Lm <= L0:
        return 0.0
    return float(_m.log((float(Lm) + float(L0)) / float(L0)) / (float(L) / 2.0))


def _r_logistic_iRFak0(L0: float, Lm: float, tau0: float, x: float):
    """r calibrado pelo ponto medido (iRFak=0): curva passa por x em tau0.

    x=Lm*L0/(L0+(Lm-L0)e^{-r tau0}) => e^{-r tau0}=L0*(Lm-x)/(x*(Lm-L0))
    => r=-ln(L0*(Lm-x)/(x*(Lm-L0)))/tau0.
    Retorna None quando o ponto é inválido (x>=Lm, x<=L0, tau0<=0) — o
    chamador cai para linear/constante (documentado).
    """
    import math as _m
    try:
        _t = float(tau0)
        _x = float(x)
    except (TypeError, ValueError):
        return None
    if _t <= 0 or not (float(L0) < _x < float(Lm)):
        return None
    try:
        _arg = float(L0) * (float(Lm) - _x) / (max(_x, 1e-12) * max(float(Lm) - float(L0), 1e-12))
    except ZeroDivisionError:
        return None
    if _arg <= 0:
        return None
    return float(-_m.log(_arg) / _t)


def crop_schedule(crop: CropParameters, n_days: int, planting_day: float = 0.0, *,
                  mode: str = "planting", after_harvest: str = "bare",
                  root_growth: str = "linear", measured_root_cm=None,
                  stage_lengths=None, kcb=None):
    """Agenda diária do ciclo (FAO-56 como pré-processador de Tp/Ep; HYDRUS-1D §10 p.146).

    ``planting_day`` é RELATIVO ao índice 0 da simulação e pode ser NEGATIVO:
    cultura estabelecida com idade DAP => ``planting_day = -DAP`` (tau no dia 0
    = DAP). Equivale a ``tRMin < 0`` no HYDRUS-1D (Tab. 12.4 Block D).

    Modos:
    - ``planting``: inativo (solo nu) antes do plantio; após a colheita
      (tau >= L): ``after_harvest="bare"`` => solo nu; ``"repeat"`` => novo
      ciclo (tau mod L, raiz reinicia em root_min; fração acumula ciclos) —
      equivalente a tRPeriod.
    - ``established``: igual ao planting com ``planting_day=-DAP``.
    - ``perennial``: sempre ativo, Kcb=kcb_mid constante, raiz fixa
      (=root_depth_cm ou measured), uptake_frac_cum linear = dias/365
      (demanda anual espalhada). Equivalente HYDRUS: lRoot=.false.

    Crescimento radicular:
    - ``linear`` (FAO-56 cap. 8): root_min→root_max até o fim de Ldev.
    - ``logistic``: Verhulst-Pearl eq. 2.21-2.22 com L0=root_min, Lm=root_max.

    ``measured_root_cm`` (raiz atual medida, só faz sentido em established;
    ignorado em planting): linear => raiz=measured no dia 0 e cresce
    linearmente até root_max no fim de Ldev (se ainda antes do fim), senão
    constante = measured; logistic => iRFak=0 (r calibrado do ponto conhecido).
    """
    import numpy as _np
    import math as _m
    n = max(int(n_days), 0)
    try:
        pd = float(planting_day)
    except (TypeError, ValueError):
        pd = 0.0
    _mode = str(mode or "planting").strip().lower()
    if _mode not in ("planting", "established", "perennial"):
        _mode = "planting"
    _ah = str(after_harvest or "bare").strip().lower()
    if _ah not in ("bare", "repeat"):
        _ah = "bare"
    _rg = str(root_growth or "linear").strip().lower()
    if _rg not in ("linear", "logistic"):
        _rg = "linear"
    cyc = _resolve_cycle(crop)
    _lengths = None
    if stage_lengths is not None:
        try:
            _lengths = tuple(float(v) for v in stage_lengths)
        except (TypeError, ValueError):
            _lengths = None
    if not _lengths or len(_lengths) != 4:
        _lengths = cyc.stage_lengths_days
    lengths = _lengths
    _kcb_ov = None
    if kcb is not None:
        try:
            _kcb_ov = tuple(float(v) for v in kcb)
            if len(_kcb_ov) != 3:
                _kcb_ov = None
        except (TypeError, ValueError):
            _kcb_ov = None
    if _kcb_ov is not None:
        kcb_ini, kcb_mid, kcb_end = _kcb_ov
    else:
        kcb_ini = cyc.kcb_ini if cyc.kcb_ini is not None else crop.kcb_ini
        kcb_mid = cyc.kcb_mid if cyc.kcb_mid is not None else crop.kcb_mid
        kcb_end = cyc.kcb_end if cyc.kcb_end is not None else crop.kcb_end
        if kcb_ini is None:
            kcb_ini = max(0.15, float(crop.kc) - 0.05)
        if kcb_mid is None:
            kcb_mid = max(0.15, float(crop.kc) - 0.05)
        if kcb_end is None:
            kcb_end = float(kcb_mid)
    # Altura (custom sem dado: 1,0 m neutro)
    h = cyc.height_m if getattr(cyc, "height_m", None) is not None else crop.height_m
    if h is None:
        try:
            h = float(crop.height_m) if crop.height_m is not None else 1.0
        except (TypeError, ValueError):
            h = 1.0
    h = float(h)
    # Raiz: máx = valor do banco/override (crop atual); mín do ciclo
    try:
        root_max = float(crop.root_depth_cm)
    except (TypeError, ValueError):
        root_max = 40.0
    rmin = crop.root_depth_min_cm if crop.root_depth_min_cm is not None else getattr(cyc, "root_depth_min_cm", None)
    try:
        root_min = float(rmin) if rmin is not None else float(root_max)
    except (TypeError, ValueError):
        root_min = float(root_max)
    root_min = min(root_min, root_max)
    _meas = None
    if _mode in ("established", "perennial"):
        try:
            _meas = float(measured_root_cm) if measured_root_cm is not None else None
        except (TypeError, ValueError):
            _meas = None
        if _meas is not None and not (_meas > 0):
            _meas = None

    active = _np.zeros(n, dtype=bool)
    kcb = _np.zeros(n, dtype=float)
    few = _np.ones(n, dtype=float)
    kc_max = _np.full(n, 1.2, dtype=float)
    ke_max = _np.ones(n, dtype=float)
    root = _np.full(n, float(root_max), dtype=float)
    frac = _np.zeros(n, dtype=float)
    stage = ["fora do ciclo"] * n

    def _set_dual(i, _kval, _act):
        try:
            _fw, _km, _ke = _dual_ke_few(float(_kval) if _act else 0.0, h)
        except Exception:
            _fw, _km, _ke = 1.0, 1.2, 1.0
        few[i], kc_max[i], ke_max[i] = _fw, _km, _ke

    _is_perennial_mode = (_mode == "perennial") or bool(getattr(cyc, "perennial", False) or getattr(crop, "perennial", False))
    if _mode == "planting" and bool(getattr(cyc, "perennial", False)) and lengths is None:
        _is_perennial_mode = True
    if _is_perennial_mode:
        _r_fix = float(_meas) if _meas is not None else float(root_max)
        for i in range(n):
            active[i] = True
            kcb[i] = float(kcb_mid)
            _set_dual(i, float(kcb[i]), True)
            root[i] = float(_r_fix)
            frac[i] = float(i) / 365.0
            stage[i] = "perene"
        _hyd = {"lRoot": False, "iRootIn": None, "tRMin": float(pd),
                "tRHarv": None, "xRMin": float(_r_fix), "xRMax": float(_r_fix),
                "iRFak": None, "tRMed": None, "xRMed": None, "tRPeriod": None, "r": None}
        return {"active": active, "kcb": kcb, "few": few, "kc_max": kc_max,
                "ke_max": ke_max, "root_depth_cm": root, "uptake_frac_cum": frac,
                "stage": stage, "hydrus_equiv": _hyd}

    if not lengths or len(lengths) != 4:
        # Custom/sem dados: sem ciclo (cte) e sem teto (fração zerada; solver não limita sem demanda)
        base_kcb = max(0.15, float(crop.kc) - 0.05)
        for i in range(n):
            active[i] = True
            kcb[i] = float(base_kcb)
            _set_dual(i, float(kcb[i]), True)
            root[i] = float(root_max)
            frac[i] = 0.0
            stage[i] = "fora do ciclo"
        _hyd = {"lRoot": False, "iRootIn": None, "tRMin": float(pd),
                "tRHarv": None, "xRMin": float(root_min), "xRMax": float(root_max),
                "iRFak": None, "tRMed": None, "xRMed": None, "tRPeriod": None, "r": None}
        return {"active": active, "kcb": kcb, "few": few, "kc_max": kc_max,
                "ke_max": ke_max, "root_depth_cm": root, "uptake_frac_cum": frac,
                "stage": stage, "hydrus_equiv": _hyd}

    Lini, Ldev, Lmid, Llate = (float(v) for v in lengths)
    L = float(Lini + Ldev + Lmid + Llate)
    _r_val = None
    _iRFak = 1
    if _rg == "logistic":
        if _meas is not None and _mode == "established":
            _tau0 = max(0.0, -float(pd))
            _r_val = _r_logistic_iRFak0(float(root_min), float(root_max), _tau0, float(_meas))
            _iRFak = 0 if _r_val is not None else 0
            if _r_val is None:
                _r_val = None
            else:
                _iRFak = 0
        else:
            _r_val = _r_logistic_iRFak1(float(root_min), float(root_max), float(L))
            _iRFak = 1
    _tau0_lin = max(0.0, -float(pd)) if _mode == "established" else 0.0
    _lin_has_ramp = False
    _lin_slope = 0.0
    if _rg == "linear" and _meas is not None and _mode == "established":
        _t_end_grow = float(Lini + Ldev)
        if _tau0_lin < _t_end_grow and float(root_max) > float(_meas):
            _den = max(_t_end_grow - _tau0_lin, 1e-12)
            _lin_slope = (float(root_max) - float(_meas)) / _den
            _lin_has_ramp = True

    def _root_at(tau_v):
        if _rg == "logistic" and _r_val is not None:
            return float(_verhulst_root(float(tau_v), float(root_min), float(root_max), float(_r_val)))
        if _lin_has_ramp:
            if float(tau_v) <= _tau0_lin:
                return float(_meas)
            if float(tau_v) >= float(Lini + Ldev):
                return float(root_max)
            return float(float(_meas) + (float(tau_v) - _tau0_lin) * _lin_slope)
        if _meas is not None and _mode == "established" and _rg == "linear" and not _lin_has_ramp:
            return float(_meas)
        if float(tau_v) <= 0:
            return float(root_min)
        if float(tau_v) >= float(Lini + Ldev):
            return float(root_max)
        froot = float(tau_v) / max(float(Lini + Ldev), 1e-12)
        return float(float(root_min) + froot * (float(root_max) - float(root_min)))

    def _stage_name(tau_v, _tin_v=None):
        _t = float(_tin_v) if _tin_v is not None else float(tau_v)
        if _t < 0 or _t >= L:
            return "fora do ciclo"
        if _t < Lini:
            return "inicial"
        if _t < Lini + Ldev:
            return "desenvolvimento"
        if _t < Lini + Ldev + Lmid:
            return "médio"
        return "final"

    _is_cane = (getattr(cyc, "cycle_key", "") == "cana_de_acucar") or (getattr(crop, "cycle_key", "") == "cana_de_acucar")
    _repeat = (_ah == "repeat") or bool(_is_cane)
    for i in range(n):
        tau = float(i) - pd
        if tau < 0:
            active[i] = False
            kcb[i] = 0.0
            root[i] = float(root_min)
            frac[i] = 0.0
            _set_dual(i, 0.0, False)
            stage[i] = "fora do ciclo"
            continue
        if _repeat:
            ncyc = int(tau // L) if L > 0 else 0
            tin = tau - ncyc * L
            active[i] = True
            kcb[i] = _kcb_from_stage(tin, Lini, Ldev, Lmid, Llate, kcb_ini, kcb_mid, kcb_end)
            root[i] = float(_root_at(tin))
            frac[i] = float(ncyc) + _logistic_f(tin, L)
            _set_dual(i, float(kcb[i]), True)
            stage[i] = _stage_name(tau, tin)
            continue
        if tau >= L:
            active[i] = False  # após a colheita = solo nu
            kcb[i] = 0.0
            root[i] = float(root_max)
            frac[i] = 1.0
            _set_dual(i, 0.0, False)
            stage[i] = "fora do ciclo"
            continue
        active[i] = True
        kcb[i] = _kcb_from_stage(tau, Lini, Ldev, Lmid, Llate, kcb_ini, kcb_mid, kcb_end)
        root[i] = float(_root_at(tau))
        frac[i] = _logistic_f(tau, L)
        _set_dual(i, float(kcb[i]), True)
        stage[i] = _stage_name(tau)
    if _rg == "logistic" and _r_val is not None:
        _iRootIn = 2
        if _iRFak == 0:
            _tRMed, _xRMed = float(_tau0_lin), float(_meas)
        else:
            _tRMed, _xRMed = float(L) / 2.0, (float(root_max) + float(root_min)) / 2.0
        _r_out = float(_r_val)
    else:
        _iRootIn = 1
        _tRMed, _xRMed, _r_out = None, None, None
    _hyd = {"lRoot": True, "iRootIn": _iRootIn, "tRMin": float(pd),
            "tRHarv": (float(pd) + float(L)) if L > 0 else None,
            "xRMin": float(root_min), "xRMax": float(root_max),
            "iRFak": int(_iRFak) if _rg == "logistic" else 1,
            "tRMed": _tRMed, "xRMed": _xRMed,
            "tRPeriod": (float(L) if _repeat else None), "r": _r_out}
    return {"active": active, "kcb": kcb, "few": few, "kc_max": kc_max,
            "ke_max": ke_max, "root_depth_cm": root, "uptake_frac_cum": frac,
            "stage": stage, "hydrus_equiv": _hyd}

def feddes_water_stress(h: np.ndarray, crop: CropParameters) -> np.ndarray:
    """
    Computes Feddes water stress response function alpha(h) in [0, 1].
    h is negative pressure head [cm].
    """
    alpha = np.zeros_like(h, dtype=float)
    
    # 1. Anaerobiosis (h > h1): alpha = 0
    # 2. Optimal aeration transition (h1 >= h > h2)
    idx2 = (h <= crop.h1) & (h > crop.h2)
    if np.any(idx2):
        alpha[idx2] = (h[idx2] - crop.h1) / (crop.h2 - crop.h1)
        
    # 3. Optimal water uptake (h2 >= h > h3): alpha = 1
    idx3 = (h <= crop.h2) & (h >= crop.h3)
    alpha[idx3] = 1.0
    
    # 4. Water stress reduction (h3 > h > h4)
    idx4 = (h < crop.h3) & (h > crop.h4)
    if np.any(idx4):
        alpha[idx4] = (h[idx4] - crop.h4) / (crop.h3 - crop.h4)
        
    # 5. Wilting point (h <= h4): alpha = 0
    return np.clip(alpha, 0.0, 1.0)

def root_distribution(z: np.ndarray, root_depth_cm: float) -> np.ndarray:
    """
    Normalized root distribution b(z) such that integral b(z) dz = 1 over root zone.
    z is depth positive downwards [cm].
    Linear decreasing distribution: maximum at surface, 0 at root_depth_cm.
    TODO: distribuição Hoffman & van Genuchten (1983) eq. 2.17 como alternativa
    (não trocar o default triangular atual sem validação).

    Note: The analytical integral of the continuous triangular function equals 1,
    but discrete grid sampling introduces a small overestimate (~1-5% depending on
    grid resolution). We re-normalise after sampling to ensure mass conservation.
    """
    bz = np.maximum(0.0, 2.0 * (1.0 - z / root_depth_cm) / root_depth_cm)
    bz[z > root_depth_cm] = 0.0
    # Re-normalize so that sum(bz * dz) = 1 for any grid spacing
    if len(z) > 1:
        dz_approx = z[1] - z[0]
        integral = np.sum(bz) * dz_approx
        if integral > 0.0:
            bz = bz / integral
    return bz
