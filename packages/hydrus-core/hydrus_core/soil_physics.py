"""
Soil Physics Module: van Genuchten - Mualem hydraulic parameters and pedotransfer functions.
Values based on USDA / Rosetta and Brazilian soil databases (Embrapa/Latossolos).
"""

from dataclasses import dataclass
import numpy as np


class RosettaUnavailableError(RuntimeError):
    """Levantada quando a Rosetta (pacote ``rosetta-soil``) não está instalada ou
    não consegue prever parâmetros válidos para a granulometria informada.

    Deliberadamente NÃO existe fallback aproximado: quando isto é levantado, o
    aplicativo deve exibir um erro ao usuário em vez de valores empíricos.
    """


@dataclass
class SoilParameters:
    name: str
    descr: str
    theta_r: float    # Residual water content [cm3/cm3]
    theta_s: float    # Saturated water content [cm3/cm3]
    alpha: float      # van Genuchten alpha parameter [1/cm]
    n: float          # van Genuchten n parameter [-]
    ks: float         # Saturated hydraulic conductivity [cm/day]
    l: float = 0.5    # Tortuosity parameter [-]
    bulk_density: float = 1.35  # Dry bulk density [g/cm3]
    sand_pct: float = None      # Granulometria: areia [%]
    clay_pct: float = None      # Granulometria: argila [%]
    citation: str = ""          # Origem dos parametros hidricos (referencia bibliografica)

    @property
    def m(self) -> float:
        return 1.0 - (1.0 / self.n)

    def __post_init__(self):
        if self.n <= 1.05:
            raise ValueError(f"Parâmetro van Genuchten n deve ser > 1.05 (recebido: {self.n}).")
        if self.theta_s <= self.theta_r:
            raise ValueError(f"theta_s ({self.theta_s}) deve ser maior que theta_r ({self.theta_r}).")
        if self.alpha <= 0.0 or self.ks <= 0.0:
            raise ValueError("Parâmetros alpha e Ks devem ser estritamente positivos.")

# Standard Soil Database (Brazilian Latossolos + USDA classes)
SOIL_DATABASE = {
    "latossolo_argiloso": SoilParameters(
        name="Latossolo Vermelho Argiloso",
        descr="Comum no Cerrado/PR/SP. Boa retenção, alta permeabilidade estrutural (pseudo-areia).",
        theta_r=0.18,
        theta_s=0.52,
        alpha=0.035,
        n=1.55,
        ks=65.0,  # Alta permeabilidade devido a microagregacao
        bulk_density=1.15,
        sand_pct=25.0,
        clay_pct=60.0,
        citation="Embrapa/Centro Nacional de Pedologia (Latossolos), valores tipicos de laboratorio"
    ),
    "latossolo_medio": SoilParameters(
        name="Latossolo Vermelho Textura Média",
        descr="Textura franco-argilo-arenosa, boa drenagem.",
        theta_r=0.10,
        theta_s=0.43,
        alpha=0.030,
        n=1.65,
        ks=80.0,
        bulk_density=1.30,
        sand_pct=45.0,
        clay_pct=25.0,
        citation="Embrapa/Centro Nacional de Pedologia (Latossolos), valores tipicos de laboratorio"
    ),
    "neossolo_arenoso": SoilParameters(
        name="Neossolo Quartzarênico (Solo Arenoso)",
        descr="Altíssimo risco de lixiviação. Baixa retenção de água e nutrientes.",
        theta_r=0.045,
        theta_s=0.38,
        alpha=0.065,
        n=2.20,
        ks=250.0,
        bulk_density=1.55,
        sand_pct=90.0,
        clay_pct=5.0,
        citation="Valores tipicos de areias quartzosas (Carson, 1974; Rosetta)"
    ),
    "argissolo": SoilParameters(
        name="Argissolo Vermelho-Amarelo",
        descr="Horizonte superficial arenoso/médio sobre horizonte B textural argiloso.",
        theta_r=0.12,
        theta_s=0.45,
        alpha=0.025,
        n=1.45,
        ks=35.0,
        bulk_density=1.40,
        sand_pct=55.0,
        clay_pct=30.0,
        citation="Valores tipicos de Argissolos (BMP Brasil; media das horizontes)"
    ),
    "franco": SoilParameters(
        name="Solo Franco (Equilibrado / USDA Loam)",
        descr="Proporções equilibradas de areia, silte e argila.",
        theta_r=0.078,
        theta_s=0.43,
        alpha=0.036,
        n=1.56,
        ks=25.0,
        bulk_density=1.35,
        sand_pct=42.0,
        clay_pct=22.0,
        citation="Guia_Validacao_HYDRUS_1D.pdf (cenario franco de validacao)"
    ),
    "argila_pesada": SoilParameters(
        name="Argila Pesada / Gleissolo",
        descr="Drenagem muito lenta, propício ao encharcamento e desnitrificação.",
        theta_r=0.15,
        theta_s=0.50,
        alpha=0.015,
        n=1.25,
        ks=8.0,
        bulk_density=1.25,
        sand_pct=15.0,
        clay_pct=65.0,
        citation="Valores tipicos de Gleissolos/Varzeas (BMP Brasil)"
    ),
    "pub_lva_arenoso": SoilParameters(
        name="Latossolo Vermelho-Amarelo (LVA Arenoso - Piracicaba)",
        descr="Solo arenoso de Piracicaba-SP (Pinho & Miranda, 2014)",
        theta_r=0.025,
        theta_s=0.423,
        alpha=0.0343,
        n=1.4634,
        ks=65.0,
        bulk_density=1.30,
        sand_pct=80.0,
        clay_pct=15.0,
        citation="PUB Arthur 2840, Tab.1 (Pinho & Miranda, 2014); rho_b 1,2-1,3 g/cm3 do PUB."
    ),
    "pub_nv_argiloso": SoilParameters(
        name="Nitossolo Vermelho (NV Argiloso - Piracicaba)",
        descr="Solo argiloso de Piracicaba-SP (Pinho & Miranda, 2014)",
        theta_r=0.068,
        theta_s=0.505,
        alpha=0.0301,
        n=1.1763,
        ks=40.0,
        bulk_density=1.30,
        sand_pct=20.0,
        clay_pct=60.0,
        citation="PUB Arthur 2840, Tab.1 (Pinho & Miranda, 2014)."
    )
}

def classify_texture(sand_pct: float = None, clay_pct: float = None) -> str:
    """
    Classifica a textura do solo a partir da granulometria (% areia / argila).
    Usada por todos os modulos para garantir consistencia no Kd e nas referencias.
    """
    sand = float(sand_pct) if sand_pct is not None else 0.0
    clay = float(clay_pct) if clay_pct is not None else 0.0
    if sand > 70.0:
        return "arenoso"
    if clay > 35.0:
        return "argiloso"
    return "medio"

def estimate_ptf_rosetta(sand_pct: float, clay_pct: float, silt_pct: float = None, bulk_density: float = 1.35) -> SoilParameters:
    """Rosetta (Schaap et al., 2001) — versão 1, média geométrica — via pacote
    `rosetta-soil` (USDA-ARS, Todd Skaggs). Reproduz a predição por rede neural do
    HYDRUS-1D ("Neural Network Prediction").

    Entradas: areia/silte/argila (%) e densidade do solo (g/cm³) → modelo 3 da Rosetta.

    Raises:
        RosettaUnavailableError: se o pacote ``rosetta-soil`` não estiver instalado
            ou a rede neural não puder fornecer uma predição válida. Não há valor
            aproximado de retorno.
    """
    if silt_pct is None:
        silt_pct = max(0.0, 100.0 - sand_pct - clay_pct)
    sand_pct = float(sand_pct)
    clay_pct = float(clay_pct)
    silt_pct = float(silt_pct)
    bulk_density = float(bulk_density)

    # A Rosetta (modelo 3) exige uma textura fisicamente válida: areia + silte + argila = 100%.
    # Com soma ≠ 100 a rede devolve "sem resultado" (code = -1) para qualquer combinação.
    _total = sand_pct + silt_pct + clay_pct
    if abs(_total - 100.0) > 0.5:
        raise RosettaUnavailableError(
            f"A granulometria precisa somar 100%: Areia={sand_pct:.1f}% + Silte={silt_pct:.1f}% "
            f"+ Argila={clay_pct:.1f}% = {_total:.1f}%. Ajuste a areia e a argila — o silte é "
            "calculado automaticamente (silte = 100 − areia − argila). Nenhum valor aproximado foi gerado."
        )

    method = "Rosetta v1 (média geométrica, rosetta-soil)"
    try:
        from rosetta import rosetta as _rosetta
    except ImportError as exc:
        raise RosettaUnavailableError(
            "A função de pedotransferência Rosetta (pacote 'rosetta-soil') não está instalada. "
            "Instale com 'pip install rosetta-soil>=0.3.2' para usar o Solo Personalizado. "
            "Nenhum valor aproximado foi gerado."
        ) from exc

    try:
        mean, _std, codes = _rosetta(
            1, [[sand_pct, silt_pct, clay_pct, bulk_density]], estimate_type="geo"
        )
    except Exception as exc:
        raise RosettaUnavailableError(
            f"A Rosetta falhou ao processar os dados (Areia={sand_pct:.1f}%, "
            f"Silte={silt_pct:.1f}%, Argila={clay_pct:.1f}%, ρb={bulk_density:.2f} g/cm³): {exc}. "
            "Nenhum valor aproximado foi gerado."
        ) from exc

    code = int(np.ravel(codes)[0])
    row = np.ravel(mean)[:5]
    if code == -1 or not np.all(np.isfinite(row)):
        raise RosettaUnavailableError(
            f"A Rosetta não conseguiu prever parâmetros para Areia={sand_pct:.1f}%, "
            f"Silte={silt_pct:.1f}%, Argila={clay_pct:.1f}%, ρb={bulk_density:.2f} g/cm³. "
            "Verifique a granulometria informada. Nenhum valor aproximado foi gerado."
        )
    theta_r, theta_s, alpha, n, ks = [float(x) for x in row]

    return SoilParameters(
        name=f"Solo Personalizado ({sand_pct:.0f}% Areia, {clay_pct:.0f}% Argila)",
        descr=(f"{method}: Areia={sand_pct:.1f}%, Silte={silt_pct:.1f}%, Argila={clay_pct:.1f}%, "
               f"ρb={bulk_density:.2f} g/cm³"),
        theta_r=float(theta_r),
        theta_s=float(theta_s),
        alpha=float(alpha),
        n=float(n),
        ks=float(ks),
        bulk_density=float(bulk_density),
        sand_pct=float(sand_pct),
        clay_pct=float(clay_pct),
        citation="Rosetta (Schaap, Leij & van Genuchten, 2001) — rosetta-soil (USDA-ARS)"
    )

def water_content_from_h(h: np.ndarray, sp: SoilParameters) -> np.ndarray:
    """
    Computes volumetric water content theta(h) given matric head h [cm] (h <= 0).
    van Genuchten (1980) equation.
    """
    # For saturated conditions (h >= 0), theta = theta_s
    h_abs = np.abs(np.minimum(h, 0.0))
    m = sp.m
    se = (1.0 + (sp.alpha * h_abs) ** sp.n) ** (-m)
    theta = sp.theta_r + (sp.theta_s - sp.theta_r) * se
    return theta

def matric_head_from_theta(theta: np.ndarray, sp: SoilParameters) -> np.ndarray:
    """
    Inverts van Genuchten (1980) to compute h from theta.
    """
    theta_eff = np.clip((theta - sp.theta_r) / (sp.theta_s - sp.theta_r), 1e-5, 0.99999)
    m = sp.m
    h_abs = ((theta_eff ** (-1.0 / m) - 1.0) ** (1.0 / sp.n)) / sp.alpha
    return -h_abs

def hydraulic_conductivity(h: np.ndarray, sp: SoilParameters) -> np.ndarray:
    """
    Computes unsaturated hydraulic conductivity K(h) [cm/day].
    van Genuchten - Mualem model.
    """
    h_abs = np.abs(np.minimum(h, 0.0))
    m = sp.m
    se = (1.0 + (sp.alpha * h_abs) ** sp.n) ** (-m)
    k = sp.ks * (se ** sp.l) * (1.0 - (1.0 - se ** (1.0 / m)) ** m) ** 2
    return np.maximum(k, 1e-12)

def specific_moisture_capacity(h: np.ndarray, sp: SoilParameters) -> np.ndarray:
    """
    Computes C(h) = d(theta)/dh [1/cm].
    """
    h_abs = np.abs(np.minimum(h, 0.0))
    m = sp.m
    factor = (sp.theta_s - sp.theta_r) * sp.alpha * sp.n * m
    denom = (1.0 + (sp.alpha * h_abs) ** sp.n) ** (m + 1.0)
    c = factor * (sp.alpha * h_abs) ** (sp.n - 1.0) / denom
    # At saturation (h >= 0), C(h) -> small positive value to avoid division by zero
    c = np.where(h >= 0, 1e-6, c)
    return np.maximum(c, 1e-7)
