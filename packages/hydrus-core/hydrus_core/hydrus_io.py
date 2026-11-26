"""
HYDRUS-1D File Generator: Exports simulation scenarios to HYDRUS-1D input files
(SELECTOR.IN, ATMOSPH.IN, PROFILE.DAT) in the official file format (v4.17),
so they can be opened/validated in the official HYDRUS-1D GUI.

O arquivo descreve o mesmo cenário do formulário: Feddes (P0=h1, POptm=h2,
P2H=P2L=h3, P3=h4), h inicial da umidade pedida, Conc na fase líquida e
rRoot/rSoil iguais à partição potencial do solver.
"""

import os
from typing import List, Tuple, Optional, Union, Dict
import numpy as np
from hydrus_core.soil_physics import (
    SoilParameters,
    matric_head_from_theta,
    water_content_from_h,
)
from hydrus_core.crop import CropParameters, root_distribution
from hydrus_core.surface_bc import potential_partition_cm


def _initial_state(soil: SoilParameters, moisture_pct: float):
    """Mesma condição inicial do solver: fração do intervalo θr+0,01 → θ(h=-150)."""
    theta_fc = float(water_content_from_h(np.array([-150.0]), soil)[0])
    th_min = float(soil.theta_r) + 0.01
    frac = float(np.clip(float(moisture_pct) / 100.0, 0.0, 1.0))
    theta_val = th_min + max(0.005, theta_fc - th_min) * frac
    theta = float(np.clip(theta_val, th_min, float(soil.theta_s) - 0.02))
    h = float(matric_head_from_theta(np.array([theta]), soil)[0])
    return theta, h


def _nodal_width_cm(i: int, nz: int, dz: float) -> float:
    """Largura nodal do HYDRUS-1D [cm].

    Meia célula nas extremidades do perfil (i = 0 e i = nz-1); célula inteira
    no interior. O nó no fim de uma camada de adubo que não é o fundo do
    perfil (ex.: −2 cm com dz = 1) entra com dz, não com dz/2.
    """
    step = float(dz)
    if nz <= 1:
        return step
    if i == 0 or i == nz - 1:
        return 0.5 * step
    return step


def _placement_bounds(placement_mode: str, z_top: float, z_bot: float):
    pm = str(placement_mode or "surface").lower().strip()
    if pm == "furrow":
        return 5.0, 10.0
    if pm == "custom":
        return min(float(z_top), float(z_bot)), max(float(z_top), float(z_bot))
    if pm == "fertigation":
        return None, None
    return 0.0, 2.0


def export_to_hydrus1d_project(
    project_dir: str,
    soil: SoilParameters,
    crop: Optional[CropParameters] = None,
    fertilizer_kg_ha: float = 0.0,
    water_events: List[Tuple[float, float, float]] = None,
    total_days: float = 7.0,
    depth_cm: float = 100.0,
    dz: float = 1.0,
    kd: float = 0.0,
    dispersivity_cm: float = 5.0,
    placement_mode: str = "surface",
    z_app_top_cm: float = 0.0,
    z_app_bottom_cm: float = 2.0,
    initial_residual_mg_dm3: Union[float, Dict[str, float]] = 0.0,
    obs_depths_cm: Optional[List[float]] = None,
    evap_cm_day: float = 0.0,
    transpiration_cm_day: float = 0.0,
    nutrient_specs: Optional[List[Dict]] = None,
    application_mechanism: str = "",
    print_days: Optional[List[float]] = None,
    ctop_mg_cm3: float = 0.0,
    pulse_days: float = 0.0,
    initial_moisture_pct: float = 100.0,
    et0_mm_day: Union[float, List[float]] = 4.0,
    use_dual_kc: bool = False,
    growing_root: bool = False,
    bare_after_harvest: bool = False,
    crop_schedule: Optional[dict] = None,
    application_day: float = 0.0,
    water_only: bool = False,
    top_bc: str = "atmospheric",
    h_top_cm: Optional[float] = None,
    flux_top_cm_day: Optional[float] = None,
    time_unit: str = "days",
    mass_unit: str = "mg",
    initial_head_cm: Optional[float] = None,
    initial_head_profile: Optional[List[Tuple[float, float]]] = None,
    c_top: Optional[float] = None,
):
    """Gera SELECTOR.IN, ATMOSPH.IN e PROFILE.DAT no formato oficial do HYDRUS-1D.

    ``evap_cm_day`` / ``transpiration_cm_day`` > 0 substituem a partição
    (ET avançado). Caso contrário, rRoot/rSoil seguem ``potential_partition_cm``.
    """
    if water_events is None:
        water_events = []
    os.makedirs(project_dir, exist_ok=True)
    nz = int(round(float(depth_cm) / float(dz))) + 1
    z_nodes = np.linspace(0.0, float(depth_cm), nz)
    theta0, h_init = _initial_state(soil, initial_moisture_pct)
    bc = str(top_bc or "atmospheric").strip().lower()
    if bc in ("head", "pressure", "dirichlet", "carga"):
        bc = "head"
    elif bc in ("flux", "neumann", "fluxo"):
        bc = "flux"
    else:
        bc = "atmospheric"
    unit = str(time_unit or "days").strip().lower()
    if unit in ("h", "hour", "hours"):
        unit = "hours"
    elif unit in ("min", "minute", "minutes"):
        unit = "minutes"
    else:
        unit = "days"
    t_scale = {"days": 1.0, "hours": 24.0, "minutes": 1440.0}[unit]
    t_name = {"days": "days", "hours": "hours", "minutes": "min"}[unit]
    m_name = "mmol" if str(mass_unit or "mg").strip().lower().startswith("mmol") else "mg"

    crop_title = crop.name if crop else "Coluna de Solo (Solo Nu)"
    h1 = float(crop.h1) if crop else -10.0
    h2 = float(crop.h2) if crop else -25.0
    h3 = float(crop.h3) if crop else -400.0
    h4 = float(crop.h4) if crop else -15000.0
    l_sink = "t" if crop else "f"
    l_root = "t" if (crop and growing_root) else "f"
    l_chem = "f" if water_only else "t"

    specs = [dict(s) for s in (nutrient_specs or [])]
    if not specs and not water_only:
        specs = [{"symbol": "Soluto", "kd": float(kd), "dose_kg_ha": float(fertilizer_kg_ha)}]
    if water_only:
        specs = [{"symbol": "Soluto", "kd": 0.0, "dose_kg_ha": 0.0}]
    elif specs and fertilizer_kg_ha and not any(float(s.get("dose_kg_ha") or 0) > 0 for s in specs):
        specs[0]["dose_kg_ha"] = float(fertilizer_kg_ha)
    nsol = max(1, len(specs))

    target_obs = obs_depths_cm or [10.0, 20.0, 30.0, 50.0]
    obs_indices = []
    for d in target_obs:
        if 0.0 <= float(d) <= float(depth_cm):
            node_idx = int(np.clip(round(float(d) / float(dz)), 0, nz - 1)) + 1
            if node_idx not in obs_indices:
                obs_indices.append(node_idx)
    if not obs_indices:
        obs_indices = [1, min(nz, 11), nz]

    if print_days:
        tprint = sorted({float(d) for d in print_days if 0.0 < float(d) <= float(total_days) + 1e-9})
    else:
        tprint = []
    if not tprint:
        tprint = [float(total_days)]
    mpl = len(tprint)

    # ------------------------------------------------------------------ SELECTOR.IN
    selector_path = os.path.join(project_dir, "SELECTOR.IN")
    with open(selector_path, "w") as f:
        f.write("*** BLOCK A: BASIC INFORMATION *****************************************\n")
        f.write("Heading\n")
        f.write(f"Simulacao - {crop_title} em {soil.name}\n")
        f.write("LUnit  TUnit  MUnit  (indicated units are obligatory for all input data)\n")
        f.write("cm\n")
        f.write(f"{t_name}\n")
        f.write(f"{m_name}\n")
        f.write("lWat   lChem lTemp  lSink lRoot lShort lWDep lScreen lVariabBC lEquil lInverse\n")
        f.write(f" t     {l_chem}     f      {l_sink}     {l_root}     f      f     f       t         t         f\n")
        f.write("NMat    NLay  CosAlpha\n")
        f.write("  1       1       1\n")
        f.write("*** BLOCK B: WATER FLOW INFORMATION ************************************\n")
        f.write("MaxIt   TolTh   TolH       (maximum number of iterations and tolerances)\n")
        f.write("  20    0.001    0.1\n")
        f.write("TopInf WLayer KodTop InitCond\n")
        if bc == "head":
            # KodTop = +1: carga de pressão constante (Dirichlet).
            f.write(" f     f       1       f\n")
        elif bc == "flux":
            # KodTop = -1 com TopInf falso: fluxo constante (Neumann).
            f.write(" f     f      -1       f\n")
        else:
            f.write(" t     f      -1       f\n")
        f.write("BotInf qGWLF FreeD SeepF KodBot DrainF\n")
        f.write(" f     f     t     f     -1      f\n")
        f.write("    hTab1   hTabN\n")
        f.write("    0.001    10000\n")
        f.write("    Model   Hysteresis\n")
        f.write("      0          0\n")
        f.write("   thr     ths    Alfa      n         Ks       l\n")
        ks_out = float(soil.ks) / t_scale
        f.write(f" {soil.theta_r:8.4f} {soil.theta_s:8.4f} {soil.alpha:8.4f} {soil.n:8.4f} {ks_out:10.3f}     0.5\n")
        f.write("*** BLOCK C: TIME INFORMATION ******************************************\n")
        f.write("        dt       dtMin       dtMax     DMul    DMul2  ItMin ItMax  MPL\n")
        f.write(f"     0.001      1e-005         1.0     1.3     0.7     3     7    {mpl:2d}\n")
        f.write("      tInit        tMax\n")
        f.write(f"          0      {float(total_days) * t_scale:8.2f}\n")
        f.write("TPrint(1),TPrint(2),...,TPrint(MPL)\n")
        f.write(" ".join(f"{t * t_scale:11.2f}" for t in tprint) + "\n")
        f.write("*** BLOCK F: SOLUTE TRANSPORT INFORMATION ******************************\n")
        f.write(" Epsi  lUpW  lArtD lTDep    cTolA    cTolR   MaxItC    PeCr  No.Solutes  lTort\n")
        f.write(f"  0.5     f     f     f      0.001    0.001    20       2      {nsol:5d}        t\n")
        f.write("     Bulk.d.     DisperL.      Frac      Mobile WC (1..NMat)\n")
        f.write(f"       {soil.bulk_density:8.3f}  {float(dispersivity_cm):10.3f}       1.0        0\n")
        f.write("         DifW       DifG                n-th solute\n")
        for _ in range(nsol):
            f.write("       1.0000           0\n")
        f.write("         Ks          Nu        Beta       Henry       SnkL1       SnkS1       SnkG1       SnkL1'      SnkS1'      SnkG1'      SnkL0       SnkS0       SnkG0        Alfa\n")
        for sp in specs:
            f.write(f"  {float(sp.get('kd', kd) or 0.0):10.4f}           0           1           0           0           0           0           0           0           0           0           0           0           0\n")
        f.write("      kTopSolute  SolTop    kBotSolute  SolBot\n")
        for _ in range(nsol):
            f.write("         -1      0.00000           0           0\n")
        f.write("      tPulse\n")
        tpulse = float(pulse_days) if pulse_days and float(pulse_days) > 0 else float(total_days)
        f.write(f"      {tpulse:8.1f}\n")
        if crop:
            f.write("*** BLOCK G: ROOT WATER UPTAKE INFORMATION *****************************\n")
            f.write("     Model  (0 - Feddes, 1 - S shape)  cRootMax\n")
            f.write("        0                               1e+030\n")
            f.write("       P0       P2H       P2L       P3          r2H        r2L\n")
            # P0=h1, POptm=h2, P2H=P2L=h3, P3=h4 (manual HYDRUS-1D, Bloco G).
            f.write(f"  {h1:8.1f} {h3:9.1f} {h3:9.1f} {h4:9.1f}         0.5         0.1\n")
            f.write("POptm(1),POptm(2),...,POptm(NMat)\n")
            f.write(f"  {h2:8.1f}\n")
            f.write("     Solute Reduction\n")
            f.write("        f\n")
        f.write("*** END OF INPUT FILE 'SELECTOR.IN' ************************************\n")

    # ------------------------------------------------------------------ PROFILE.DAT
    if crop:
        root_cm = float(crop.root_depth_cm)
        beta_vals = root_distribution(z_nodes, root_cm)
    else:
        beta_vals = np.zeros(nz)

    z_top, z_bot = _placement_bounds(placement_mode, z_app_top_cm, z_app_bottom_cm)
    conc = np.zeros((nz, nsol))
    rho = float(soil.bulk_density)
    if z_top is not None:
        node_mask = (z_nodes >= (z_top - 1e-6)) & (z_nodes <= (z_bot + 1e-6))
        app_nodes = np.where(node_mask)[0]
        if len(app_nodes) == 0:
            z_mid = 0.5 * (z_top + z_bot)
            app_nodes = np.sort(np.argsort(np.abs(z_nodes - z_mid))[:2])
        # θ(h) que o HYDRUS-1D recalcula a partir do h escrito no PROFILE.
        theta_h = float(water_content_from_h(np.array([h_init]), soil)[0])
        widths = np.array([_nodal_width_cm(int(i), nz, dz) for i in app_nodes], dtype=float)
        for j, sp in enumerate(specs):
            dose = float(sp.get("dose_kg_ha") or 0.0)
            if j == 0 and dose <= 0:
                dose = float(fertilizer_kg_ha or 0.0)
            mass = dose * 0.01  # kg/ha -> mg/cm2
            kd_j = float(sp.get("kd", kd) or 0.0)
            if mass > 0 and len(app_nodes):
                ret = theta_h + rho * max(0.0, kd_j)
                # Conc uniforme na fase líquida: soma Conc·(θ+ρKd)·Δx_nodal = dose.
                c_liq = mass / max(ret * float(np.sum(widths)), 1e-12)
                conc[app_nodes, j] += c_liq
            res_raw = sp.get("initial_residual_mg_dm3", None)
            if res_raw is None:
                if isinstance(initial_residual_mg_dm3, dict):
                    res_raw = initial_residual_mg_dm3.get(str(sp.get("symbol")), 0.0)
                else:
                    res_raw = initial_residual_mg_dm3 if j == 0 else 0.0
            try:
                res_val = float(res_raw or 0.0)
            except (TypeError, ValueError):
                res_val = 0.0
            if res_val > 0:
                # O solver soma o residual em concentração total (mg/cm³ de solo).
                # O PROFILE.DAT guarda a fase líquida.
                c_bulk = res_val * 0.001
                c_liq = c_bulk / max(theta0 + rho * max(0.0, kd_j), 1e-8)
                conc[z_nodes <= 20.0 + 1e-6, j] += c_liq

    if initial_head_profile:
        pts = [(float(a), float(b)) for a, b in initial_head_profile]
        zd = np.array([p[0] for p in pts], dtype=float)
        vv = np.array([p[1] for p in pts], dtype=float)
        order = np.argsort(zd, kind="mergesort")
        zd, vv = zd[order], vv[order]
        h_nodes = np.interp(z_nodes, zd, vv)
    elif initial_head_cm is not None:
        h_nodes = np.full(nz, float(initial_head_cm))
    else:
        h_nodes = np.full(nz, h_init)

    profile_path = os.path.join(project_dir, "PROFILE.DAT")
    with open(profile_path, "w") as f:
        f.write("    2\n")
        f.write("    1  0.000000e+000  1.000000e+000  1.000000e+000\n")
        f.write(f"    2  {-float(depth_cm):14.6e}  1.000000e+000  1.000000e+000\n")
        f.write(f"{nz:5d}    1    1    1 x         h         Mat  Lay      Beta           Axz            Bxz            Dxz            Temp          Conc           SConc\n")
        for i, z in enumerate(z_nodes):
            conc_txt = "  ".join(f"{float(conc[i, j]):12.6e}" for j in range(nsol))
            sconc_txt = "  ".join(f"{0.0:12.6e}" for _ in range(nsol))
            f.write(
                f"{i+1:5d}  {-float(z):12.4e}  {float(h_nodes[i]):12.4e}    1    1  "
                f"{float(beta_vals[i]):12.6e}  {1.0:12.6e}  {1.0:12.6e}  {1.0:12.6e}  {20.0:12.6e}  {conc_txt}  {sconc_txt}\n"
            )
        f.write(f"{len(obs_indices):5d}\n")
        f.write(" ".join(f"{idx:5d}" for idx in obs_indices) + "\n")

    # ------------------------------------------------------------------ ATMOSPH.IN
    n_records = max(1, int(round(float(total_days))))
    et0_arr = np.atleast_1d(np.asarray(et0_mm_day, dtype=float)).ravel()
    use_evap = float(evap_cm_day or 0.0) > 0.0
    use_transp = float(transpiration_cm_day or 0.0) > 0.0
    is_fert = str(placement_mode).lower().strip() == "fertigation"
    app_day = float(application_day or 0.0)
    pulse = float(pulse_days) if pulse_days and float(pulse_days) > 0 else float(total_days)

    if bc != "atmospheric":
        n_records = 1
    atmosph_path = os.path.join(project_dir, "ATMOSPH.IN")
    with open(atmosph_path, "w") as f:
        f.write("*** BLOCK I: ATMOSPHERIC INFORMATION  **********************************\n")
        f.write("   MaxAL                    (MaxAL = number of atmospheric data-records)\n")
        f.write(f"   {n_records}\n")
        f.write(" hCritS                 (max. allowed pressure head at the soil surface)\n")
        f.write(" 1e+030\n")
        f.write("       tAtm        Prec       rSoil       rRoot      hCritA          rB          hB          ht        tTop        tBot        Ampl        cTop        cBot\n")
        if bc != "atmospheric":
            t_file = float(total_days) * t_scale
            precip_cm = 0.0
            ht = 0.0
            if bc == "flux" and flux_top_cm_day is not None:
                precip_cm = float(flux_top_cm_day) / t_scale
            if bc == "head" and h_top_cm is not None:
                ht = float(h_top_cm)
            c_vals = [float(c_top) if c_top is not None else 0.0 for _ in specs] or [0.0]
            c_txt = "  ".join(f"{c:10.5f}" for c in c_vals) + "  " + "  ".join("0.0000" for _ in c_vals)
            f.write(
                f"  {t_file:10.2f}  {precip_cm:10.4f}  {0.0:10.4f}  {0.0:10.4f}  "
                f"{10000.0:10.1f}      0.0000      0.0000  {ht:10.4f}"
                f"      20.000      20.000      0.0000  {c_txt}\n"
            )
        for d in range(1, n_records + 1) if bc == "atmospheric" else []:
            t_start = float(d - 1)
            t_end = float(d)
            precip_cm = 0.0
            for start, dur, mm in water_events:
                overlap = max(0.0, min(float(start) + float(dur), t_end) - max(float(start), t_start))
                if float(dur) > 0.0 and overlap > 0.0:
                    precip_cm += (float(mm) / 10.0) * (overlap / float(dur))
            et0 = float(et0_arr[min(d - 1, et0_arr.size - 1)]) if et0_arr.size else 0.0
            tp, ep = potential_partition_cm(
                crop, et0,
                use_dual_kc=bool(use_dual_kc),
                sched=crop_schedule,
                day_index=d - 1,
                bare_after_harvest=bool(bare_after_harvest),
            )
            r_soil = float(evap_cm_day) if use_evap else float(ep)
            r_root = (float(transpiration_cm_day) if use_transp else float(tp))
            ctops = []
            for sp in specs:
                c_top = 0.0
                if is_fert:
                    dose = float(sp.get("dose_kg_ha") or 0.0)
                    in_pulse = (t_end > app_day) and (t_start < app_day + pulse)
                    if in_pulse and precip_cm > 0 and dose > 0:
                        # mg/cm3 = (kg/ha * 0.01 mg/cm2) / cm de água no dia.
                        c_top = (dose * 0.01) / precip_cm
                    elif ctop_mg_cm3 and in_pulse:
                        c_top = float(ctop_mg_cm3)
                ctops.append(c_top)
            c_txt = "  ".join(f"{c:10.5f}" for c in ctops) + "  " + "  ".join("0.0000" for _ in ctops)
            f.write(
                f"  {t_end:10.2f}  {precip_cm:10.4f}  {r_soil:10.4f}  {r_root:10.4f}  "
                f"{10000.0:10.1f}      0.0000      0.0000      0.0000"
                f"      20.000      20.000      0.0000  {c_txt}\n"
            )
        f.write("end*** END OF INPUT FILE 'ATMOSPH.IN' **********************************\n")

    obs_file = os.path.join(project_dir, "OBS_NODES.txt")
    with open(obs_file, "w") as f:
        f.write("Nós de Observação do Perfil (HYDRUS-1D):\n")
        for rank, n_i in enumerate(obs_indices, start=1):
            z_prof = (n_i - 1) * float(dz)
            f.write(f"Ponto {rank:2d}: Nó {n_i:4d} | Profundidade: {z_prof:6.1f} cm\n")
        if application_mechanism:
            f.write(f"\n{application_mechanism}\n")
    return project_dir
