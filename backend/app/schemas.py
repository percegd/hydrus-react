"""Schemas da API — espelham os inputs do wizard, sem acoplamento com UI."""

from typing import Optional

from pydantic import BaseModel, Field


class SoluteInput(BaseModel):
    symbol: str = Field(examples=["K"])
    name: str = Field(examples=["Potássio"])
    dose_kg_ha: float = Field(ge=0, examples=[30.0])
    kd: float = Field(ge=0, examples=[0.45])
    initial_residual_mg_dm3: float = Field(default=0.0, ge=0)
    dispersivity_cm: float = Field(default=20.0, gt=0)
    release_type: str = Field(default="immediate", examples=["immediate"])
    release_days: float = Field(default=60.0, gt=0)


class PlacementInput(BaseModel):
    mode: str = Field(default="surface", examples=["surface"])
    z_top_cm: float = Field(default=0.0, ge=0)
    z_bottom_cm: float = Field(default=2.0, ge=0)
    fertigation_c0_mg_l: float = Field(default=20.0, ge=0)
    fertigation_pulse_days: float = Field(default=0.0, ge=0)
    application_day: float = Field(default=0.0, ge=0)


class CustomSoilInput(BaseModel):
    """Solo personalizado (Gradio is_custom_soil + Rosetta).

    sand_pct/clay_pct definem a granulometria (soma ≤ 100); os demais campos
    são overrides editáveis dos parâmetros de van Genuchten (ausente = valor
    estimado pela Rosetta via POST /soils/rosetta).
    """

    sand_pct: float = Field(examples=[60.0])
    clay_pct: float = Field(examples=[25.0])
    bulk_density: Optional[float] = Field(default=None, examples=[1.3])
    theta_r: Optional[float] = Field(default=None, examples=[0.1])
    theta_s: Optional[float] = Field(default=None, examples=[0.43])
    alpha: Optional[float] = Field(default=None, examples=[0.03])
    n: Optional[float] = Field(default=None, examples=[1.65])
    ks: Optional[float] = Field(default=None, examples=[80.0])


class RosettaRequest(BaseModel):
    sand_pct: float = Field(examples=[60.0])
    clay_pct: float = Field(examples=[25.0])
    bulk_density: Optional[float] = Field(default=None, examples=[1.3])


class RosettaResponse(BaseModel):
    theta_r: float
    theta_s: float
    alpha: float
    n: float
    ks: float
    bulk_density: float
    silt_pct: float
    texture: str


class FertilizerInfo(BaseModel):
    key: str
    label: str
    name: str
    nutrient_pcts: dict[str, float]
    descr: str = ""


class BlendPresetInfo(BaseModel):
    key: str
    label: str
    nutrient_pcts: dict[str, float]


class FertilizerDoseRequest(BaseModel):
    """Conversão dose bruta -> elementar (port de calculate_effective_dose).

    Uso comercial: fert_key + gross_dose (+ nutrient_symbol opcional p/ modo
    1-soluto com erro quando o adubo não contém o nutriente).
    Uso personalizado: custom_pcts (% N-P-K-S-Ca-Mg) ou blend_preset.
    """

    fert_key: Optional[str] = Field(default=None, examples=["kcl"])
    gross_dose: float = Field(ge=0, examples=[200.0])
    nutrient_symbol: Optional[str] = Field(default=None, examples=["K"])
    custom_pcts: Optional[dict[str, float]] = Field(
        default=None, description="% elementar por nutriente (N,P,K,S,Ca,Mg)"
    )
    blend_preset: Optional[str] = Field(default=None, examples=["NPK (blend)"])


class FertilizerDoseResponse(BaseModel):
    fert_key: str
    fert_name: str
    gross_dose: float
    nutrient_pcts: dict[str, float]
    elemental_doses: dict[str, float]
    message: str


class KdEntry(BaseModel):
    symbol: str
    kd: float
    citation: str
    description: str = ""
    texture: Optional[str] = None
    langmuir: Optional[dict] = None


class KdResponse(BaseModel):
    soil_key: Optional[str] = None
    sand_pct: Optional[float] = None
    clay_pct: Optional[float] = None
    texture: str
    entries: list[KdEntry]


class FertilizerUsed(BaseModel):
    fert_key: str = Field(examples=["kcl"])
    gross_dose: float = Field(ge=0, examples=[200.0])


class SimulateRequest(BaseModel):
    soil_key: Optional[str] = Field(default="latossolo_medio", examples=["latossolo_medio"])
    custom_soil: Optional[CustomSoilInput] = Field(default=None)
    crop_key: Optional[str] = Field(default="soja", examples=["soja"])
    # T13: cultura editável como no Gradio (crop params box: nome editável,
    # profundidade radicular, Kc e limiares de Feddes h1..h4). Todos opcionais:
    # ausente = valor do banco para crop_key; crop_key="custom" = cultura
    # personalizada montada a partir destes campos.
    crop_name: Optional[str] = Field(default=None, examples=["Soja"])
    kc: Optional[float] = Field(default=None, examples=[1.0])
    h1: Optional[float] = Field(default=None, examples=[-15.0])
    h2: Optional[float] = Field(default=None, examples=[-30.0])
    h3: Optional[float] = Field(default=None, examples=[-450.0])
    h4: Optional[float] = Field(default=None, examples=[-12000.0])
    depth_cm: float = Field(default=200.0, gt=0, le=300)
    root_depth_cm: Optional[float] = Field(default=None, gt=0)
    total_days: float = Field(default=7.0, gt=0, le=730)
    rain_mm: float = Field(default=60.0, ge=0)
    rain_series: Optional[list[float]] = Field(
        default=None, description="Chuva diária em mm; se informada, define total_days"
    )
    initial_moisture_pct: float = Field(default=80.0, ge=0, le=100)
    et0_mm_day: float = Field(default=4.0, ge=0)
    et0_series: Optional[list[float]] = Field(default=None, description="ET0 diária em mm")
    # ET avançada (Gradio adv_et_toggle): 0 = derivar de ET0 (E = ET0 − T, T = ET0·Kc).
    evap_mm_day: float = Field(default=0.0, ge=0)
    transp_mm_day: float = Field(default=0.0, ge=0)
    placement: PlacementInput = Field(default_factory=PlacementInput)
    # T5: modo "Somente água" (Gradio simulation_mode): sem transporte de solutos.
    water_only: bool = Field(default=False)
    solutes: list[SoluteInput] = Field(default_factory=list)
    # T9: janela de análise + dias de leitura (Gradio defaults: 1, 365, "55, 128, 237, 365").
    # print_days=None = marcos automáticos do Gradio (proporcional à duração;
    # em 365 dias equivale a 55, 128, 237, 365).
    analysis_start_day: int = Field(default=1)
    analysis_end_day: int = Field(default=365)
    print_days: Optional[list[float]] = Field(
        default=None, description="Dias de leitura (ex: 55, 128, 237, 365)"
    )
    # Nós de observação [cm]: default do campo do Gradio "10, 20, 30, 50"
    # (em ambos os modos; filtrado pela profundidade do perfil no service).
    obs_depths_cm: Optional[list[float]] = Field(
        default=None, description="Nós de observação em cm (default Gradio: 10, 20, 30, 50)"
    )
    # Rótulo da fonte da série p/ o laudo sazonal (frontend envia o rótulo
    # exato do seletor + "(NASA POWER)"; default = série do polo).
    series_source_label: Optional[str] = Field(
        default="Série climática do polo (NASA POWER)"
    )
    # D) Etapa 1 do passo a passo: adubo comercial que originou as doses
    # (enviado só quando a tabela não foi editada após o modal).
    fertilizer: Optional[FertilizerUsed] = Field(default=None)


class JobCreated(BaseModel):
    job_id: str


class SoluteBalance(BaseModel):
    symbol: str
    name: str
    dose_kg_ha: float
    retained_root_pct: float
    below_profile_pct: float
    bottom_pct: float
    uptaken_pct: float
    peak_depth_cm: Optional[float]
    dose_input_kg_ha: float = 0.0
    is_fertigation: bool = False
    capsule_pct: float = 0.0


class WaterBalance(BaseModel):
    """Balanço hídrico do período (presente em todas as corridas).

    Rótulos dinâmicos iguais aos do Gradio (Lâmina Aplicada / Chuva Anual Total
    / Chuva no Período; Drenagem no Fundo / Drenagem Anual / Drenagem no Período).
    """

    applied_mm: float
    drainage_mm: float
    storage_mm: float
    runoff_mm: float
    evap_mm: Optional[float] = None
    transp_mm: Optional[float] = None
    applied_label: str = "Lâmina Aplicada"
    drainage_label: str = "Drenagem no Fundo"


class ExtraPlot(BaseModel):
    """Gráfico extra nomeado (galeria completa como no Gradio).

    Jobs assíncronos retornam {key, title, url} (lazy, sem base64);
    /simulate síncrono continua embutindo png_base64.
    """

    key: str
    title: str
    png_base64: Optional[str] = None
    url: Optional[str] = None


class ScreenGalleryItem(BaseModel):
    """Item da galeria Por Soluto da tela de resultados (mesmo gráfico do Gradio)."""

    symbol: str
    name: str
    url: str


class ScreenImages(BaseModel):
    """Imagens estáticas da tela de Resultados (matplotlib, iguais às do Gradio).

    Cada campo guarda a URL relativa do PNG servido pelo backend
    (/jobs/{job_id}/tela/{nome}.png); None = o gráfico não foi gerado.
    """

    perfil: Optional[str] = None
    btc: Optional[str] = None
    evolucao: Optional[str] = None
    galeria: list[ScreenGalleryItem] = Field(default_factory=list)


class SimulateResponse(BaseModel):
    drainage_mm: float
    solutes: list[SoluteBalance]
    plot_png_base64: Optional[str] = None
    plots_png_base64: Optional[dict[str, str]] = None
    extra_plots: list[ExtraPlot] = Field(default_factory=list)
    profiles: Optional[dict] = None
    water_only: bool = False
    water_balance: Optional[WaterBalance] = None
    screen: Optional[ScreenImages] = None


class StepsResponse(BaseModel):
    steps_markdown: str


class HelpEntry(BaseModel):
    key: str
    title: str
    unit: str
    what: str
    simulation: str


class JobStatus(BaseModel):
    job_id: str
    status: str  # queued | running | failed
    elapsed_s: float
    result: Optional[SimulateResponse] = None
    error: Optional[str] = None
    has_excel: bool = False
    has_report: bool = False
    has_graphs: bool = False
    has_steps: bool = False
