"""Solo nu: a planilha marca o que é da cultura, e o gráfico de fluxos omite a série."""

from types import SimpleNamespace

import matplotlib.pyplot as plt
import numpy as np
from openpyxl import load_workbook

from hydrus_core.export_excel import export_soil_profile_excel
from hydrus_core.visualizer import plot_hydrus_cumflux


def _results():
    z = np.linspace(0, 10, 11)
    theta = np.full_like(z, 0.3)
    return SimpleNamespace(
        z=z,
        theta_profiles=[theta, theta],
        n_profiles=[],
        nutrient_results={
            "K": {
                "dose_kg_ha": 30.0,
                "retained_root_pct": 99.0,
                "leaching_ratio_pct": 1.0,
                "uptaken_pct": 0.0,
                "capsule_pct": 0.0,
                "input_kg_ha": 30.0,
                "residual_kg_ha": 0.0,
                "final_profile": theta,
            }
        },
        print_profiles={},
        obs_times_days=[],
        obs_depths_cm=[],
        obs_c_series={},
        obs_theta_series={},
        flux_times_days=[0.0, 1.0, 2.0],
        cum_infil_cm=[0.0, 1.0, 2.0],
        cum_evap_series_cm=[0.0, 0.4, 0.8],
        cum_transp_series_cm=[0.0, 0.0, 0.0],
        cum_bottom_series_cm=[0.0, 0.1, 0.2],
        peak_depth_cm=float("nan"),
    )


def _params(has_crop: bool):
    return {
        "water_only": False,
        "has_crop": has_crop,
        "nutrient_symbol": "K",
        "nutrient_label": "Potássio",
        "uptaken_pct": 0.0,
        "transp_mm": 0.0,
        "evap_mm": 12.0,
        "nutrient_results": _results().nutrient_results,
    }


def _summary(path):
    sheet = load_workbook(path)["Parametros_e_Balanco"]
    return {row[0].value: row[1].value for row in sheet.rows}


def test_bare_soil_excel_marks_crop_items_and_keeps_flux_series(tmp_path):
    path = tmp_path / "nu.xlsx"
    export_soil_profile_excel(_results(), str(path), _params(False))
    vals = _summary(path)
    assert vals["Transpiração [mm]"] == "não se aplica"
    assert vals["Absorção pela Cultura [%] (limitada pela demanda)"] == "não se aplica"
    assert vals["Evaporação [mm]"] == 12.0
    headers = [c.value for c in next(load_workbook(path)["Fluxos_Acumulados"].rows)]
    assert "Transpiração acumulada [mm]" in headers


def test_crop_with_zero_transpiration_stays_numeric(tmp_path):
    path = tmp_path / "cultura.xlsx"
    export_soil_profile_excel(_results(), str(path), _params(True))
    vals = _summary(path)
    assert vals["Transpiração [mm]"] == 0
    assert vals["Absorção pela Cultura [%] (limitada pela demanda)"] == 0


def test_cumflux_legend_follows_crop_flag(tmp_path, monkeypatch):
    seen = {}
    real = plt.Figure.savefig

    def grab(self, *args, **kwargs):
        leg = self.axes[0].get_legend()
        seen["labels"] = [t.get_text() for t in leg.get_texts()] if leg else []
        return real(self, *args, **kwargs)

    monkeypatch.setattr(plt.Figure, "savefig", grab)
    plot_hydrus_cumflux(_results(), str(tmp_path / "sem.png"), show_transpiration=False)
    assert "Transpiração" not in seen["labels"]
    assert "Evaporação" in seen["labels"]
    assert "Infiltração" in seen["labels"]
    plot_hydrus_cumflux(_results(), str(tmp_path / "com.png"), show_transpiration=True)
    assert "Transpiração" in seen["labels"]
