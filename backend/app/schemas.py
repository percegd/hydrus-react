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


class SimulateRequest(BaseModel):
    soil_key: str = Field(examples=["latossolo_medio"])
    crop_key: Optional[str] = Field(default="soja", examples=["soja"])
    depth_cm: float = Field(default=200.0, gt=0, le=300)
    root_depth_cm: Optional[float] = Field(default=None, gt=0)
    total_days: float = Field(default=30.0, gt=0, le=730)
    rain_mm: float = Field(default=100.0, ge=0)
    initial_moisture_pct: float = Field(default=20.0, ge=0, le=100)
    et0_mm_day: float = Field(default=4.0, ge=0)
    solutes: list[SoluteInput] = Field(min_length=1)


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
