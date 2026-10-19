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


class SimulateRequest(BaseModel):
    soil_key: str = Field(examples=["latossolo_medio"])
    crop_key: Optional[str] = Field(default="soja", examples=["soja"])
    depth_cm: float = Field(default=200.0, gt=0, le=300)
    root_depth_cm: Optional[float] = Field(default=None, gt=0)
    total_days: float = Field(default=30.0, gt=0, le=730)
    rain_mm: float = Field(default=100.0, ge=0)
    rain_series: Optional[list[float]] = Field(
        default=None, description="Chuva diária em mm; se informada, define total_days"
    )
    initial_moisture_pct: float = Field(default=20.0, ge=0, le=100)
    et0_mm_day: float = Field(default=4.0, ge=0)
    et0_series: Optional[list[float]] = Field(default=None, description="ET0 diária em mm")
    placement: PlacementInput = Field(default_factory=PlacementInput)
    solutes: list[SoluteInput] = Field(min_length=1)


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


class SimulateResponse(BaseModel):
    drainage_mm: float
    solutes: list[SoluteBalance]
    plot_png_base64: Optional[str] = None
    plots_png_base64: Optional[dict[str, str]] = None
    profiles: Optional[dict] = None


class JobStatus(BaseModel):
    job_id: str
    status: str  # queued | running | done | failed
    elapsed_s: float
    result: Optional[SimulateResponse] = None
    error: Optional[str] = None
    has_excel: bool = False
    has_report: bool = False
