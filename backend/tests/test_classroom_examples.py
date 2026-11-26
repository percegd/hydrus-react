"""Exemplos de aula HYDRUS-1D montados pelo schema (não pelo exportador).

A) infiltração empoçada, 1 h, carga h=0.
B) fluxo constante + K a 10 mg/L, 3 h.
O caminho padrão (dias, BC atmosférica, Δz=1 cm, umidade em %) permanece o anterior.
"""

import os

import numpy as np

from app.schemas import PlacementInput, ProfilePoint, SimulateRequest, SoluteInput
from app.service import _run_core, write_hydrus_project
from app.validation import validate_request


def _sand_common(**extra):
    base = dict(
        soil_key="areia_carsel",
        crop_key=None,
        depth_cm=70,
        dz_cm=0.7,
        n_nodes=101,
        time_unit="hours",
        ic_mode="head",
        initial_head_cm=-100.0,
        rain_mm=0,
        et0_mm_day=0,
        obs_depths_cm=[7, 14, 21, 28, 35, 42, 49, 56, 63, 70],
        placement=PlacementInput(mode="surface"),
    )
    base.update(extra)
    return SimulateRequest(**base)


def test_cenario_a_infiltracao_empocada():
    req = _sand_common(
        total_days=1,
        top_bc="head",
        h_top_cm=0.0,
        water_only=True,
        print_days=[0.2, 0.4, 0.6, 0.8, 1.0],
        solutes=[],
    )
    assert validate_request(req) == []
    res, *_ = _run_core(req)
    rows = {round(t * 24.0, 1): i for i, t in enumerate(res.level_times_days)}
    ref = {
        0.0: dict(V=3.59, qT=None, h=-99.5),
        0.2: dict(V=11.417, qT=-31.377),
        0.4: dict(V=17.549, qT=-30.249),
        0.6: dict(V=23.565, qT=-29.960),
        0.8: dict(V=29.544, qT=-29.847),
        1.0: dict(V=30.100, qT=-29.700, qB=-29.700, h=0.0),
    }
    for t, exp in ref.items():
        i = rows[t]
        vol = res.level_volume_cm[i]
        assert abs(vol - exp["V"]) / exp["V"] <= 0.02, (t, vol, exp["V"])
        qt = res.level_q_top_cm_day[i]
        if exp["qT"] is not None and t >= 0.4:
            got = -qt / 24.0
            assert abs(got - exp["qT"]) / abs(exp["qT"]) <= 0.03, (t, got)
    i1 = rows[1.0]
    assert abs(res.level_h_mean_cm[i1]) < 0.05
    assert abs(-res.level_q_bot_cm_day[i1] / 24.0 - (-29.7)) / 29.7 <= 0.03
    infil = res.level_infil_cum_cm[i1]
    drain = res.level_drain_cum_cm[i1]
    assert abs(infil - 31.895) / 31.895 <= 0.03, infil
    assert abs(drain - 5.3854) / 5.3854 <= 0.10, drain
    # Perfil saturado: θ = θs.
    assert abs(float(np.mean(res.theta_profiles[-1])) - 0.43) < 1e-3


def test_cenario_b_pulso_de_potassio():
    def _run(kd):
        req = _sand_common(
            total_days=3,
            top_bc="flux",
            flux_top=1.0 / 24.0,
            water_only=False,
            diffusion_cm2_day=0.0,
            print_days=[1, 2, 3],
            conc_unit="mg_l",
            molar_mass_g_mol=39.0983,
            solutes=[SoluteInput(
                symbol="K", name="Potássio", dose_kg_ha=0, kd=kd,
                dispersivity_cm=7, inlet_conc=10,
            )],
        )
        assert validate_request(req) == []
        res, soil, *_ = _run_core(req)
        return res, soil

    res0, soil = _run(0.0)
    assert soil.bulk_density == 1.5
    info = res0.nutrient_results["K"]
    assert abs(info["mass_closure_pct"]) < 1.0
    # q = 1 cm/d, C = 10 mg/L = 0,01 mg/cm³, t = 0,125 d → 0,125 kg/ha.
    expected = 1.0 * 0.01 * (3.0 / 24.0) * 100.0
    assert abs(info["applied_kg_ha"] - expected) / expected < 0.01
    com = []
    z = np.asarray(res0.z)
    for t in sorted(res0.print_profiles):
        c = np.asarray(res0.print_profiles[t]["c_total"]["K"], dtype=float)
        com.append(float(np.sum(c * z) / np.sum(c)))
    assert com[0] < com[1] < com[2]

    res_kd, _ = _run(0.5)
    info_kd = res_kd.nutrient_results["K"]
    assert abs(info_kd["mass_closure_pct"]) < 1.0
    com_kd = []
    for t in sorted(res_kd.print_profiles):
        c = np.asarray(res_kd.print_profiles[t]["c_total"]["K"], dtype=float)
        com_kd.append(float(np.sum(c * z) / np.sum(c)))
    # Kd>0 retarda: o centro de massa fica mais raso.
    assert com_kd[-1] < com[-1] * 0.7


def test_padrao_atmosferico_nao_muda():
    req = SimulateRequest(
        soil_key="latossolo_medio",
        crop_key="soja",
        total_days=7,
        rain_mm=40,
        initial_moisture_pct=80,
        et0_mm_day=4,
        time_unit="days",
        top_bc="atmospheric",
        ic_mode="moisture",
        dz_cm=1.0,
        solutes=[SoluteInput(symbol="K", name="Potássio", dose_kg_ha=30, kd=0.45, dispersivity_cm=8)],
        placement=PlacementInput(mode="surface"),
        print_days=[3, 7],
    )
    res, *_ = _run_core(req)
    k = res.nutrient_results["K"]
    assert abs(res.q_bottom_cum_cm - 0.10381879) < 1e-6
    assert abs(res.transp_cum_cm - 2.7157894) < 1e-5
    assert abs(k["retained_profile_pct"] - 86.4321063) < 1e-4
    assert len(res.z) == 201


def test_tabela_de_h_interpola_e_exporta(tmp_path):
    req = _sand_common(
        total_days=0.2,
        top_bc="head",
        h_top_cm=0.0,
        water_only=True,
        ic_mode="table",
        initial_head_cm=None,
        initial_profile_kind="h",
        initial_profile=[
            ProfilePoint(depth_cm=0, value=-80),
            ProfilePoint(depth_cm=70, value=-120),
        ],
        print_days=[0.2],
        solutes=[],
    )
    assert validate_request(req) == []
    res, soil, *_ = _run_core(req)
    # Interpolação linear: meio do perfil em -100 cm. A BC põe o topo em 0.
    assert abs(float(res.h_profiles[0][len(res.z) // 2]) - (-100.0)) < 1.0
    assert abs(float(res.h_profiles[0][0])) < 1e-6
    out = write_hydrus_project(req, soil, None, res.times_days[-1] and (0.2 / 24.0), str(tmp_path))
    selector = open(os.path.join(out, "SELECTOR.IN"), encoding="utf-8").read()
    assert "\nhours\n" in selector
    assert "f     f       1       f" in selector
    assert "29.700" in selector
    prof = open(os.path.join(out, "PROFILE.DAT"), encoding="utf-8").read().splitlines()
    # Nó da superfície guarda o h da tabela (−80 cm), não o da BC.
    assert "-8.0000e+01" in prof[4]


def test_exportador_mmol_e_fluxo(tmp_path):
    from hydrus_core.soil_physics import SOIL_DATABASE

    req = _sand_common(
        total_days=3,
        top_bc="flux",
        flux_top=1.0 / 24.0,
        water_only=False,
        diffusion_cm2_day=0.0,
        print_days=[3],
        conc_unit="mmol_l",
        molar_mass_g_mol=39.0983,
        solutes=[SoluteInput(
            symbol="K", name="Potássio", dose_kg_ha=0, kd=0,
            dispersivity_cm=7, inlet_conc=0.2557,
        )],
    )
    soil = SOIL_DATABASE["areia_carsel"]
    out = write_hydrus_project(req, soil, None, 3.0 / 24.0, str(tmp_path))
    selector = open(os.path.join(out, "SELECTOR.IN"), encoding="utf-8").read()
    assert "\nhours\n" in selector
    assert "\nmmol\n" in selector
    assert "f     f      -1       f" in selector
    atmos = open(os.path.join(out, "ATMOSPH.IN"), encoding="utf-8").read()
    # 0,2557 mmol/L = 0,0002557 mmol/cm³.
    assert "0.00026" in atmos or "0.0002557" in atmos