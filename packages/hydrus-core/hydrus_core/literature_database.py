"""
Scientific Literature Database for AgroHydrus 1D:
1. Nutrient Adsorption Partition Coefficients (Kd) across soil textures (Embrapa, van Raij, Sparks, SSSA).
2. Commercial Fertilizers and chemical compositions (Ureia, KCl, Polialita, K-Mag, MAP, etc.).
3. Climatological Historical Series for Brazilian Agricultural Hubs (INMET / NASA POWER data).
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple
import numpy as np

# -------------------------------------------------------------
# 1. BASE CIENTÍFICA DE ADSORÇÃO DE NUTRIENTES (Kd) NA LITERATURA
# -------------------------------------------------------------
@dataclass
class KdLiteratureEntry:
    nutrient_symbol: str
    nutrient_name: str
    soil_texture: str        # 'arenoso', 'medio', 'argiloso'
    default_kd: float        # cm3/g
    min_kd: float
    max_kd: float
    citation: str            # Referência bibliográfica aberta
    description: str

LITERATURE_KD_DATABASE: Dict[Tuple[str, str], KdLiteratureEntry] = {
    # --- NITROGÊNIO (Nitrato NO3-) ---
    ("N", "arenoso"): KdLiteratureEntry(
        nutrient_symbol="N",
        nutrient_name="Nitrogênio (Nitrato - NO3-)",
        soil_texture="arenoso",
        default_kd=0.00,
        min_kd=0.00,
        max_kd=0.05,
        citation="SSSA Book Series (Sparks et al., 1996); Raij (2011)",
        description="Nitrato é um ânion livre repelido pelas cargas negativas das argilas. Mobilidade máxima."
    ),
    ("N", "medio"): KdLiteratureEntry(
        nutrient_symbol="N",
        nutrient_name="Nitrogênio (Nitrato - NO3-)",
        soil_texture="medio",
        default_kd=0.00,
        min_kd=0.00,
        max_kd=0.08,
        citation="SSSA Book Series (Sparks et al., 1996); Raij (2011)",
        description="Praticamente nula adsorção. Pode apresentar retenção residual muito discreta em solos ácricos."
    ),
    ("N", "argiloso"): KdLiteratureEntry(
        nutrient_symbol="N",
        nutrient_name="Nitrogênio (Nitrato - NO3-)",
        soil_texture="argiloso",
        default_kd=0.02,
        min_kd=0.00,
        max_kd=0.15,
        citation="Raij (2011) - Fertilidade do Solo e Adubação; Silva (2013)",
        description="Em Latossolos muito argilosos e ácidos (horizonte B ácrico), óxidos de Fe/Al podem adsorver traços de NO3-."
    ),

    # --- POTÁSSIO (K+) ---
    ("K", "arenoso"): KdLiteratureEntry(
        nutrient_symbol="K",
        nutrient_name="Potássio (K+)",
        soil_texture="arenoso",
        default_kd=0.20,
        min_kd=0.10,
        max_kd=0.35,
        citation="Embrapa Solos (Boletim de Pesquisa 148); Sparks (1987)",
        description="Baixa capacidade de troca catiônica (CTC < 4 cmolc/dm3). Retenção fraca, sujeito a lixiviação moderada."
    ),
    ("K", "medio"): KdLiteratureEntry(
        nutrient_symbol="K",
        nutrient_name="Potássio (K+)",
        soil_texture="medio",
        default_kd=0.45,
        min_kd=0.25,
        max_kd=0.70,
        citation="Raij (2011); Ernani et al. (2007) - Química do Solo",
        description="Equilíbrio intermediário entre potássio trocável na CTC e na solução."
    ),
    ("K", "argiloso"): KdLiteratureEntry(
        nutrient_symbol="K",
        nutrient_name="Potássio (K+)",
        soil_texture="argiloso",
        default_kd=0.85,
        min_kd=0.50,
        max_kd=1.50,
        citation="Embrapa Solos; Pinho & Miranda (2014); Sparks (1987)",
        description="Boa retenção na CTC pelas argilas e matéria orgânica. Menor teor em solução livre, menor lixiviação."
    ),

    # --- CÁLCIO (Ca2+) ---
    ("Ca", "arenoso"): KdLiteratureEntry(
        nutrient_symbol="Ca",
        nutrient_name="Cálcio (Ca2+)",
        soil_texture="arenoso",
        default_kd=0.60,
        min_kd=0.30,
        max_kd=2.00,
        citation="U.S. EPA Soil Screening Guidance (EPA-540-R-96); Raij (2011)",
        description="Cátion bivalente com maior energia de atração à CTC que o potássio."
    ),
    ("Ca", "medio"): KdLiteratureEntry(
        nutrient_symbol="Ca",
        nutrient_name="Cálcio (Ca2+)",
        soil_texture="medio",
        default_kd=1.20,
        min_kd=0.60,
        max_kd=2.50,
        citation="Raij (2011); Havlin et al. (2014) - Soil Fertility and Fertilizers",
        description="Boa adsorção na CTC em solos corrigidos com calcário."
    ),
    ("Ca", "argiloso"): KdLiteratureEntry(
        nutrient_symbol="Ca",
        nutrient_name="Cálcio (Ca2+)",
        soil_texture="argiloso",
        default_kd=2.20,
        min_kd=1.00,
        max_kd=4.50,
        citation="Embrapa Solos; Raij (2011)",
        description="Forte retenção na fração coloidal. Lixiviação insignificante na camada arável."
    ),

    # --- MAGNÉSIO (Mg2+) ---
    ("Mg", "arenoso"): KdLiteratureEntry(
        nutrient_symbol="Mg",
        nutrient_name="Magnésio (Mg2+)",
        soil_texture="arenoso",
        default_kd=0.35,
        min_kd=0.15,
        max_kd=0.80,
        citation="Sparks et al. (1996); Raij (2011)",
        description="Raio de hidratação maior que o Ca2+, resultando em menor força de ligação e maior mobilidade."
    ),
    ("Mg", "medio"): KdLiteratureEntry(
        nutrient_symbol="Mg",
        nutrient_name="Magnésio (Mg2+)",
        soil_texture="medio",
        default_kd=0.80,
        min_kd=0.40,
        max_kd=1.60,
        citation="Raij (2011); Ernani et al. (2007)",
        description="Retenção moderada na CTC."
    ),
    ("Mg", "argiloso"): KdLiteratureEntry(
        nutrient_symbol="Mg",
        nutrient_name="Magnésio (Mg2+)",
        soil_texture="argiloso",
        default_kd=1.50,
        min_kd=0.70,
        max_kd=3.00,
        citation="Embrapa Solos; Raij (2011)",
        description="Boa retenção na fração coloidal de solos argilosos."
    ),

    # --- ENXOFRE (Sulfato SO4 2-) ---
    ("S", "arenoso"): KdLiteratureEntry(
        nutrient_symbol="S",
        nutrient_name="Enxofre (Sulfato - SO4 2-)",
        soil_texture="arenoso",
        default_kd=0.05,
        min_kd=0.00,
        max_kd=0.15,
        citation="Casagrande et al. (2003) - Adsorção de sulfato em solos brasileiros; Raij (2011)",
        description="Pouca ou nenhuma adsorção na camada superficial arenosa. Alta lixiviação com chuvas volumosas."
    ),
    ("S", "medio"): KdLiteratureEntry(
        nutrient_symbol="S",
        nutrient_name="Enxofre (Sulfato - SO4 2-)",
        soil_texture="medio",
        default_kd=0.15,
        min_kd=0.05,
        max_kd=0.35,
        citation="Casagrande et al. (2003); Couto et al. (1979)",
        description="Adsorção específica em óxidos de ferro e alumínio dependente do pH."
    ),
    ("S", "argiloso"): KdLiteratureEntry(
        nutrient_symbol="S",
        nutrient_name="Enxofre (Sulfato - SO4 2-)",
        soil_texture="argiloso",
        default_kd=0.40,
        min_kd=0.15,
        max_kd=0.90,
        citation="Casagrande et al. (2003); Raij (2011)",
        description="Em Latossolos argilosos, a adsorção aumenta consideravelmente em profundidade (horizonte B textural/latossólico)."
    ),

    # --- FÓSFORO (Fosfato H2PO4-) ---
    ("P", "arenoso"): KdLiteratureEntry(
        nutrient_symbol="P",
        nutrient_name="Fósforo (Fosfato - H2PO4-)",
        soil_texture="arenoso",
        default_kd=5.00,
        min_kd=2.00,
        max_kd=12.00,
        citation="Novais & Smyth (1999) - Fósforo em Solo e Planta; Raij (2011)",
        description="Mesmo em areia, o fosfato tem forte afinidade química superficial (fixação)."
    ),
    ("P", "medio"): KdLiteratureEntry(
        nutrient_symbol="P",
        nutrient_name="Fósforo (Fosfato - H2PO4-)",
        soil_texture="medio",
        default_kd=25.00,
        min_kd=10.00,
        max_kd=50.00,
        citation="Novais & Smyth (1999); Embrapa Solos",
        description="Altíssima adsorção/precipitação com Fe e Al. Lixiviação praticamente zero."
    ),
    ("P", "argiloso"): KdLiteratureEntry(
        nutrient_symbol="P",
        nutrient_name="Fósforo (Fosfato - H2PO4-)",
        soil_texture="argiloso",
        default_kd=80.00,
        min_kd=40.00,
        max_kd=200.00,
        citation="Novais & Smyth (1999); Raij (2011)",
        description="Fixação quase total na fração sólida. O fósforo move-se milímetros por difusão."
    )
}

# -------------------------------------------------------------
# 2. BASE DE FERTILIZANTES COMERCIAIS
# -------------------------------------------------------------
COMMERCIAL_FERTILIZERS = {
    "ureia": {
        "name": "Ureia Protegida ou Convencional (45-00-00)",
        "primary_nutrient": "N",
        "nutrient_pct": 45.0,
        "descr": "Fonte de alta concentração em N. Solúvel, transforma-se rapidamente em nitrato."
    },
    "nitrato_amonio": {
        "name": "Nitrato de Amônio (33-00-00)",
        "primary_nutrient": "N",
        "nutrient_pct": 33.0,
        "descr": "Fornece 50% de N na forma nítrica imediata e 50% amoniacal."
    },
    "sulfato_amonio": {
        "name": "Sulfato de Amônio (21-00-00 + 24% S)",
        "primary_nutrient": "N",
        "nutrient_pct": 21.0,
        "secondary_nutrient": "S",
        "secondary_pct": 24.0,
        "descr": "Excelente fonte combinada de Nitrogênio e Enxofre solúvel."
    },
    "kcl": {
        "name": "Cloreto de Potássio - KCl (00-00-60)",
        "primary_nutrient": "K",
        "nutrient_pct": 52.4, # Pureza estequiométrica (39.1/74.6 = 52.4% K elementar, conforme TCC Isabela 2024)
        "descr": "Fonte padrão de potássio na agricultura brasileira. Alta solubilidade."
    },
    "polialita": {
        "name": "Polialita / Polissulfato (K2Ca2Mg(SO4)4 · 2H2O)",
        "primary_nutrient": "K",
        "nutrient_pct": 11.6, # 14% K2O
        "secondary_nutrient": "S",
        "secondary_pct": 19.0,
        "tertiary_nutrient": "Ca",
        "tertiary_pct": 12.0,
        "quaternary_nutrient": "Mg",
        "quaternary_pct": 3.6,
        "descr": "Fertilizante multinutriente natural de liberação gradual prolongada."
    },
    "kmag": {
        "name": "K-Mag / Sulpomag (00-00-22 + 11% Mg + 22% S)",
        "primary_nutrient": "K",
        "nutrient_pct": 18.0,
        "secondary_nutrient": "Mg",
        "secondary_pct": 11.0,
        "tertiary_nutrient": "S",
        "tertiary_pct": 22.0,
        "descr": "Duplo sulfato de potássio e magnésio, fonte solúvel sem cloro."
    },
    "map": {
        "name": "MAP - Fosfato Monoamônico (11-52-00)",
        "primary_nutrient": "P",
        "nutrient_pct": 22.7, # 52% P2O5 = 22.7% P elementar
        "secondary_nutrient": "N",
        "secondary_pct": 11.0,
        "descr": "Fonte de alta concentração em fósforo com arranque de nitrogênio."
    },
    "kcl_gesso": {
        "name": "KCl + Gesso Agrícola (Blend Condicionador)",
        "primary_nutrient": "K",
        "nutrient_pct": 26.2,  # 50% KCl (52.4% K / 2 = 26.2% K)
        "secondary_nutrient": "Ca",
        "secondary_pct": 10.0, # ~20% Ca no gesso agrícola * 50% = 10% Ca
        "tertiary_nutrient": "S",
        "tertiary_pct": 8.0,   # ~16% S no gesso agrícola * 50% = 8% S
        "descr": "Mistura física/blend para condicionamento de subsuperfície com fornecimento de K, Ca e S."
    }
}

# -------------------------------------------------------------
# 3. POLOS AGRÍCOLAS BRASILEIROS E CLIMATOLOGIA PÚBLICA (INMET)
# -------------------------------------------------------------
AGRICULTURAL_HUBS = {
    "sorriso_mt": {
        "name": "Sorriso / Sinop - MT (Médio-Norte / Cerrado)",
        "annual_normal_mm": 1850.0,
        "et0_mean_mm_day": 4.0,          # Estimativa de ET0 media anual (mm/dia)
        "wet_months": [10, 11, 12, 1, 2, 3, 4], # Outubro a Abril
        "dry_months": [5, 6, 7, 8, 9],           # Maio a Setembro (seca total)
        "rain_factor_seco": 0.72,                # ~1.330 mm
        "rain_factor_chuvoso": 1.25,             # ~2.310 mm
        "descr": "Maior polo produtor de soja e milho safrinha do mundo. Seca de inverno rígida e veranicos de verão."
    },
    "rio_verde_go": {
        "name": "Rio Verde / Jataí - GO (Sudoeste Goiano)",
        "annual_normal_mm": 1600.0,
        "et0_mean_mm_day": 4.2,          # Estimativa de ET0 media anual (mm/dia)
        "wet_months": [10, 11, 12, 1, 2, 3, 4],
        "dry_months": [5, 6, 7, 8, 9],
        "rain_factor_seco": 0.75,                # ~1.200 mm
        "rain_factor_chuvoso": 1.28,             # ~2.050 mm
        "descr": "Cerrado central com alta produtividade de grãos em Latossolos Vermelhos argilosos."
    },
    "lem_ba": {
        "name": "Luís Eduardo Magalhães - BA (Matopiba / Oeste Baiano)",
        "annual_normal_mm": 1100.0,
        "et0_mean_mm_day": 4.5,          # Estimativa de ET0 media anual (mm/dia)
        "wet_months": [11, 12, 1, 2, 3, 4],
        "dry_months": [5, 6, 7, 8, 9, 10],
        "rain_factor_seco": 0.68,                # ~750 mm (estiagem severa)
        "rain_factor_chuvoso": 1.35,             # ~1.480 mm
        "descr": "Solos de textura média a arenosa. Alto risco de veranicos e perda rápida de nutrientes."
    },
    "piracicaba_sp": {
        "name": "Ribeirão Preto / Piracicaba - SP (Cinturão Paulista)",
        "annual_normal_mm": 1320.0,
        "et0_mean_mm_day": 3.6,          # Estimativa de ET0 media anual (mm/dia)
        "wet_months": [10, 11, 12, 1, 2, 3],
        "dry_months": [4, 5, 6, 7, 8, 9],
        "rain_factor_seco": 0.76,                # ~1.000 mm
        "rain_factor_chuvoso": 1.45,             # ~1.910 mm
        "descr": "Polo canavieiro, citrícola e de grãos em solos argilosos (Nitossolo e Latossolo)."
    },
    "londrina_pr": {
        "name": "Londrina / Maringá - PR (Norte Paranaense)",
        "annual_normal_mm": 1650.0,
        "et0_mean_mm_day": 3.5,          # Estimativa de ET0 media anual (mm/dia)
        "wet_months": [9, 10, 11, 12, 1, 2, 3, 4, 5], # Chuva bem distribuída
        "dry_months": [6, 7, 8],
        "rain_factor_seco": 0.78,                # ~1.280 mm
        "rain_factor_chuvoso": 1.30,             # ~2.140 mm
        "descr": "Terra Roxa Estruturada (Nitossolo Vermelho Eutrófico). Chuvas distribuídas ao longo das 4 estações."
    },
    "passo_fundo_rs": {
        "name": "Passo Fundo - RS (Planalto Gaúcho)",
        "annual_normal_mm": 1820.0,
        "et0_mean_mm_day": 3.2,          # Estimativa de ET0 media anual (mm/dia)
        "wet_months": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], # Sem estação seca definida
        "dry_months": [],
        "rain_factor_seco": 0.70,                # ~1.270 mm
        "rain_factor_chuvoso": 1.32,             # ~2.400 mm
        "descr": "Trigo, aveia, cevada e soja. Chuvas frequentes o ano inteiro decorrentes de frentes polares."
    }
}

def generate_hub_rainfall_series(hub_key: str, scenario: str = "medio") -> np.ndarray:
    """
    Gera uma série diária de 365 dias representativa da climatologia do polo agrícola
    com base nas normais do INMET para:
    - 'medio': Ano climatológico padrão
    - 'seco': Ano seco / estiagem prolongada
    - 'chuvoso': Ano super chuvoso / El Niño
    """
    hub = AGRICULTURAL_HUBS.get(hub_key, AGRICULTURAL_HUBS["sorriso_mt"])
    normal_mm = hub["annual_normal_mm"]
    
    if scenario == "seco":
        target_total = normal_mm * hub["rain_factor_seco"]
        seed = 42
    elif scenario == "chuvoso":
        target_total = normal_mm * hub["rain_factor_chuvoso"]
        seed = 83
    else:
        target_total = normal_mm
        seed = 100
        
    rng = np.random.default_rng(seed)
    
    # 365 dias divididos em 12 meses
    days_per_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    series = np.zeros(365)
    
    current_day = 0
    for m_idx, n_days in enumerate(days_per_month):
        month_num = m_idx + 1
        is_wet = month_num in hub["wet_months"]
        
        # Probabilidade de chuva no dia
        prob_rain = 0.50 if is_wet else 0.08
        if scenario == "seco" and is_wet:
            prob_rain = 0.35 # veranicos mais frequentes
        elif scenario == "chuvoso":
            prob_rain = min(0.65, prob_rain * 1.3)
            
        rain_days = rng.random(n_days) < prob_rain
        
        # Intensidade diária (distribuição exponencial/gama)
        mean_intensity = 18.0 if is_wet else 5.0
        if scenario == "chuvoso":
            mean_intensity *= 1.3
        elif scenario == "seco":
            mean_intensity *= 0.8
            
        daily_amounts = rng.exponential(mean_intensity, n_days) * rain_days
        series[current_day:current_day + n_days] = daily_amounts
        current_day += n_days
        
    # Calibrar proporcionalmente para o total esperado
    current_sum = np.sum(series)
    if current_sum > 0:
        series = series * (target_total / current_sum)
        
    return np.round(series, 1)

def generate_hub_et0_series(hub_key: str, scenario: str = "medio") -> np.ndarray:
    """Estimativa sazonal da ET0 diária (mm/dia) para o polo e cenário.

    ATENÇÃO: não é dado medido. É uma curva sintética construída a partir da normal
    anual de ET0 do polo (`et0_mean_mm_day`), com sazonalidade suavizada (ET0 mais
    alto nos meses secos e mais baixo nos chuvosos) e um leve ajuste por cenário
    (ano seco → ET0 um pouco maior; chuvoso → um pouco menor). A média anual resultante
    é igual ao valor do polo no cenário médio. O usuário pode editar/colar o ET0 real.
    """
    hub = AGRICULTURAL_HUBS.get(hub_key, AGRICULTURAL_HUBS["sorriso_mt"])
    base = float(hub.get("et0_mean_mm_day", 4.0))

    wet = set(hub.get("wet_months", []))
    # Peso por mês: -1 nos meses chuvosos (mais nublados, ET0 menor), +1 nos secos.
    month_w = np.array([-1.0 if (m + 1) in wet else 1.0 for m in range(12)])
    # Suavização circular para evitar degraus entre meses.
    kernel = np.array([1.0, 2.0, 3.0, 2.0, 1.0])
    kernel = kernel / kernel.sum()
    w_padded = np.concatenate([month_w[-2:], month_w, month_w[:2]])
    w_smooth = np.convolve(w_padded, kernel, mode="valid")
    w_smooth = w_smooth - w_smooth.mean()  # mantém a média anual = base

    amplitude = 0.20
    month_et0 = base * (1.0 + amplitude * w_smooth)

    if scenario == "seco":
        month_et0 = month_et0 * 1.08
    elif scenario == "chuvoso":
        month_et0 = month_et0 * 0.94

    days_per_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    series = np.repeat(month_et0, days_per_month).astype(float)

    # Variação dia a dia determinística (evita "degraus") mantendo a média.
    seed = {"seco": 42, "chuvoso": 83}.get(scenario, 100) + len(hub_key)
    rng = np.random.default_rng(seed)
    series = series + rng.normal(0.0, 0.25, size=series.shape)
    series = np.clip(series, 0.5, None)

    return np.round(series, 2)

# -------------------------------------------------------------
# 1b. ISOTERMA DE LANGMUIR OPCIONAL PARA FOSFORO (P)
# Saturacao de sitios de adsorcao (Novais & Smyth, 1999):
#   S(C) = Smax * K * C / (1 + K * C)   [mg P / g solo]
# em que C = concentracao em fase aquosa [mg/cm3], Smax = capacidade
# maxima de adsorcao (CMAP) e K = constante de afinidade.
# Linear (Kd constante) segue como default para TODOS os nutrientes,
# inclusive P; Langmuir so quando optado por nutriente (sorption="langmuir").
# Calibracao: Smax*K ~= Kd linear da tabela acima no limite C->0
# (P medio Kd~25: 0.80*30=24; P argiloso Kd~80: 1.60*50=80).
# -------------------------------------------------------------
@dataclass
class LangmuirParams:
    nutrient_symbol: str
    soil_texture: str          # 'arenoso', 'medio', 'argiloso'
    smax_mg_g: float           # capacidade maxima [mg P / g solo]
    kl_cm3_mg: float           # afinidade [cm3 / mg P]
    citation: str
    description: str

P_LANGMUIR_DATABASE: Dict[str, LangmuirParams] = {
    "arenoso": LangmuirParams(
        nutrient_symbol="P",
        soil_texture="arenoso",
        smax_mg_g=0.30,
        kl_cm3_mg=16.0,   # Smax*K = 4.8 ~= Kd 5.0 (P arenoso)
        citation="Novais & Smyth (1999) - Fosforo em Solo e Planta; Raij (2011)",
        description="CMAP baixa em areia: poucos sitios Fe/Al; satura rapido.",
    ),
    "medio": LangmuirParams(
        nutrient_symbol="P",
        soil_texture="medio",
        smax_mg_g=0.80,
        kl_cm3_mg=30.0,   # Smax*K = 24 ~= Kd 25 (P medio)
        citation="Novais & Smyth (1999); Embrapa Solos",
        description="CMAP intermediaria; isoterma concava satura sitios com dose alta.",
    ),
    "argiloso": LangmuirParams(
        nutrient_symbol="P",
        soil_texture="argiloso",
        smax_mg_g=1.60,
        kl_cm3_mg=50.0,   # Smax*K = 80 = Kd 80 (P argiloso)
        citation="Novais & Smyth (1999); Raij (2011)",
        description="CMAP alta em oxidos Fe/Al; fixacao quase total em baixa C.",
    ),
}


def get_langmuir_params(nutrient_symbol: str, soil_texture: str) -> LangmuirParams:
    """Retorna params de Langmuir so para P; demais simbolos levantam KeyError.

    Uso: solver opt-in por nutriente (sorption='langmuir'); linear segue default.
    """
    if str(nutrient_symbol).strip().upper() != "P":
        raise KeyError(f"Langmuir disponivel apenas para P (pedido: {nutrient_symbol!r}).")
    key = str(soil_texture).strip().lower()
    if key not in P_LANGMUIR_DATABASE:
        key = "medio"  # fallback textural conservador
    return P_LANGMUIR_DATABASE[key]


def get_kd_literature_data(nutrient_symbol: str, soil_texture: str) -> KdLiteratureEntry:
    key = (nutrient_symbol, soil_texture)
    if key in LITERATURE_KD_DATABASE:
        return LITERATURE_KD_DATABASE[key]
    # Fallback
    return KdLiteratureEntry(
        nutrient_symbol=nutrient_symbol,
        nutrient_name=nutrient_symbol,
        soil_texture=soil_texture,
        default_kd=0.20,
        min_kd=0.00,
        max_kd=1.00,
        citation="Literatura Geral de Solos (Raij, 2011)",
        description="Estimativa padrão com base na textura do solo."
    )
