"""
Numerical Simulation Engine: 1D Mass-Conservative Richards Equation (Celia et al., 1990)
and 1D Advection-Dispersion Solute Transport (Šimůnek et al. / HYDRUS physics).
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any, Union
import numpy as np
from scipy import linalg

from hydrus_core.soil_physics import (
    SoilParameters,
    water_content_from_h,
    matric_head_from_theta,
    hydraulic_conductivity,
    specific_moisture_capacity
)
from hydrus_core.crop import CropParameters, feddes_water_stress, root_distribution
from hydrus_core import crop as _crop_mod

@dataclass
class SimulationConfig:
    depth_cm: float = 100.0         # Profundidade total do perfil [cm]
    dz: float = 1.0                 # Espaçamento de malha [cm]
    total_days: float = 7.0         # Duração total da simulação [dias]
    target_depth_cm: float = 30.0   # Profundidade da camada de avaliação / interesse agronômico [cm]
    dt_init: float = 0.001          # Passo de tempo inicial [dias]
    dt_min: float = 1e-5            # Passo de tempo minimo [dias] (1e-6 travava eventos em argiloso)
    dt_max: float = 0.05            # Passo de tempo maximo [dias]
    max_picard_iter: int = 25       # Máximo de iterações de Picard
    picard_tol: float = 0.001       # Tolerância de convergência em h [cm]
    picard_omega: float = 0.9       # Passo inicial do line search de Newton (w <= omega)
                                    # Estabiliza a frente de molhamento em solos de
                                    # retencao ingreme (argilosos, n~1.18)
    obs_depths_cm: List[float] = field(default_factory=lambda: [10.0, 20.0, 30.0, 50.0]) # Profundidades de observação temporal [cm]

    def __post_init__(self):
        # F3: domínio com teto sensato (1 cm .. 500 cm). Sem teto, malha
        # gigante estoura memória/tempo; sem piso, nz degenera (nz=1).
        try:
            _d = float(self.depth_cm)
        except (TypeError, ValueError):
            raise ValueError(f"Profundidade do perfil (depth_cm) deve ser numérica (recebido: {self.depth_cm!r}).")
        if not (1.0 <= _d <= 500.0):
            raise ValueError(
                f"Profundidade do perfil (depth_cm={_d}) fora de [1, 500] cm — "
                "fisicamente impossível / malha inviável.")
        try:
            _dz = float(self.dz)
        except (TypeError, ValueError):
            raise ValueError(f"Espaçamento de malha (dz) deve ser numérico (recebido: {self.dz!r}).")
        if not (0.05 <= _dz <= 50.0):
            raise ValueError(f"Espaçamento de malha (dz={_dz}) fora de [0.05, 50] cm.")
        try:
            _t = float(self.total_days)
        except (TypeError, ValueError):
            raise ValueError(f"Duração do ensaio (total_days) deve ser numérica (recebido: {self.total_days!r}).")
        if not (_t > 0.0):
            raise ValueError(f"Duração do ensaio (total_days={_t}) deve ser > 0 dias.")

@dataclass
class SimulationResults:
    z: np.ndarray                   # Vetor de profundidades [cm]
    times_days: List[float]         # Tempos registrados [dias]
    theta_profiles: List[np.ndarray]# Perfis de umidade volumétrica [cm3/cm3]
    h_profiles: List[np.ndarray]    # Perfis de potencial matricial [cm]
    n_profiles: List[np.ndarray]    # Perfis de concentração de Nitrato (mg N / cm3 de solo)
    q_bottom_cum_cm: float          # Drenagem profunda acumulada no fundo [cm]
    n_leached_mg_cm2: float         # Nitrogênio lixiviado abaixo do perfil [mg/cm2]
    n_below_root_mg_cm2: float      # Nitrogênio abaixo da profundidade da raiz [mg/cm2]
    n_in_root_zone_mg_cm2: float    # Nitrogênio disponível na zona radicular [mg/cm2]
    n_total_applied_mg_cm2: float   # Nitrogênio total aplicado [mg/cm2]
    leaching_ratio_pct: float       # Porcentagem de perda por lixiviação além da raiz [%]
    peak_depth_cm: float            # Profundidade do pico de concentração [cm]
    nutrient_results: Dict[str, dict] = field(default_factory=dict) # Resultados detalhados por nutriente (multi-nutriente)
    target_depth_cm: float = 30.0   # Camada de avaliação agronômica [cm]
    runoff_cum_cm: float = 0.0      # Escoamento superficial acumulado (excedente de Ks) [cm]
    obs_depths_cm: List[float] = field(default_factory=list) # Profundidades monitoradas [cm]
    obs_times_days: List[float] = field(default_factory=list) # Tempos das séries temporais [dias]
    obs_theta_series: Dict[float, List[float]] = field(default_factory=dict) # depth -> [theta(t)]
    obs_c_series: Dict[str, Dict[float, List[float]]] = field(default_factory=dict) # sym -> depth -> [C_aq(t) em mg/L]
    print_profiles: Dict[float, Dict[str, Any]] = field(default_factory=dict) # dia -> {"theta","h","c_total":{sym:arr}}
    # Balanço de massa no perfil (fronteira = fundo do domínio)
    retained_profile_pct: float = 0.0   # % da dose que permanece no perfil [%]
    leached_bottom_pct: float = 0.0     # % da dose que atravessou o fundo do domínio [%]
    uptaken_pct: float = 0.0            # % da dose absorvida pela cultura (raiz) [%]
    mass_closure_pct: float = 0.0       # R2: fechamento (perfil+lixiviado+absorvido)/(aplicado+residual)*100-100 [%]
    mass_closure: float = 0.0           # R2: alias de mass_closure_pct (erro relativo de massa [%])
    converged: bool = True              # False se algum passo foi aceito sem convergência (fallback dt_min)
    non_converged_steps: int = 0        # nº de passos aceitos sem convergência no piso de dt
    evap_cum_cm: float = 0.0            # F1: evaporação acumulada do solo [cm]
    transp_cum_cm: float = 0.0          # F1: transpiração acumulada da cultura (sink Feddes) [cm]
    water_closure_cm: float = 0.0       # F1: resíduo hídrico P-(dS+D+RO+E+T) [cm] (dV)
    water_closure_pct: float = 0.0      # F1: resíduo hídrico relativo a P [%] (0 se P=0)

class Hydrus1DSimulator:
    """
    Simulador 1D para fluxo de água e transporte de Nitrogênio (Nitrato / Ureia).
    """
    def __init__(self, soil: SoilParameters, crop: Optional[CropParameters] = None, config: Optional[SimulationConfig] = None):
        self.soil = soil
        self.crop = crop
        self.cfg = config or SimulationConfig()
        self.config = self.cfg
        
        # Grid spatial discretization
        self.nz = int(self.cfg.depth_cm / self.cfg.dz) + 1
        self.z = np.linspace(0.0, self.cfg.depth_cm, self.nz)
        self.dz = self.cfg.dz
        
        # Root distribution
        if self.crop:
            self.root_b = root_distribution(self.z, self.crop.root_depth_cm)
        else:
            self.root_b = np.zeros(self.nz)

    def run(
        self,
        initial_moisture_pct: float,      # Umidade inicial como % da capacidade de campo (~0.3 a 0.8)
        fertilizer_dose_kg_ha: float,     # Dose de Nitrogênio ou Nutriente [kg/ha]
        water_events: List[Tuple[float, float, float]], # Lista de tuplas: (tempo_inicio_dia, duracao_dia, lamina_mm)
        et0_mm_day: float = 4.0,          # Evapotranspiração de referência diária [mm/dia]
        dispersivity_cm: float = 5.0,     # Dispersividade longitudinal [cm]
        kd: float = 0.0,                  # Coeficiente de adsorção linear [cm3/g]
        release_type: str = "immediate",  # "immediate" / "convencional" ou "controlled" / "liberacao_controlada"
        release_days: float = 60.0,       # Duração da liberação [dias] para liberação controlada
        nutrients: Optional[List[Dict[str, Any]]] = None, # Lista opcional de nutrientes para simulação simultânea
        placement_mode: str = "surface",  # "surface" (0-2cm), "furrow" (5-10cm) ou "custom"
        z_app_top_cm: float = 0.0,        # Profundidade superior de aplicação [cm] (para custom)
        z_app_bottom_cm: float = 2.0,     # Profundidade inferior de aplicação [cm] (para custom)
        initial_residual_mg_dm3: Union[float, Dict[str, float]] = 0.0, # Teor residual inicial no perfil (0-20 cm) [mg/dm3]
        fertigation_c0_mg_l: float = 0.0, # Concentração de entrada na água de fertirrigação [mg/L] (Concentration Flux BC)
        fertigation_pulse_days: float = 0.0, # Duração do pulso de fertirrigação [dias] (0 = todo o evento)
        obs_depths_cm: Optional[List[float]] = None, # Profundidades para séries temporais C(t) e θ(t) [cm]
        application_day: float = 0.0,     # Dia do ano da aplicação do adubo [dias] (0 = início)
        evap_cm_day: Optional[float] = None, # Evaporação potencial do solo [cm/dia]; None => partição de ET0
        transpiration_mm_day: Optional[float] = None, # Transpiração potencial [mm/dia]; None => ET0·Kc (exige cultura)
        print_days: Optional[List[float]] = None, # Dias de leitura (perfis completos) [dias]
        water_only: bool = False,          # True => roda apenas fluxo de água (sem transporte de soluto)
        crop_schedule: Optional[dict] = None,  # agenda diária do ciclo (crop.crop_schedule); None = modo coluna
        uptake_cap: bool = True            # True => limita absorção acumulada à demanda da cultura
    ) -> SimulationResults:
        """
        Executa a simulação transiente acoplada de fluxo hídrico (Richards 1D)
        e transporte de solutos multi-nutriente com suporte a posicionamento de adubo
        (superfície, sulco, fertirrigação contínua ou profundidade customizada),
        teor residual inicial de solo, padrões de liberação e monitoramento temporal
        em nós de observação (Breakthrough Curves).

        F2: kd/dispersividade com None ou texto geram ValueError claro (sem
        TypeError cru). Regra documentada: item de `nutrients` com
        kd/dispersividade None herda o escalar da chamada (`kd` /
        `dispersivity_cm`); escalar None também é erro claro.
        F5: `print_days` com dia além de `total_days` (ou < 0) levanta
        ValueError — sem clamp silencioso para o perfil final.
        """
        # --- F2/F5: validação dura de entrada do solver direto (sem UI) ---
        def _req_float(val: Any, fname: str, ctx: str) -> float:
            if val is None or (isinstance(val, bool)):
                raise ValueError(
                    f"{ctx}: '{fname}' não pode ser None/bool (recebido: {val!r}). "
                    f"Informe {fname} numérico ou omita o parâmetro.")
            try:
                import math as _m
                f = float(val)
            except (TypeError, ValueError):
                raise ValueError(
                    f"{ctx}: '{fname}' deve ser numérico (recebido: {val!r}).")
            try:
                import math as _m2
                if _m2.isnan(f) or _m2.isinf(f):
                    raise ValueError(
                        f"{ctx}: '{fname}' não pode ser NaN/inf (recebido: {val!r}).")
            except ValueError:
                raise
            except Exception:
                pass
            return f

        # Escalares de transporte (F2): erro claro em vez de TypeError:float(None).
        if kd is None:
            raise ValueError("Hydrus1DSimulator.run: 'kd' não pode ser None. "
                             "Informe kd numérico >= 0 (ex.: 0.0) ou omita o parâmetro.")
        if dispersivity_cm is None:
            raise ValueError("Hydrus1DSimulator.run: 'dispersivity_cm' não pode ser None. "
                             "Informe dispersividade numérica >= 0 (ex.: 5.0) ou omita o parâmetro.")
        try:
            _kd_scalar = float(kd)
        except (TypeError, ValueError):
            raise ValueError(f"Hydrus1DSimulator.run: 'kd' deve ser numérico (recebido: {kd!r}).")
        try:
            _disp_scalar = float(dispersivity_cm)
        except (TypeError, ValueError):
            raise ValueError(f"Hydrus1DSimulator.run: 'dispersivity_cm' deve ser numérico (recebido: {dispersivity_cm!r}).")
        if _kd_scalar < 0:
            raise ValueError(f"Hydrus1DSimulator.run: 'kd' ({_kd_scalar}) não pode ser negativo.")
        if _disp_scalar < 0:
            raise ValueError(f"Hydrus1DSimulator.run: 'dispersivity_cm' ({_disp_scalar}) não pode ser negativa.")
        # F5: snapshot além da duração — erro bloqueante (UI já bloqueia; o
        # solver direto não pode fazer clamp silencioso para o perfil final).
        if print_days:
            for _pd in print_days:
                try:
                    _pf = float(_pd)
                except (TypeError, ValueError):
                    raise ValueError(
                        f"Hydrus1DSimulator.run: dia de leitura (print_days) inválido: {_pd!r}. "
                        "Use números em (0, total_days].")
                if not (0.0 < _pf <= float(self.cfg.total_days) + 1e-9):
                    raise ValueError(
                        f"Hydrus1DSimulator.run: dia de leitura {_pf} fora da duração "
                        f"do ensaio ({float(self.cfg.total_days)} dias). "
                        "Use dias em (0, total_days].")
        z = self.z
        nz = self.nz
        dz = self.dz
        dt = self.cfg.dt_init
        # R3: constantes da definicao UNICA de theta(h) = VG(h) + eps*softplus(h)
        # (regularizacao overly-bulk; detalhe junto ao residuo de Richards).
        # Definidas aqui no topo para que deteccao de frente, residuo,
        # theta reportado e transporte usem a MESMA fonte.
        _eps_sat = 2e-2   # [cm3/cm3]/cm
        _sig_band = 1.0   # [cm]
        
        # 1. Condição Inicial de Umidade
        # Estimar capacidade de campo (h ~ -150 cm)
        h_fc = -150.0
        theta_fc = float(water_content_from_h(np.array([h_fc]), self.soil)[0])
        # Umidade inicial escalonada entre o limiar residual (solo seco) e a capacidade de campo
        # (0..100%; 100% = capacidade de campo). Iniciar em CC é a prática usual sem medição
        # (Šimůnek et al. 2008 manual HYDRUS-1D; aquecimento/spin-up como alternativa).
        th_min = self.soil.theta_r + 0.01
        frac = np.clip(initial_moisture_pct / 100.0, 0.0, 1.0)
        theta_val = th_min + max(0.005, theta_fc - th_min) * frac
        theta_init = np.full(nz, np.clip(theta_val, th_min, self.soil.theta_s - 0.02))
        h = matric_head_from_theta(theta_init, self.soil)
        # F1: armazenamento inicial na MESMA definição _theta do passo
        # (VG + eps*softplus), para que S0/S1 do fechamento sejam consistentes.
        # Em h inicial seco o termo eps é ~0 (sem efeito prático).
        theta = (water_content_from_h(h, self.soil) + _eps_sat * _sig_band
                 * (np.maximum(h / _sig_band, 0.0)
                    + np.log1p(np.exp(-np.abs(h / _sig_band)))))
        
        # 2. Configuração dos Nutrientes e Condições Iniciais
        # 1 kg/ha = 0.1 g/m2 = 0.01 mg/cm2
        active_nutrients = []
        if water_only:
            # Modo "somente água": nenhum soluto é transportado (só Richards + ET)
            pass
        elif nutrients and len(nutrients) > 0:
            for n_item in nutrients:
                sym = str(n_item.get("symbol", "N"))
                name = str(n_item.get("name", sym))
                # F2: None herda o escalar da chamada (default documentado);
                # texto/lixo gera ValueError claro com o símbolo (sem TypeError).
                try:
                    dose = float(n_item.get("dose_kg_ha", fertilizer_dose_kg_ha))
                except (TypeError, ValueError):
                    raise ValueError(
                        f"Soluto '{sym}': 'dose_kg_ha' deve ser numérica "
                        f"(recebido: {n_item.get('dose_kg_ha')!r}).")
                _kd_raw = n_item.get("kd", kd)
                if _kd_raw is None:
                    _kd_raw = _kd_scalar  # default documentado: herda escalar
                try:
                    n_kd = float(_kd_raw)
                except (TypeError, ValueError):
                    raise ValueError(
                        f"Soluto '{sym}': 'kd' deve ser numérico >= 0 "
                        f"(recebido: {n_item.get('kd')!r}).")
                if n_kd < 0:
                    raise ValueError(f"Soluto '{sym}': 'kd' ({n_kd}) não pode ser negativo.")
                _disp_raw = n_item.get("dispersivity_cm", dispersivity_cm)
                if _disp_raw is None:
                    _disp_raw = _disp_scalar  # default documentado: herda escalar
                try:
                    n_disp = float(_disp_raw)
                except (TypeError, ValueError):
                    raise ValueError(
                        f"Soluto '{sym}': 'dispersivity_cm' deve ser numérica >= 0 "
                        f"(recebido: {n_item.get('dispersivity_cm')!r}).")
                if n_disp < 0:
                    raise ValueError(
                        f"Soluto '{sym}': 'dispersivity_cm' ({n_disp}) não pode ser negativa.")
                n_rel_type = str(n_item.get("release_type", release_type)).lower()
                n_rel_days = float(n_item.get("release_days", release_days))
                n_c0 = float(n_item.get("fertigation_c0_mg_l", fertigation_c0_mg_l))
                n_pulse = float(n_item.get("fertigation_pulse_days", fertigation_pulse_days))
                active_nutrients.append({
                    "symbol": sym,
                    "name": name,
                    "dose_kg_ha": dose,
                    "kd": n_kd,
                    "dispersivity_cm": n_disp,
                    "release_type": n_rel_type,
                    "release_days": max(1.0, n_rel_days),
                    "applied_mg_cm2": dose * 0.01,
                    "released_mg_cm2": 0.0,
                    "residual_mg_cm2": 0.0,  # R2: massa do teor residual inicial (fora da dose)
                    "sorption": str(n_item.get("sorption", n_item.get("isotherm", "linear"))).lower(),  # P-Langmuir opt-in: "langmuir"
                    "smax_mg_g": float(n_item.get("smax_mg_g", n_item.get("Smax", 0.0)) or 0.0),
                    "kl_cm3_mg": float(n_item.get("kl_cm3_mg", n_item.get("KL", n_item.get("K", 0.0))) or 0.0),
                    "c_prof": np.zeros(nz),
                    "leached_bottom": 0.0,
                    "uptaken_mg_cm2": 0.0,
                    "recorded_profiles": [],
                    "placement_mode": n_item.get("placement_mode", placement_mode),
                    "z_app_top_cm": n_item.get("z_app_top_cm", z_app_top_cm),
                    "z_app_bottom_cm": n_item.get("z_app_bottom_cm", z_app_bottom_cm),
                    "initial_residual_mg_dm3": n_item.get("initial_residual_mg_dm3", None),
                    "fertigation_c0_mg_l": n_c0,
                    "fertigation_pulse_days": n_pulse
                })
        else:
            # Compatibilidade retroativa (API/testes): sem lista de nutrientes,
            # roda um único soluto "N" com os parâmetros escalares informados.
            # (Escalares None já barrados acima com ValueError claro.)
            active_nutrients.append({
                "symbol": "N",
                "name": "Nutriente Principal",
                "dose_kg_ha": float(fertilizer_dose_kg_ha),
                "kd": float(_kd_scalar),
                "dispersivity_cm": float(_disp_scalar),
                "release_type": str(release_type).lower(),
                "release_days": max(1.0, float(release_days)),
                "applied_mg_cm2": float(fertilizer_dose_kg_ha) * 0.01,
                "released_mg_cm2": 0.0,
                "residual_mg_cm2": 0.0,  # R2: massa do teor residual inicial (fora da dose)
                "sorption": "linear",  # P-Langmuir opt-in fica na lista `nutrients`
                "smax_mg_g": 0.0,
                "kl_cm3_mg": 0.0,
                "c_prof": np.zeros(nz),
                "leached_bottom": 0.0,
                "uptaken_mg_cm2": 0.0,
                "recorded_profiles": [],
                "placement_mode": placement_mode,
                "z_app_top_cm": z_app_top_cm,
                "z_app_bottom_cm": z_app_bottom_cm,
                "initial_residual_mg_dm3": None,
                "fertigation_c0_mg_l": float(fertigation_c0_mg_l),
                "fertigation_pulse_days": float(fertigation_pulse_days)
            })

        def _inject_dose(n_item):
            """Injeta a dose aplicada nos nós da camada de aplicação (imediata/pulso CRF)."""
            app_vol = n_item["app_layer_vol"]
            is_fert = (str(n_item["placement_mode"]).lower() == "fertigation" or n_item.get("fertigation_c0_mg_l", 0.0) > 0)
            if is_fert:
                # Fertirrigação: adubo entra dissolvido na água de irrigação ao longo do tempo (Concentration Flux BC)
                n_item["applied_mg_cm2"] = 0.0
                n_item["released_mg_cm2"] = 0.0
            elif n_item["release_type"] in ["immediate", "convencional"]:
                # Convencional: 100% da massa solubiliza de imediato na camada de aplicação
                init_m = n_item["applied_mg_cm2"]
                n_item["c_prof"][n_item["app_nodes"]] += init_m / app_vol
                n_item["released_mg_cm2"] = init_m
            else:
                # Liberação Controlada / Lenta: pulso inicial de contato (2% da dose)
                init_pulse = n_item["applied_mg_cm2"] * 0.02
                n_item["c_prof"][n_item["app_nodes"]] += init_pulse / app_vol
                n_item["released_mg_cm2"] = init_pulse

        # Inicialização da concentração no solo com teor residual e posicionamento do adubo
        for n_item in active_nutrients:
            # 2.1 Mapeamento da profundidade e identificação de nós
            n_pm = str(n_item["placement_mode"]).lower().strip()
            if n_pm == "furrow":
                z_top = 5.0
                z_bot = 10.0
            elif n_pm == "custom":
                z_top = min(float(n_item["z_app_top_cm"]), float(n_item["z_app_bottom_cm"]))
                z_bot = max(float(n_item["z_app_top_cm"]), float(n_item["z_app_bottom_cm"]))
            else: # "surface" ou default
                z_top = 0.0
                z_bot = 2.0

            node_mask = (z >= (z_top - 1e-6)) & (z <= (z_bot + 1e-6))
            app_nodes = np.where(node_mask)[0]
            if len(app_nodes) == 0:
                z_mid = 0.5 * (z_top + z_bot)
                app_nodes = np.sort(np.argsort(np.abs(z - z_mid))[:2])

            n_item["app_nodes"] = app_nodes
            n_item["app_layer_vol"] = len(app_nodes) * dz
            n_item["placement_mode"] = n_pm
            n_item["z_app_top_cm"] = z_top
            n_item["z_app_bottom_cm"] = z_bot

            # 2.2 Teor residual basal nos primeiros 20 cm do perfil
            sym = n_item["symbol"]
            item_res = n_item.get("initial_residual_mg_dm3")
            if item_res is not None:
                res_val = float(item_res)
            elif isinstance(initial_residual_mg_dm3, dict):
                res_val = float(initial_residual_mg_dm3.get(sym, initial_residual_mg_dm3.get(n_item["name"], initial_residual_mg_dm3.get("default", 0.0))))
            else:
                try:
                    res_val = float(initial_residual_mg_dm3)
                except (ValueError, TypeError):
                    res_val = 0.0

            n_item["initial_residual_mg_dm3"] = res_val
            if res_val > 0.0:
                res_conc_mg_cm3 = res_val * 0.001 # 1 mg/dm3 = 0.001 mg/cm3
                residual_mask = z <= (20.0 + 1e-6)
                n_item["c_prof"][residual_mask] += res_conc_mg_cm3
                # R2: contabiliza a massa residual na MESMA convenção do balanço
                # final (soma c*dz), para que mass_closure inclua aplicado+residual.
                n_item["residual_mg_cm2"] = float(res_conc_mg_cm3 * np.count_nonzero(residual_mask) * dz)
            else:
                n_item["residual_mg_cm2"] = 0.0

            # 2.3 Injeção da dose inicial aplicada (ou diferida para o dia de aplicação)
            if application_day <= 0.0:
                _inject_dose(n_item)
                n_item["pending_inject"] = False
            else:
                n_item["pending_inject"] = True
            n_item["recorded_profiles"].append(n_item["c_prof"].copy())

        # Configurar nós de observação temporal (análogo ao HYDRUS-1D Obs_Node)
        if obs_depths_cm is not None and len(obs_depths_cm) > 0:
            target_obs = [float(d) for d in obs_depths_cm if 0.0 <= float(d) <= self.cfg.depth_cm]
        else:
            target_obs = [float(d) for d in getattr(self.cfg, "obs_depths_cm", [10.0, 20.0, 30.0, 50.0]) if 0.0 <= float(d) <= self.cfg.depth_cm]
        if not target_obs:
            target_obs = [min(10.0, self.cfg.depth_cm), min(30.0, self.cfg.depth_cm), self.cfg.depth_cm]

        obs_node_map = {}
        for d in sorted(list(set(target_obs))):
            idx = int(np.clip(round(d / dz), 0, nz - 1))
            obs_node_map[float(z[idx])] = idx

        obs_times = [0.0]
        obs_theta = {d: [float(theta[idx])] for d, idx in obs_node_map.items()}
        for _ni in active_nutrients:
            _ni["kd_eff"] = _ni["kd"]
        obs_c = {n_item["symbol"]: {d: [float(n_item["c_prof"][idx] / max(theta[idx] + self.soil.bulk_density * max(0.0, float(np.asarray(n_item["kd_eff"])[idx]) if np.ndim(n_item["kd_eff"]) else float(n_item["kd_eff"])), 1e-4) * 1000.0)] for d, idx in obs_node_map.items()} for n_item in active_nutrients}
        next_obs_save = 0.0
        obs_save_dt = max(self.cfg.total_days / 120.0, 1e-4)

        # Variáveis acumuladoras do fluxo hídrico
        t = 0.0
        q_bottom_cum = 0.0
        runoff_cum = 0.0  # Escoamento superficial acumulado [cm]
        evap_cum = 0.0    # F1: evaporação real acumulada [cm]
        transp_cum = 0.0  # F1: transpiração real acumulada (sink Feddes) [cm]
        non_converged_steps = 0  # R1: passos aceitos sem convergência (fallback dt_min)

        # F1: fronteiras de evento hídrico (início/fim de cada chuva).
        # Sem snap, o passo atravessa a borda e aplica a taxa do início
        # para o dt inteiro (ou perde o início): erro sistemático ~dt*q
        # que cresce com P (ex.: 2,4 mm em 60 mm, 4% de P, com ET0=0).
        _evt_bounds = set()
        for _ev in (water_events or []):
            try:
                _s, _d, _m = float(_ev[0]), float(_ev[1]), float(_ev[2])
            except (TypeError, ValueError, IndexError):
                continue
            if _d > 0:
                if 0.0 < _s < float(self.cfg.total_days):
                    _evt_bounds.add(float(_s))
                _e = _s + _d
                if 0.0 < _e < float(self.cfg.total_days):
                    _evt_bounds.add(float(_e))
        _evt_bounds = sorted(_evt_bounds)
        
        recorded_times = [0.0]
        recorded_theta = [theta.copy()]
        recorded_h = [h.copy()]

        # Perfis completos em dias de leitura escolhidos pelo usuário (print times do HYDRUS)
        print_days_list = sorted(float(d) for d in (print_days or []) if float(d) > 0.0)
        print_profiles: Dict[float, Dict[str, Any]] = {}
        _pd_idx = 0

        save_interval = max(0.5, self.cfg.total_days / 10.0)
        next_save = save_interval
        
        # Constante de difusão molecular em água [cm2/dia]
        d_diff = 1.0

        # --- P9: agenda do ciclo (Kc dual + raiz variável + teto de absorção) ---
        # crop_schedule: dict de arrays diários (active, kcb, few/ke, root_depth_cm,
        # uptake_frac_cum) gerado por hydrus_core.crop.crop_schedule.
        _sched = crop_schedule if isinstance(crop_schedule, dict) else None
        _sched_n = 0
        if _sched is not None:
            try:
                _sched_n = int(len(_sched.get("kcb", [])))
            except Exception:
                _sched_n = 0
                _sched = None
        # Demanda total por nutriente (kg/ha elemento; ordem de grandeza, calibre localmente)
        _demand_kg_ha: Dict[str, float] = {}
        if self.crop is not None and getattr(self.crop, "uptake_demand_kg_ha", None):
            try:
                for _k, _v in dict(getattr(self.crop, "uptake_demand_kg_ha") or {}).items():
                    _demand_kg_ha[str(_k)] = float(_v)
            except Exception:
                _demand_kg_ha = {}
            # Estádios herdam a demanda da mãe via cycle_key
            if not _demand_kg_ha:
                try:
                    _cyc = _crop_mod._resolve_cycle(self.crop)
                    for _k, _v in dict(getattr(_cyc, "uptake_demand_kg_ha", None) or {}).items():
                        _demand_kg_ha[str(_k)] = float(_v)
                except Exception:
                    pass
        # Ciclo-mãe p/ teto sem schedule (modo coluna): F(offset+t)-F(offset)
        _col_cycle = None
        _col_L = 0.0
        _col_perennial = False
        _col_offset = 0.0
        if self.crop is not None:
            try:
                _col_cycle = _crop_mod._resolve_cycle(self.crop)
                _ll = getattr(_col_cycle, "stage_lengths_days", None)
                if _ll and len(_ll) == 4:
                    _col_L = float(sum(float(v) for v in _ll))
                _col_perennial = bool(getattr(_col_cycle, "perennial", False))
                _col_offset = float(getattr(self.crop, "stage_offset_days", 0.0) or 0.0)
            except Exception:
                _col_cycle, _col_L, _col_perennial, _col_offset = None, 0.0, False, 0.0
        # Teto acumulado por nutriente (mg/cm2) + flag de corte
        for _ni in active_nutrients:
            _ni["uptake_capped"] = False
            _ni["uptake_cap_mg_cm2"] = None
            _sym0 = str(_ni.get("symbol", ""))
            _dem = _demand_kg_ha.get(_sym0, None)
            if uptake_cap and _dem is not None and _dem > 0:
                if _sched is not None and _sched_n > 0:
                    try:
                        _fr = _sched.get("uptake_frac_cum", None)
                        _fr_end = float(_fr[min(_sched_n - 1, max(int(self.cfg.total_days), 0))]) if _fr is not None else 0.0
                    except Exception:
                        _fr_end = 0.0
                    _ni["uptake_cap_mg_cm2"] = float(_dem) * 0.01 * max(0.0, _fr_end)
                elif _col_cycle is not None and (_col_L > 0 or _col_perennial):
                    if _col_perennial:
                        _fend = max(0.0, float(self.cfg.total_days)) / 365.0
                    else:
                        _fend = _crop_mod._logistic_f(_col_offset + float(self.cfg.total_days), _col_L) - _crop_mod._logistic_f(_col_offset, _col_L)
                    _ni["uptake_cap_mg_cm2"] = float(_dem) * 0.01 * max(0.0, _fend)
        _last_root_day = -1
        _root_max_for_mask = float(self.crop.root_depth_cm) if self.crop else float(getattr(self.config, "target_depth_cm", 30.0))
        if _sched is not None and _sched_n > 0:
            try:
                import numpy as _np2
                _root_max_for_mask = float(_np2.max(_np2.asarray(_sched.get("root_depth_cm", [_root_max_for_mask]), dtype=float)))
            except Exception:
                pass

        # Loop Temporal
        while t < self.cfg.total_days:
            if t + dt > self.cfg.total_days:
                dt = self.cfg.total_days - t
            # F1: snap às fronteiras de evento (com epsilon p/ FP).
            # Garante que nenhum passo cruze início/fim de chuva.
            if _evt_bounds:
                _t_next = None
                for _b in _evt_bounds:
                    if _b > t + 1e-9:
                        _t_next = _b
                        break
                if _t_next is not None and t + dt > _t_next:
                    dt = max(_t_next - t, self.cfg.dt_min * 0.1)
                
            # Determinar taxa de infiltração superficial (chuva/irrigação) no tempo t [cm/dia]
            surface_flux_cm_day = 0.0
            for start_day, duration_day, mm in water_events:
                if start_day <= t < (start_day + duration_day):
                    # mm/dia convertidos para cm/dia
                    surface_flux_cm_day += (mm / 10.0) / duration_day

            # Chaveamento fluxo -> carga na superficie (analogico ao "Atmospheric BC
            # with Surface Water Layer" do HYDRUS): se a agua aplicada excede a
            # condutividade hidraulica saturada (Ks), a superficie encharca e o
            # excedente vira escoamento superficial (runoff) em vez de infiltrar.
            infil_rate_cm_day = min(surface_flux_cm_day, self.soil.ks)

            # Limita dt ao tempo de preenchimento da celula seca mais proxima da
            # superficie (frente de molhamento): com Neumann intenso sobre perfil
            # seco, a raiz do sistema implicito fica muito longe do chute e o
            # metodo de passo grande gastava 25 iteracoes sem convergir.
            if infil_rate_cm_day > 0.0:
                th_now = water_content_from_h(h, self.soil) + _eps_sat * _sig_band * (np.maximum(h / _sig_band, 0.0) + np.log1p(np.exp(-np.abs(h / _sig_band))))
                front = np.flatnonzero(th_now < self.soil.theta_s - 0.01)
                if front.size:
                    iw = int(front[0])
                    deficit = max(self.soil.theta_s - float(th_now[iw]), 0.01)
                    dV_w = dz * (0.5 if iw == 0 else 1.0)
                    dt = min(dt, max(0.5 * dV_w * deficit / infil_rate_cm_day,
                                     self.cfg.dt_min))
            
            # ET0 do dia (aceita escalar ou série diária)
            if np.ndim(et0_mm_day) == 0:
                et0_today_mm = float(et0_mm_day)
            else:
                _et0_arr = np.asarray(et0_mm_day, dtype=float).ravel()
                et0_today_mm = float(_et0_arr[min(int(t), _et0_arr.size - 1)])

            # Demanda hídrica: Kc dual FAO-56 Cap. 7 (Allen et al. 1998).
            # Tp = Kcb·ET0 (x ativo); Ep = Ke·ET0, Ke = min(Kcmax-Kcb, few·Kcmax),
            # Kcmax = max(1,2; Kcb+0,05) (eq. 72, sem correção climática),
            # few = 1-fc, fc = ((Kcb-0,15)/(Kcmax-0,15))^(1+0,5h) (eq. 76, clip 0..0,99).
            # Ke ≤ 1 p/ continuidade com solo nu (Ep=ET0). A redução por secagem (Kr)
            # já é feita fisicamente pelo limitador hCritA da superfície (como no
            # HYDRUS-1D, Šimůnek et al. 2008) — ver max_evap abaixo. Fora do ciclo:
            # Tp=0, Ep=ET0. Sem schedule (coluna): Kcb = max(0,15; kc-0,05)
            # (Kcb mid ≈ Kc mid − 0,05) e height_m da cultura (custom: 1,0 m).
            _sched_idx = min(int(t), _sched_n - 1) if (_sched is not None and _sched_n > 0) else None
            _sched_active = True
            if self.crop is not None:
                if _sched is not None and _sched_idx is not None:
                    try:
                        _sched_active = bool(_sched["active"][_sched_idx])
                        _kcb_day = float(_sched["kcb"][_sched_idx])
                    except Exception:
                        _sched_active, _kcb_day = True, max(0.15, float(self.crop.kc) - 0.05)
                    # Raiz variável: recalcula root_b no máx. 1x por dia
                    try:
                        _rday = float(_sched["root_depth_cm"][_sched_idx])
                        if int(t) != _last_root_day and _rday > 0:
                            self.root_b = root_distribution(self.z, _rday)
                            _last_root_day = int(t)
                    except Exception:
                        pass
                    if not _sched_active:
                        _tp_pot = 0.0
                        _ke_day = 1.0
                        _ep_pot = float(et0_today_mm) / 10.0
                    else:
                        try:
                            _ke_day = float(_sched["ke_max"][_sched_idx])
                        except Exception:
                            _fw0, _km0, _ke0 = _crop_mod._dual_ke_few(_kcb_day, float(getattr(self.crop, "height_m", 1.0) or 1.0))
                            _ke_day = _ke0
                        _tp_pot = _kcb_day * float(et0_today_mm) / 10.0
                        _ep_pot = min(1.0, max(0.0, _ke_day)) * float(et0_today_mm) / 10.0
                else:
                    _kcb_day = max(0.15, float(self.crop.kc) - 0.05)
                    try:
                        _hh = float(getattr(self.crop, "height_m", None) or 1.0)
                    except (TypeError, ValueError):
                        _hh = 1.0
                    _fw0, _km0, _ke0 = _crop_mod._dual_ke_few(_kcb_day, _hh)
                    _tp_pot = _kcb_day * float(et0_today_mm) / 10.0
                    _ep_pot = min(1.0, max(0.0, _ke0)) * float(et0_today_mm) / 10.0
            else:
                _tp_pot = 0.0
                _ep_pot = float(et0_today_mm) / 10.0
            # Explícitos continuam sobrepondo (mesma semântica)
            if transpiration_mm_day is not None:
                transpiration_demand_cm_day = max(0.0, float(transpiration_mm_day)) / 10.0
            else:
                transpiration_demand_cm_day = float(_tp_pot) if self.crop else 0.0
            # Evaporação do solo: explícita (evap_cm_day) ou partição dual (E = Ke·ET0)
            if evap_cm_day is not None:
                evap_pot_cm_day = max(0.0, float(evap_cm_day))
            else:
                evap_pot_cm_day = float(_ep_pot) if self.crop else max(0.0, float(et0_today_mm) / 10.0 - transpiration_demand_cm_day)
            if evap_pot_cm_day > 0.0:
                k0_surf = hydraulic_conductivity(np.array([h[0]]), self.soil)[0]
                max_evap = max(0.0, ((h[1] - (-10000.0)) / dz) * k0_surf)
                evap_act_cm_day = min(evap_pot_cm_day, max_evap)
            else:
                evap_act_cm_day = 0.0
            # Fluxo líquido no topo (infiltração descendente menos evaporação ascendente)
            net_top_flux_cm_day = infil_rate_cm_day - evap_act_cm_day
            
            # --- 1. RESOLVER EQUACAO DE RICHARDS (Newton-Raphson com line search) ---
            # Newton sobre o MESMO esquema implicito misto de Celia et al. (1990)
            # do Picard (mesma raiz convergida). O Picard puro oscilava na frente
            # de molhamento de solos de retencao ingreme (argilosos, n~1.18):
            # C(h)->0 na saturacao zera a capacidade do no e o dK/dh grande nas
            # faces (salto seco/molhado) desestabiliza o ponto fixo. Aqui:
            #  - residuo F(h) com os mesmos BCs do original (Neumann com gravidade
            #    no topo; drenagem livre de gradiente unitario no fundo);
            #  - Jacobiana tridiagonal analitica incluindo dK/dh nos fluxos de face;
            #  - line search de descida monotona do residuo (substitui o passo
            #    fixo do Picard, que convergia linearmente ou oscilava);
            #  - regularizacao "overly-bulk" (eps_sat): capacidade minima na banda
            #    proxima a h >= 0, pois no sem capacidade torna o sistema singular.
            h_old = h.copy()
            theta_old = theta.copy()
            h_new = h_old.copy()
            
            # R3: definicao UNICA de theta(h) em todo o passo (Richards +
            # transporte + diagnostico). theta(h) = VG(h) + eps_sat*softplus(h):
            # o termo eps e regularizacao "overly-bulk" (capacidade minima na
            # banda |h|~1 cm p/ h>=0, pois C(h)->0 na saturacao singulariza o
            # Jacobiano). Versao anterior somava eps so no residuo (:410) e
            # reportava theta puro VG (:525), criando armazenamento fantasma
            # (mismatch 3.4e-03 cm). Aqui o MESMO _theta alimenta residuo,
            # capacidade, theta reportado, theta_safe do transporte e obs.
            eps_sat = _eps_sat
            sig_band = _sig_band

            def _softplus(hv):
                return sig_band * (np.maximum(hv / sig_band, 0.0)
                                   + np.log1p(np.exp(-np.abs(hv / sig_band))))

            def _sigmoid(hv):
                return 1.0 / (1.0 + np.exp(-np.clip(hv / sig_band, -60.0, 60.0)))
            dV = np.full(nz, dz)
            dV[0] = dz * 0.5
            dV[-1] = dz * 0.5
            
            def _theta(hv):
                # R3: unica fonte de verdade de armazenamento; usada no residuo,
                # no theta reportado e no transporte (theta_safe deriva dela).
                return water_content_from_h(hv, self.soil) + eps_sat * _softplus(hv)

            def _richards_residual(hv, th_old, dt_step, infil_step):
                th = _theta(hv)
                k = hydraulic_conductivity(hv, self.soil)
                if self.crop:
                    s = feddes_water_stress(hv, self.crop) * self.root_b * transpiration_demand_cm_day
                else:
                    s = np.zeros(nz)
                kf = 0.5 * (k[:-1] + k[1:])
                g = 1.0 - (hv[1:] - hv[:-1]) / dz
                q = kf * g
                Fv = dV * (th - th_old) / dt_step + s * dV
                Fv[1:-1] += q[1:] - q[:-1]
                Fv[0] += q[0] - infil_step
                # F1: drenagem livre = K(h_fundo) (gradiente unitário no fundo,
                # q=-K*(dh/dz-1) com dh/dz=0). A forma anterior usava kf[-1]
                # (média das 2 últimas células) no balanço mas reportava a
                # face interna q_faces[-1]=kf[-1]*(1-dh/dz) no acumulado:
                # mismatch sistemático ~k*dh/dz que crescia com P.
                Fv[-1] += k[-1] - q[-1]
                return Fv
            
            def _cap_reg(hv):
                # R3: d(_theta)/dh consistente com o residuo (derivada do softplus = sigmoide).
                return specific_moisture_capacity(hv, self.soil) + eps_sat * _sigmoid(hv)
            
            omega = float(getattr(self.cfg, "picard_omega", 1.0))
            omega = min(max(omega, 0.05), 1.0)
            
            converged = False
            n_picard_it = self.cfg.max_picard_iter
            F = _richards_residual(h_new, theta_old, dt, net_top_flux_cm_day)
            norm_F = float(np.max(np.abs(F)))
            norm_F0 = max(norm_F, 1e-12)
            for it in range(self.cfg.max_picard_iter):
                c = _cap_reg(h_new)
                k = hydraulic_conductivity(h_new, self.soil)
                # dK/dh por diferenca central (K crescente em h; trava p/ >= 0)
                eps_h = 1e-4 * (1.0 + np.abs(h_new))
                kp = (hydraulic_conductivity(h_new + eps_h, self.soil)
                      - hydraulic_conductivity(h_new - eps_h, self.soil)) / (2.0 * eps_h)
                kp = np.maximum(kp, 0.0)
                
                # Fluxos de face e derivadas dq_j/dh_j, dq_j/dh_{j+1}
                k_half = 0.5 * (k[:-1] + k[1:])
                g_fac = 1.0 - (h_new[1:] - h_new[:-1]) / dz
                dq_up = 0.5 * kp[:-1] * g_fac + k_half / dz
                dq_dn = 0.5 * kp[1:] * g_fac - k_half / dz
                
                # Jacobiana tridiagonal (armazenamento em banda)
                J_diag = np.empty(nz)
                J_sup = np.zeros(nz - 1)  # coef. de h_{i+1} na linha i
                J_sub = np.zeros(nz - 1)  # coef. de h_{i-1} na linha i
                J_diag[0] = dV[0] * c[0] / dt + dq_up[0]
                J_sup[0] = dq_dn[0]
                J_diag[1:-1] = dV[1:-1] * c[1:-1] / dt + dq_up[1:] - dq_dn[:-1]
                J_sub[:-1] = -dq_up[:-1]
                J_sup[1:] = dq_dn[1:]  # F_i contem +q_i => +d q_i/d h_{i+1}
                # F1: derivada da drenagem livre K(h[-1]) (não mais kf[-1]):
                # d/dh[-1]=kp[-1] cheia; d/dh[-2]=0 (sem dependência).
                J_diag[-1] = dV[-1] * c[-1] / dt + kp[-1] - dq_dn[-1]
                J_sub[-1] = -dq_up[-1]
                
                ab = np.zeros((3, nz))
                ab[0, 1:] = J_sup
                ab[1, :] = J_diag
                ab[2, :-1] = J_sub
                
                try:
                    delta = linalg.solve_banded((1, 1), ab, -F)
                except linalg.LinAlgError:
                    break  # tratado como nao convergido (dt reduzido)
                if not np.all(np.isfinite(delta)):
                    break
                
                # Line search (Armijo): aceita o maior passo w <= omega que reduz
                # o residuo de forma monotona
                moved = False
                w = omega
                while w >= 0.02:
                    h_try = h_new + w * delta
                    F_try = _richards_residual(h_try, theta_old, dt, net_top_flux_cm_day)
                    if np.all(np.isfinite(F_try)):
                        norm_try = float(np.max(np.abs(F_try)))
                        if norm_try < (1.0 - 1e-4 * w) * norm_F:
                            moved = True
                            break
                    w *= 0.5
                if not moved:
                    break  # sem direcao de descida neste dt: nao convergido
                
                h_new = h_try
                step_max = w * float(np.max(np.abs(delta)))
                F = F_try
                norm_F = norm_try
                n_picard_it = it + 1
                if step_max < self.cfg.picard_tol or norm_F < 1e-2 * norm_F0:
                    # criterio de passo fino OU queda de 100x no residuo da
                    # itacao (fluxo de saida ~ 1% do desbalanceio inicial)
                    converged = True
                    break
            
            # Se nao convergiu, reduz dt e tenta novamente
            stuck_at_floor = False
            if not converged and dt > self.cfg.dt_min:
                dt = max(dt * 0.5, self.cfg.dt_min)
                continue
            if not converged:
                # Fallback no piso de dt: aceita a ultima iterate (residuo minimo
                # do line search) e volta a crescer o passo, evitando travamento.
                # R1: exposto via SimulationResults.converged=False.
                stuck_at_floor = True
                non_converged_steps += 1
            
            # Acumula escoamento APENAS do passo aceito (nunca de tentativas de
            # dt reduzido que foram descartadas por nao-convergencia)
            runoff_cum += (surface_flux_cm_day - infil_rate_cm_day) * dt
                
            # Atualiza variáveis de fluxo
            h = h_new
            # Absorcao radicular no estado atualizada (usada no transporte)
            if self.crop:
                s_root = feddes_water_stress(h, self.crop) * self.root_b * transpiration_demand_cm_day
            else:
                s_root = np.zeros(nz)
            # R3: theta reportado = MESMO _theta do residuo (sem fantasma).
            theta = _theta(h)
            k_prof = hydraulic_conductivity(h, self.soil)
            k_half = 0.5 * (k_prof[:-1] + k_prof[1:])
            
            # Fluxos de Darcy nas faces dos nós [cm/dia] (positivo para baixo)
            dh_dz = (h[1:] - h[:-1]) / dz
            q_faces = k_half * (1.0 - dh_dz)

            # F1: drenagem livre = K(h_fundo) (gradiente unitário), IDÊNTICA
            # ao termo do balanço (Fv[-1] += k[-1]-q[-1]). A forma anterior
            # acumulava a face interna q_faces[-1] aqui mas kf[-1] no
            # resíduo: mismatch sistemático que crescia com P.
            q_bottom = float(k_prof[-1])
            q_bottom_cum += q_bottom * dt
            # F1: ET real acumulada (evaporação superficial + sink Feddes).
            # Sem ela, o fechamento P-(dS+D+RO) carrega E+T como "resíduo"
            # (E aparente cresce com P e dá ~mm mesmo com ET0=0 por erro
            # numérico das bordas — agora com snap + fundo consistente).
            evap_cum += float(evap_act_cm_day) * dt
            if self.crop:
                transp_cum += float(np.sum(s_root * dV)) * dt
            
            theta_safe = np.where(theta < 0.0, 1e-8, theta)
            q_nodes = np.zeros(nz)
            q_nodes[0] = infil_rate_cm_day
            q_nodes[1:-1] = 0.5 * (q_faces[:-1] + q_faces[1:])
            q_nodes[-1] = q_bottom
            v_pore = q_nodes / theta_safe
            q_faces_pos = np.maximum(q_faces, 0.0) / dz
            uptake_rate_base = s_root[1:-1].copy() if self.crop else 0.0
            uptake_0_base = float(s_root[0]) if self.crop else 0.0
            uptake_last_base = float(s_root[-1]) if self.crop else 0.0

            # --- 2. RESOLVER TRANSPORTE DE SOLUTOS PARA CADA NUTRIENTE ---
            for n_item in active_nutrients:
                # 2.0 Injeção diferida no dia de aplicação (usado em séries anuais)
                if n_item.get("pending_inject") and t >= application_day:
                    _inject_dose(n_item)
                    n_item["pending_inject"] = False

                # 2.1 Liberação gradual / controlada no passo de tempo atual
                if n_item["release_type"] not in ["immediate", "convencional"]:
                    rem_m = max(0.0, n_item["applied_mg_cm2"] - n_item["released_mg_cm2"])
                    if rem_m > 0 and t >= application_day and t < (application_day + n_item["release_days"] * 2.0):
                        # Modulação por umidade superficial (Arthur PUB 2840 / Isabela TCC 2024)
                        app_nds = n_item.get("app_nodes", [0])
                        th_top = float(np.mean(theta[app_nds])) if len(app_nds) > 0 else float(theta[0])
                        se_top = np.clip((th_top - self.soil.theta_r) / max(self.soil.theta_s - self.soil.theta_r, 1e-4), 0.05, 1.0)
                        release_rate = (n_item["applied_mg_cm2"] / n_item["release_days"]) * se_top # mg/cm2/dia
                        delta_m = min(rem_m, release_rate * dt)
                        n_item["released_mg_cm2"] += delta_m
                        n_item["c_prof"][n_item["app_nodes"]] += delta_m / n_item["app_layer_vol"]

                # 2.2 Coeficiente de adsorção Kd e capacidade de retenção
                # Linear (default p/ todos, inclusive P). P-Langmuir (Novais &
                # Smyth, 1999) só com sorption="langmuir" no item do nutriente:
                # Kd_secante(C) = Smax*K/(1+K*C) por nó, i.e. S(C)/C da isoterma
                # S(C)=Smax*K*C/(1+K*C); em C->0 recupera o Kd linear
                # (Smax*K ~= Kd da tabela) e em dose alta satura os sitios
                # (Kd cai, mais P em solução). Linearização secante explícita
                # em C_aq_old preserva o mapeamento C_total = ret_cap*C_aq.
                n_kd = n_item["kd"]
                n_disp = n_item["dispersivity_cm"]
                c_old = n_item["c_prof"].copy()

                # Competição catiônica: Ca2+ compete pelos sítios de troca (Gapon/Vanselow)
                # com K+ e Mg2+ em solos com argila (Isabela TCC 2024)
                if n_item["symbol"] in ["K", "Mg"] and n_kd > 0:
                    ca_item = next((it for it in active_nutrients if it["symbol"] == "Ca"), None)
                    if ca_item is not None:
                        ca_ret = theta_safe + self.soil.bulk_density * max(0.0, ca_item["kd"])
                        ca_c_aq = np.maximum(ca_item["c_prof"] / np.maximum(ca_ret, 1e-4), 0.0)
                        clay_pct_val = self.soil.clay_pct if self.soil.clay_pct is not None else 30.0
                        clay_factor = np.clip(clay_pct_val / 35.0, 0.1, 1.5)
                        comp_attenuation = 1.0 / (1.0 + 1.2 * clay_factor * ca_c_aq)
                        kd_eff = n_kd * comp_attenuation
                    else:
                        kd_eff = n_kd
                elif str(n_item.get("sorption", "linear")).lower() == "langmuir" and str(n_item["symbol"]).strip().upper() == "P":
                    from hydrus_core.soil_physics import classify_texture as _ct
                    from hydrus_core.literature_database import get_langmuir_params as _glp
                    _tex = _ct(getattr(self.soil, "sand_pct", None), getattr(self.soil, "clay_pct", None))
                    _smax = float(n_item.get("smax_mg_g", 0.0) or 0.0)
                    _kl = float(n_item.get("kl_cm3_mg", 0.0) or 0.0)
                    if _smax <= 0.0 or _kl <= 0.0:
                        _lp = _glp("P", _tex)  # default textural (Smax*K ~= Kd linear)
                        _smax, _kl = float(_lp.smax_mg_g), float(_lp.kl_cm3_mg)
                    n_item["smax_mg_g"], n_item["kl_cm3_mg"] = _smax, _kl
                    _ret_lin = theta_safe + self.soil.bulk_density * max(0.0, float(n_kd))
                    _c_aq_ref = np.maximum(c_old / np.maximum(_ret_lin, 1e-4), 0.0)
                    kd_eff = (_smax * _kl) / (1.0 + _kl * _c_aq_ref)
                else:
                    kd_eff = n_kd
                # N2: guarda Kd efetivo (com atenuação por competição) para uso nos obs
                n_item["kd_eff"] = kd_eff

                ret_cap = theta_safe + self.soil.bulk_density * np.maximum(0.0, kd_eff)
                c_aq_old = c_old / ret_cap

                # P9: teto de absorção por nutriente (demanda da cultura).
                # Absorção passiva (fluxo de massa, Šimůnek & Hopmans 2009) limitada pela
                # demanda nutricional (Feddes 1978 p/ água; teto nutricional: Raij 1997/Malavolta 2006).
                # Conservativo: U_pot = Σ s_root·c_aq_old·dz·dt; permitido = teto(t+dt)−uptaken;
                # f = min(1, permitido/U_pot). Usa f·s_root na matriz E na acumulação (fecha balanço).
                _f_cap = 1.0
                if self.crop and uptake_cap:
                    _dem_cap = _demand_kg_ha.get(str(n_item.get("symbol", "")), None)
                    if _dem_cap is not None and _dem_cap > 0:
                        try:
                            _dem_mg = float(_dem_cap) * 0.01
                            if _sched is not None and _sched_n > 0:
                                _fr_arr = _sched.get("uptake_frac_cum", None)
                                _idx_end = min(int(t + dt), _sched_n - 1)
                                _fr_end = float(_fr_arr[_idx_end]) if _fr_arr is not None else 0.0
                                _teto_end = _dem_mg * max(0.0, _fr_end)
                            elif _col_cycle is not None and (_col_L > 0 or _col_perennial):
                                if _col_perennial:
                                    # F linear (demanda anual/365 por dia): F(off+t)-F(off) = t/365
                                    _f_end = max(0.0, float(t + dt)) / 365.0
                                else:
                                    _f_end = _crop_mod._logistic_f(_col_offset + float(t + dt), _col_L) - _crop_mod._logistic_f(_col_offset, _col_L)
                                _teto_end = _dem_mg * max(0.0, _f_end)
                            else:
                                _teto_end = None
                            if _teto_end is not None:
                                _upt_sofar = float(n_item.get("uptaken_mg_cm2", 0.0))
                                _permit = max(0.0, float(_teto_end) - _upt_sofar)
                                # U_pot com c_aq_old (explícito conservativo)
                                _upot = float(np.sum(s_root * np.maximum(c_aq_old, 0.0) * dz)) * float(dt)
                                if _upot > 1e-18:
                                    _f_cap = float(np.clip(_permit / _upot, 0.0, 1.0))
                                else:
                                    _f_cap = 1.0
                                if _f_cap < 1.0 - 1e-12:
                                    n_item["uptake_capped"] = True
                        except Exception:
                            _f_cap = 1.0
                _up_rate = (uptake_rate_base * _f_cap) if self.crop else 0.0
                _up_0 = float(uptake_0_base * _f_cap) if self.crop else 0.0
                _up_last = float(uptake_last_base * _f_cap) if self.crop else 0.0

                # Dispersão hidrodinâmica específica
                d_hydro = n_disp * np.abs(v_pore) + d_diff
                d_half = 0.5 * (d_hydro[:-1] + d_hydro[1:])
                theta_half = 0.5 * (theta_safe[:-1] + theta_safe[1:])
                disp_half = (theta_half * d_half) / (dz * dz)

                # Montar matriz tridiagonal
                A_sol = np.zeros(nz - 1)
                B_sol = np.zeros(nz)
                C_sol = np.zeros(nz - 1)
                rhs_sol = (ret_cap * c_aq_old) / dt

                disp_top = disp_half[:-1]
                disp_bot = disp_half[1:]
                # Upwind completo nas duas direcoes:
                # q_faces > 0 => escoamento descendente (de i para i+1)
                # q_faces < 0 => escoamento ascendente (de i+1 para i)
                q_down = np.maximum(q_faces, 0.0) / dz   # coeficiente de saida para baixo / entrada de cima
                q_up   = np.maximum(-q_faces, 0.0) / dz  # coeficiente de saida para cima / entrada de baixo

                A_sol[:-1] = -(disp_top + q_down[:-1])   # c[i-1] entra de cima quando desce
                C_sol[1:]  = -(disp_bot + q_up[1:])      # c[i+1] entra de baixo quando sobe
                B_sol[1:-1] = (ret_cap[1:-1] / dt) + disp_top + disp_bot + q_down[1:] + q_up[:-1] + _up_rate

                # Contorno superior (i = 0)
                d_bot_0 = 0.5 * (d_hydro[0] + d_hydro[1])
                theta_bot_0 = 0.5 * (theta_safe[0] + theta_safe[1])
                disp_bot_0 = (theta_bot_0 * d_bot_0) / (dz * dz)

                B_sol[0] = (ret_cap[0] / dt) + disp_bot_0 + q_down[0] + _up_0
                # Fluxo ascendente no topo (evaporação): o soluto NÃO cruza a superfície,
                # logo o nó 0 apenas recebe o soluto que sobe do nó 1 (sem saída de massa).
                C_sol[0] = -(disp_bot_0 + q_up[0])

                # Influxo contínuo de fertirrigação (Concentration Flux BC)
                is_fert = (str(n_item["placement_mode"]).lower() == "fertigation" or n_item.get("fertigation_c0_mg_l", 0.0) > 0)
                if is_fert and infil_rate_cm_day > 0.0:
                    c0_fert = float(n_item.get("fertigation_c0_mg_l", 0.0))
                    pulse_d = float(n_item.get("fertigation_pulse_days", 0.0))
                    # A fertirrigação só começa a partir do dia da aplicação (app_day);
                    # a duração do pulso é contada a partir desse dia (0 = contínua).
                    _t_since_app = t - application_day
                    if t >= application_day and (pulse_d <= 0.0 or _t_since_app <= pulse_d):
                        c_in_aq = c0_fert * 0.001  # mg/L -> mg/cm3 de água
                        rhs_sol[0] += q_down[0] * c_in_aq
                        dm_fert = q_down[0] * dz * c_in_aq * dt
                        n_item["applied_mg_cm2"] += dm_fert
                        n_item["released_mg_cm2"] += dm_fert

                # Contorno inferior (i = nz - 1)
                d_top_n = 0.5 * (d_hydro[-2] + d_hydro[-1])
                theta_top_n = 0.5 * (theta_safe[-2] + theta_safe[-1])
                disp_top_n = (theta_top_n * d_top_n) / (dz * dz)
                adv_out_n = max(q_bottom, 0.0) / dz

                B_sol[-1] = (ret_cap[-1] / dt) + disp_top_n + adv_out_n + q_up[-1] + float(_up_last if self.crop else 0.0)
                A_sol[-1] = -(disp_top_n + q_down[-1])

                # Resolver sistema de soluto
                ab_sol = np.zeros((3, nz))
                ab_sol[0, 1:] = C_sol
                ab_sol[1, :] = B_sol
                ab_sol[2, :-1] = A_sol

                c_aq_new = linalg.solve_banded((1, 1), ab_sol, rhs_sol)
                # R2-revisao :659: piso fisico de nao-negatividade (C_aq >= 0).
                # Mantido por ser restrição física (concentração negativa não
                # existe), não máscara de balanço como o clip de pct; eventual
                # massa negativada cortada aqui aparece como resíduo no
                # mass_closure (não é zerada em silêncio no pct).
                c_aq_new = np.maximum(0.0, c_aq_new)

                n_item["c_prof"] = c_aq_new * ret_cap
                n_item["leached_bottom"] += q_bottom * c_aq_new[-1] * dt
                # Massa absorvida pela cultura (sink de transpiração) [mg/cm2]
                # N4: inclui o último nó (sem zerar s_root[-1]). R2: peso dz
                # (não dV) — mesma convenção do perfil (soma c*dz) e da matriz
                # do soluto; dV (0.5 nas fronteiras) subcontava a absorção nos
                # nós 0/-1 e vazava massa do fechamento em cenários com uptake
                # forte (até -7% em 7 dias com milho). P9: mesmos termos f·s_root
                # da matriz (balanço fecha; excedente fica no solo).
                if self.crop:
                    uptake_vec = s_root * _f_cap
                    n_item["uptaken_mg_cm2"] += float(np.sum(uptake_vec * c_aq_new * dz)) * dt
            
            # Avanço temporal e adaptação do passo
            t_prev = t
            t += dt
            if dt < self.cfg.dt_max:
                if stuck_at_floor:
                    # recupera o passo de tempo apos aceitar solucao relaxada no
                    # piso dt_min (nunca congelar o relgio do evento)
                    dt = min(max(dt * 1.5, self.cfg.dt_min * 10.0), self.cfg.dt_max)
                elif converged and n_picard_it <= 3:
                    dt = min(dt * 1.5, self.cfg.dt_max)
                else:
                    dt = min(dt * 1.2, self.cfg.dt_max)
                
            # Salvar perfis completos nos dias de leitura (print times escolhidos)
            while _pd_idx < len(print_days_list) and print_days_list[_pd_idx] <= t:
                _pd = print_days_list[_pd_idx]
                print_profiles[_pd] = {
                    "theta": theta.copy(),
                    "h": h.copy(),
                    "c_total": {n["symbol"]: n["c_prof"].copy() for n in active_nutrients},
                }
                _pd_idx += 1

            # Salvar observações temporais (Breakthrough Curves nos nós de profundidade)
            if t >= next_obs_save or t >= self.cfg.total_days:
                obs_times.append(float(t))
                for d_val, idx_val in obs_node_map.items():
                    obs_theta[d_val].append(float(theta[idx_val]))
                    for n_it in active_nutrients:
                        sym_it = n_it["symbol"]
                        # N2: obs usa kd_eff (com competição Ca) em vez do kd nominal
                        _ke = n_it.get("kd_eff", n_it["kd"])
                        _ke_v = float(np.asarray(_ke)[idx_val]) if np.ndim(_ke) else float(_ke)
                        ret_v = float(theta_safe[idx_val] + self.soil.bulk_density * max(0.0, _ke_v))
                        c_soil_val = float(n_it["c_prof"][idx_val])
                        c_aq_val = (c_soil_val / max(ret_v, 1e-5)) * 1000.0  # mg/L em fase aquosa
                        obs_c[sym_it][d_val].append(c_aq_val)
                next_obs_save = t + obs_save_dt

            # Salvar resultados em intervalos
            if t >= next_save or t >= self.cfg.total_days:
                recorded_times.append(float(t))
                recorded_theta.append(theta.copy())
                recorded_h.append(h.copy())
                for n_item in active_nutrients:
                    n_item["recorded_profiles"].append(n_item["c_prof"].copy())
                next_save += save_interval

        # Print times restantes (<= total_days, erro já barrado acima): grava
        # com o perfil final caso o último passo não tenha cravado o dia.
        while _pd_idx < len(print_days_list):
            _pd = print_days_list[_pd_idx]
            if _pd not in print_profiles:
                print_profiles[_pd] = {
                    "theta": theta.copy(),
                    "h": h.copy(),
                    "c_total": {n["symbol"]: n["c_prof"].copy() for n in active_nutrients},
                }
            _pd_idx += 1
                
        # --- CÁLCULO DOS INDICADORES FINAIS AGRONÔMICOS ---
        # Máscaras usam a profundidade MÁXIMA da cultura (raiz cresce até o máx no ciclo).
        root_depth = float(_root_max_for_mask) if self.crop else getattr(self.config, "target_depth_cm", 30.0)
        root_mask = z <= root_depth
        below_root_mask = z > root_depth
        
        nutrient_results = {}
        for n_item in active_nutrients:
            sym = n_item["symbol"]
            applied_m = n_item["applied_mg_cm2"]
            rel_m = n_item["released_mg_cm2"]
            rem_capsule_m = max(0.0, applied_m - rel_m)

            c_final = n_item["c_prof"]
            m_root = float(np.sum(c_final[root_mask] * dz))
            m_below = float(np.sum(c_final[below_root_mask] * dz))
            m_leached = float(n_item["leached_bottom"])
            m_lost_total = m_below + m_leached
            m_profile = float(np.sum(c_final * dz))
            m_uptaken = float(n_item.get("uptaken_mg_cm2", 0.0))
            m_residual = float(n_item.get("residual_mg_cm2", 0.0))
            # P9: todos os % de destino sobre m_inputs = dose (+ fertirrigação) + residual,
            # SEM recorte; na CRF a dose inclui a cápsula. Assim
            # retido+abaixo+fundo+absorvido+cápsula = 100 + mass_closure_pct (erro numérico, |·|<1%).
            m_inputs = applied_m + m_residual
            _den = max(m_inputs, 1e-12)
            if m_inputs < 1e-12:
                leaching_pct_total = 0.0
                retained_root_pct = 0.0
                capsule_pct = 0.0
                retained_profile_pct = 0.0
                leached_bottom_pct = 0.0
                uptaken_pct = 0.0
            else:
                leaching_pct_total = float((m_lost_total / _den) * 100.0)
                retained_root_pct = float((m_root / _den) * 100.0)
                capsule_pct = float((rem_capsule_m / _den) * 100.0)
                retained_profile_pct = float((m_profile / _den) * 100.0)
                leached_bottom_pct = float((m_leached / _den) * 100.0)
                uptaken_pct = float((m_uptaken / _den) * 100.0)

            # Lixiviação em relação ao que já foi liberado no solo (crua, sobre liberado)
            leaching_pct_released = float((m_lost_total / max(rel_m, 1e-4)) * 100.0)

            # Balanço de massa no perfil (fronteira = fundo do domínio) — métrica principal
            # P9: cápsula entra no fechamento (antes a CRF aparecia como erro):
            # mass_closure = (perfil + lixiviado + absorvido + cápsula − inputs)/inputs.
            # O residual entra em c_prof; sem somá-lo ao denominador, 10 mg/dm3 em
            # 0-20 cm virava +19,4% fantasma. Mantido sem clip (resíduo numérico exposto).
            if m_inputs < 1e-12:
                mass_closure_pct = 0.0
            else:
                mass_closure_pct = float((m_profile + m_leached + m_uptaken + rem_capsule_m - m_inputs) / _den * 100.0)

            # Pico indefinido (NaN) se sem massa ou perfil plano/fantasma — sem recomendação, só descrição
            try:
                _cmax = float(np.max(c_final)) if c_final.size else 0.0
                _cmin = float(np.min(c_final)) if c_final.size else 0.0
            except (TypeError, ValueError):
                _cmax, _cmin = 0.0, 0.0
            _flat_ratio = float((_cmax - _cmin) / max(_cmax, 1e-18)) if _cmax > 1e-18 else 0.0
            if (m_inputs < 1e-9) or (_cmax <= 1e-12) or (m_profile < 0.0005 * max(m_inputs, 0.0)) or (_flat_ratio < 0.10):
                peak_depth = float("nan")
            else:
                peak_idx = int(np.argmax(c_final))
                peak_depth = float(z[peak_idx])

            nutrient_results[sym] = {
                "symbol": sym,
                "name": n_item["name"],
                "dose_kg_ha": n_item["dose_kg_ha"],
                "kd": n_item["kd"],
                "dispersivity_cm": n_item["dispersivity_cm"],
                "release_type": n_item["release_type"],
                "release_days": n_item["release_days"],
                "placement_mode": n_item["placement_mode"],
                "z_app_top_cm": n_item["z_app_top_cm"],
                "z_app_bottom_cm": n_item["z_app_bottom_cm"],
                "initial_residual_mg_dm3": n_item["initial_residual_mg_dm3"],
                "applied_kg_ha": applied_m * 100.0,
                "released_kg_ha": rel_m * 100.0,
                "fertigation_c0_mg_l": float(n_item.get("fertigation_c0_mg_l", 0.0) or 0.0),
                "capsule_kg_ha": rem_capsule_m * 100.0,
                "retained_kg_ha": m_root * 100.0,
                "leached_kg_ha": m_lost_total * 100.0,
                "input_kg_ha": m_inputs * 100.0,
                "retained_root_pct": retained_root_pct,
                "capsule_pct": capsule_pct,
                "retained_profile_kg_ha": m_profile * 100.0,
                "retained_profile_pct": retained_profile_pct,
                "leached_bottom_kg_ha": m_leached * 100.0,
                "leached_bottom_pct": leached_bottom_pct,
                "uptaken_kg_ha": m_uptaken * 100.0,
                "uptaken_pct": uptaken_pct,
                "residual_mg_cm2": m_residual,
                "residual_kg_ha": m_residual * 100.0,
                "mass_closure_pct": mass_closure_pct,
                "mass_closure": mass_closure_pct,
                "uptake_cap_kg_ha": (float(n_item.get("uptake_cap_mg_cm2", 0.0) or 0.0) * 100.0
                                     if n_item.get("uptake_cap_mg_cm2", None) is not None else None),
                "uptake_capped": bool(n_item.get("uptake_capped", False)),
                "sorption": str(n_item.get("sorption", "linear")),
                "smax_mg_g": float(n_item.get("smax_mg_g", 0.0) or 0.0),
                "kl_cm3_mg": float(n_item.get("kl_cm3_mg", 0.0) or 0.0),
                "kd_eff": (np.asarray(n_item.get("kd_eff", n_item["kd"]), dtype=float).copy()
                           if np.ndim(n_item.get("kd_eff", 0.0)) else float(n_item.get("kd_eff", n_item["kd"]))),
                "leaching_ratio_pct": leaching_pct_total,
                "leaching_of_released_pct": leaching_pct_released,
                "peak_depth_cm": peak_depth,
                "final_profile": c_final.copy(),
                "profiles": n_item["recorded_profiles"]
            }

        # --- F1/F7: fechamento hídrico exposto (relativo a P) ---
        # P-(dS+D+RO+E+T) com dS em volumes de controle (dV: 0.5 nas
        # fronteiras, como no resíduo). Sem E+T o "resíduo" carrega a ET
        # como erro aparente (cresce com P). Exposto p/ teste de teto relativo.
        _dVw = np.full(nz, dz)
        _dVw[0] = dz * 0.5
        _dVw[-1] = dz * 0.5
        _p_tot_cm = 0.0
        for _ev in (water_events or []):
            try:
                _p_tot_cm += float(_ev[2]) / 10.0
            except (TypeError, ValueError, IndexError):
                pass
        _s0 = float(np.sum(np.asarray(recorded_theta[0], dtype=float) * _dVw))
        _s1 = float(np.sum(np.asarray(theta, dtype=float) * _dVw))
        _wc_cm = float(_p_tot_cm - (_s1 - _s0) - float(q_bottom_cum) - float(runoff_cum)
                       - float(evap_cum) - float(transp_cum))
        _wc_pct = float(_wc_cm / max(_p_tot_cm, 1e-9) * 100.0) if _p_tot_cm > 1e-12 else 0.0

        # Nutriente principal para compatibilidade retroativa
        if active_nutrients:
            primary = active_nutrients[0]
            prim_sym = primary["symbol"]
            prim_res = nutrient_results[prim_sym]
            
            return SimulationResults(
                z=z,
                times_days=recorded_times,
                theta_profiles=recorded_theta,
                h_profiles=recorded_h,
                n_profiles=primary["recorded_profiles"],
                q_bottom_cum_cm=float(q_bottom_cum),
                n_leached_mg_cm2=float(primary["leached_bottom"]),
                n_below_root_mg_cm2=float(np.sum(primary["c_prof"][below_root_mask] * dz)),
                n_in_root_zone_mg_cm2=float(np.sum(primary["c_prof"][root_mask] * dz)),
                n_total_applied_mg_cm2=float(primary["applied_mg_cm2"]),
                leaching_ratio_pct=prim_res["leaching_ratio_pct"],
                peak_depth_cm=prim_res["peak_depth_cm"],
                nutrient_results=nutrient_results,
                target_depth_cm=float(root_depth),
                runoff_cum_cm=float(runoff_cum),
                obs_depths_cm=list(obs_node_map.keys()),
                obs_times_days=obs_times,
                obs_theta_series=obs_theta,
                obs_c_series=obs_c,
                retained_profile_pct=float(prim_res.get("retained_profile_pct", 0.0)),
                leached_bottom_pct=float(prim_res.get("leached_bottom_pct", 0.0)),
                uptaken_pct=float(prim_res.get("uptaken_pct", 0.0)),
                mass_closure_pct=float(prim_res.get("mass_closure_pct", 0.0)),
                mass_closure=float(prim_res.get("mass_closure_pct", 0.0)),
                converged=(non_converged_steps == 0),
                non_converged_steps=int(non_converged_steps),
                print_profiles=print_profiles,
                evap_cum_cm=float(evap_cum),
                transp_cum_cm=float(transp_cum),
                water_closure_cm=float(_wc_cm),
                water_closure_pct=float(_wc_pct)
            )
        else:
            # Modo "somente água" - sem solutos
            return SimulationResults(
                z=z,
                times_days=recorded_times,
                theta_profiles=recorded_theta,
                h_profiles=recorded_h,
                n_profiles=[],
                q_bottom_cum_cm=float(q_bottom_cum),
                n_leached_mg_cm2=0.0,
                n_below_root_mg_cm2=0.0,
                n_in_root_zone_mg_cm2=0.0,
                n_total_applied_mg_cm2=0.0,
                leaching_ratio_pct=0.0,
                peak_depth_cm=0.0,
                nutrient_results={},
                target_depth_cm=float(root_depth),
                runoff_cum_cm=float(runoff_cum),
                obs_depths_cm=list(obs_node_map.keys()),
                obs_times_days=obs_times,
                obs_theta_series=obs_theta,
                obs_c_series={},
                retained_profile_pct=0.0,
                leached_bottom_pct=0.0,
                uptaken_pct=0.0,
                mass_closure_pct=0.0,
                mass_closure=0.0,
                converged=(non_converged_steps == 0),
                non_converged_steps=int(non_converged_steps),
                print_profiles=print_profiles,
                evap_cum_cm=float(evap_cum),
                transp_cum_cm=float(transp_cum),
                water_closure_cm=float(_wc_cm),
                water_closure_pct=float(_wc_pct)
            )
