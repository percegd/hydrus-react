"""
Crop Database and Root Water/Nutrient Uptake Module (Feddes et al. 1978).
"""

from dataclasses import dataclass
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

# Limiares de Feddes por cultura/estádio (faixas de Feddes et al. 1978 /
# Wesseling 1991; h3 varia com a demanda evaporativa e o estádio).
# h4 (murcha) e h1 (anaerobiose) diferem por tolerância da cultura:
# hortaliças sensíveis murcham cedo (~-5000), grãos ~-8000, cana/café
# toleram até ~-12000/-15000. Valores iniciais por classe — calibre localmente
# (todos editáveis na UI, passo 1, seção Cultura).
CROP_DATABASE = {
    "milho": CropParameters(
        name="Milho",
        stage="Desenvolvimento",
        root_depth_cm=40.0,
        kc=1.05,
        h1=-15.0,
        h2=-30.0,
        h3=-450.0,
        h4=-8000.0
    ),
    "soja": CropParameters(
        name="Soja",
        stage="Desenvolvimento",
        root_depth_cm=35.0,
        kc=1.0,
        h1=-15.0,
        h2=-30.0,
        h3=-450.0,
        h4=-12000.0
    ),
    "milho_inicial": CropParameters(
        name="Milho (Estágio Vegetativo Inicial - V3/V4)",
        stage="V3/V4",
        root_depth_cm=25.0,
        kc=0.5,
        h1=-15.0,
        h2=-30.0,
        h3=-400.0,
        h4=-8000.0
    ),
    "milho_desenvolvimento": CropParameters(
        name="Milho (Desenvolvimento / Florescimento - V8/VT)",
        stage="V8/VT",
        root_depth_cm=60.0,
        kc=1.2,
        h1=-15.0,
        h2=-30.0,
        h3=-500.0,
        h4=-8000.0
    ),
    "soja_inicial": CropParameters(
        name="Soja (V2/V3)",
        stage="V2/V3",
        root_depth_cm=20.0,
        kc=0.4,
        h1=-15.0,
        h2=-30.0,
        h3=-400.0,
        h4=-12000.0
    ),
    "soja_desenvolvimento": CropParameters(
        name="Soja (R1/R5 - Enchimento)",
        stage="R1/R5",
        root_depth_cm=50.0,
        kc=1.15,
        h1=-15.0,
        h2=-30.0,
        h3=-500.0,
        h4=-12000.0
    ),
    "cana_de_acucar": CropParameters(
        name="Cana-de-açúcar (Cana-planta ou soca estabelecida)",
        stage="Pleno vigor",
        root_depth_cm=80.0,
        kc=1.25,
        h1=-15.0,
        h2=-30.0,
        h3=-600.0,
        h4=-15000.0
    ),
    "cafe": CropParameters(
        name="Café Adulto",
        stage="Produção",
        root_depth_cm=70.0,
        kc=0.95,
        h1=-15.0,
        h2=-30.0,
        h3=-600.0,
        h4=-12000.0
    ),
    "hortalicas": CropParameters(
        name="Hortaliças / Olerícolas (Alface/Tomate)",
        stage="Desenvolvimento",
        root_depth_cm=25.0,
        kc=1.05,
        h1=-10.0,
        h2=-20.0,
        h3=-300.0,
        h4=-5000.0
    )
}

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

