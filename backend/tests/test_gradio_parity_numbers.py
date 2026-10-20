"""Paridade numérica com o Gradio (sazonal Latossolo médio, Piracicaba ano médio).

Reproduz o cenário comparado via sim.run: série climática do polo
piracicaba_sp cenário "medio" (mesmo helper do endpoint /hubs/{key}/series),
solo latossolo_medio, sem cultura, depth 200, N (kd 0, disp 20) 30 kg/ha e
K (kd 0.45, disp 20) 30 kg/ha a lanço (surface 0–2), application_day 30,
print_days [55, 128, 237, 365], janela 1–365.
"""

from app.climate import build_series_rows
from app.schemas import PlacementInput, SimulateRequest, SoluteInput
from app.service import run_simulation


def test_gradio_parity_numbers_piracicaba_medio() -> None:
    rain, et0, _year = build_series_rows("piracicaba_sp", "medio")
    assert len(rain) == 365
    assert len(et0) == 365

    req = SimulateRequest(
        soil_key="latossolo_medio",
        crop_key=None,
        depth_cm=200.0,
        rain_series=list(rain),
        et0_series=list(et0),
        initial_moisture_pct=80.0,  # ignorado no sazonal (Gradio fixa 20.0)
        analysis_start_day=1,
        analysis_end_day=365,
        print_days=[55.0, 128.0, 237.0, 365.0],
        placement=PlacementInput(
            mode="surface",
            z_top_cm=0.0,
            z_bottom_cm=2.0,
            fertigation_c0_mg_l=20.0,  # ignorado fora de fertigation (paridade Gradio)
            fertigation_pulse_days=7.0,
            application_day=30.0,
        ),
        solutes=[
            SoluteInput(symbol="N", name="Nitrogênio", dose_kg_ha=30.0, kd=0.0, dispersivity_cm=20.0),
            SoluteInput(symbol="K", name="Potássio", dose_kg_ha=30.0, kd=0.45, dispersivity_cm=20.0),
        ],
    )

    resp = run_simulation(req, with_plot=False)

    assert abs(float(resp.drainage_mm) - 288.2) <= 0.5, resp.drainage_mm
    by_sym = {s.symbol: s for s in resp.solutes}
    assert abs(float(by_sym["N"].retained_root_pct) - 86.6) <= 0.5, by_sym["N"]
    assert abs(float(by_sym["K"].retained_root_pct) - 100.0) <= 0.5, by_sym["K"]
