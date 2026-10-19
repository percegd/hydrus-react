"""
HYDRUS-1D File Generator: Exports simulation scenarios to HYDRUS-1D input files
(SELECTOR.IN, ATMOSPH.IN, PROFILE.DAT) in the official file format (v4.17),
so they can be opened/validated in the official HYDRUS-1D GUI.

Formato de referência: HYDRUS-1D (Šimůnek et al.), arquivos de exemplo do
código-fonte oficial. Blocos: A (basic) → B (water flow) → C (time) →
F (solute transport) → G (root water uptake).
"""

import os
from typing import List, Tuple, Optional, Union, Dict
import numpy as np
from hydrus_core.soil_physics import SoilParameters
from hydrus_core.crop import CropParameters


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
    evap_cm_day: float = 0.0,             # Evaporação potencial do solo [cm/dia] (rSoil)
    transpiration_cm_day: float = 0.0,    # Transpiração potencial [cm/dia] (rRoot)
    nutrient_specs: Optional[List[Dict]] = None, # Lista de nutrientes ativos (documentação)
    application_mechanism: str = "",       # Mecanismo de aplicação (documentação)
    print_days: Optional[List[float]] = None, # Dias de impressão (TPrint) [dias]
    ctop_mg_cm3: float = 0.0,              # Concentração de entrada no topo (cTop) [mg/cm3]
    pulse_days: float = 0.0                # Duração do pulso (tPulse) [dias]
):
    """Gera SELECTOR.IN, ATMOSPH.IN e PROFILE.DAT no formato oficial do HYDRUS-1D."""
    if water_events is None:
        water_events = []
    os.makedirs(project_dir, exist_ok=True)
    nz = int(depth_cm / dz) + 1
    z_nodes = np.linspace(0.0, depth_cm, nz)

    crop_title = crop.name if crop else "Coluna de Solo (Solo Nu)"
    h1 = crop.h1 if crop else -10.0
    h2 = crop.h2 if crop else -25.0
    h3 = crop.h3 if crop else -400.0
    l_sink = "t" if crop else "f"

    # Nós de observação
    target_obs = obs_depths_cm or [10.0, 20.0, 30.0, 50.0]
    obs_indices = []
    for d in target_obs:
        if 0.0 <= float(d) <= depth_cm:
            node_idx = int(np.clip(round(float(d) / dz), 0, nz - 1)) + 1
            if node_idx not in obs_indices:
                obs_indices.append(node_idx)
    if not obs_indices:
        obs_indices = [1, min(nz, 11), nz]

    # Dias de impressão (TPrint)
    if print_days:
        tprint = sorted(set(float(d) for d in print_days if 0.0 < float(d) <= total_days))
    else:
        tprint = []
    if not tprint:
        tprint = [total_days]
    mpl = len(tprint)

    pulse = float(pulse_days) if pulse_days and pulse_days > 0 else float(total_days)

    # ------------------------------------------------------------------ SELECTOR.IN
    selector_path = os.path.join(project_dir, "SELECTOR.IN")
    with open(selector_path, "w") as f:
        f.write("*** BLOCK A: BASIC INFORMATION *****************************************\n")
        f.write("Heading\n")
        f.write(f"Simulacao - {crop_title} em {soil.name}\n")
        f.write("LUnit  TUnit  MUnit  (indicated units are obligatory for all input data)\n")
        f.write("cm\n")
        f.write("days\n")
        f.write("mg\n")
        f.write("lWat   lChem lTemp  lSink lRoot lShort lWDep lScreen lVariabBC lEquil lInverse\n")
        f.write(f" t     t     f      {l_sink}     f     f      f     f       t         t         f\n")
        f.write("NMat    NLay  CosAlpha\n")
        f.write("  1       1       1\n")

        f.write("*** BLOCK B: WATER FLOW INFORMATION ************************************\n")
        f.write("MaxIt   TolTh   TolH       (maximum number of iterations and tolerances)\n")
        f.write("  30    0.001    0.1\n")
        f.write("TopInf WLayer KodTop InitCond\n")
        f.write(" t     f      -1       f\n")
        f.write("BotInf qGWLF FreeD SeepF KodBot DrainF\n")
        f.write(" f     f     t     f     -1      f\n")
        f.write("    hTab1   hTabN\n")
        f.write("    1e-006   10000\n")
        f.write("    Model   Hysteresis\n")
        f.write("      0          0\n")
        f.write("   thr     ths    Alfa      n         Ks       l\n")
        f.write(f" {soil.theta_r:8.4f} {soil.theta_s:8.4f} {soil.alpha:8.4f} {soil.n:8.4f} {soil.ks:10.3f}     0.5\n")

        f.write("*** BLOCK C: TIME INFORMATION ******************************************\n")
        f.write("        dt       dtMin       dtMax     DMul    DMul2  ItMin ItMax  MPL\n")
        f.write(f"     1e-005      1e-005         0.5     1.3     0.7     3     7    {mpl:2d}\n")
        f.write("      tInit        tMax\n")
        f.write(f"          0      {total_days:8.1f}\n")
        f.write("TPrint(1),TPrint(2),...,TPrint(MPL)\n")
        f.write(" ".join(f"{t:11.2f}" for t in tprint) + "\n")

        f.write("*** BLOCK F: SOLUTE TRANSPORT INFORMATION ******************************\n")
        # Padrão HYDRUS-1D: N solutos independentes, cada um com o seu Kd (coluna "Ks").
        # A dispersividade (DisperL) é parâmetro do material de solo (NMat), compartilhada.
        specs = list(nutrient_specs or [])
        if not specs:
            specs = [{"symbol": "Soluto 1", "kd": float(kd)}]
        nsol = max(1, len(specs))

        f.write(" Epsi  lUpW  lArtD lTDep    cTolA    cTolR   MaxItC    PeCr  No.Solutes  lTort\n")
        f.write(f"  1.0     t     f     f      0.001    0.001    30       2      {nsol:5d}        t\n")
        f.write("     Bulk.d.     DisperL.      Frac      Mobile WC (1..NMat)\n")
        f.write(f"       {soil.bulk_density:8.3f}  {dispersivity_cm:10.3f}       1.0        0\n")
        f.write("         DifW       DifG                n-th solute\n")
        for _ in range(nsol):
            f.write("          1.0        0.0\n")
        f.write("         Ks          Nu        Beta       Henry       SnkL1       SnkS1       SnkG1       SnkL1'      SnkS1'      SnkG1'      SnkL0       SnkS0       SnkG0        Alfa\n")
        for _sp in specs:
            _kd_sol = float(_sp.get("kd", kd) or 0.0)
            f.write(f"  {_kd_sol:10.4f}           0           1           0           0           0           0           0           0           0           0           0           0           0\n")
        f.write("      kTopSolute  SolTop    kBotSolute  SolBot\n")
        for _ in range(nsol):
            f.write(f"         -1     {ctop_mg_cm3:10.5f}           0           0\n")
        f.write("      tPulse\n")
        f.write(f"      {pulse:8.1f}\n")

        if crop:
            f.write("*** BLOCK G: ROOT WATER UPTAKE INFORMATION *****************************\n")
            f.write("     Model  (0 - Feddes, 1 - S shape)  cRootMax\n")
            f.write("        0                               1e+030\n")
            f.write("       P0       P2H       P2L       P3          r2H        r2L\n")
            f.write(f"  {h1:8.1f} {h2:9.1f} {h2:9.1f} {h3:9.1f}         0.5         0.1\n")
            f.write("POptm(1),POptm(2),...,POptm(NMat)\n")
            f.write("     -25\n")
            f.write("     Solute Reduction\n")
            f.write("        f\n")

        f.write("*** END OF INPUT FILE 'SELECTOR.IN' ************************************\n")

    # OBS_NODES.txt (auxiliar legível)
    obs_file = os.path.join(project_dir, "OBS_NODES.txt")
    with open(obs_file, "w") as f:
        f.write("Nós de Observação do Perfil (HYDRUS-1D):\n")
        for rank, n_i in enumerate(obs_indices, start=1):
            z_prof = (n_i - 1) * dz
            f.write(f"Ponto {rank:2d}: Nó {n_i:4d} | Profundidade: {z_prof:6.1f} cm\n")

    # ------------------------------------------------------------------ PROFILE.DAT
    profile_path = os.path.join(project_dir, "PROFILE.DAT")
    if crop:
        from hydrus_core.crop import root_distribution
        beta_vals = root_distribution(z_nodes, crop.root_depth_cm)
    else:
        beta_vals = np.zeros(nz)

    pm = str(placement_mode).lower().strip()
    if pm == "furrow":
        z_top, z_bot = 5.0, 10.0
    elif pm == "custom":
        z_top = min(float(z_app_top_cm), float(z_app_bottom_cm))
        z_bot = max(float(z_app_top_cm), float(z_app_bottom_cm))
    else:  # "surface"
        z_top, z_bot = 0.0, 2.0

    node_mask = (z_nodes >= (z_top - 1e-6)) & (z_nodes <= (z_bot + 1e-6))
    app_nodes = np.where(node_mask)[0]
    if len(app_nodes) == 0:
        z_mid = 0.5 * (z_top + z_bot)
        app_nodes = np.sort(np.argsort(np.abs(z_nodes - z_mid))[:2])

    conc_prof = np.zeros(nz)
    if isinstance(initial_residual_mg_dm3, dict):
        res_val = float(initial_residual_mg_dm3.get("N", initial_residual_mg_dm3.get("default", 0.0)))
    else:
        try:
            res_val = float(initial_residual_mg_dm3)
        except (ValueError, TypeError):
            res_val = 0.0
    if res_val > 0.0:
        res_conc = res_val * 0.001  # mg/dm3 -> mg/cm3
        conc_prof[z_nodes <= (20.0 + 1e-6)] += res_conc

    applied_mass = float(fertilizer_kg_ha) * 0.01  # kg/ha -> mg/cm2
    if applied_mass > 0.0 and len(app_nodes) > 0:
        conc_prof[app_nodes] += applied_mass / (len(app_nodes) * dz)

    with open(profile_path, "w") as f:
        f.write("    1\n")                          # NMat
        f.write("    1  0.000000e+000  1.000000e+000  1.000000e+000\n")
        f.write(f"{nz:5d}    1    1    1 x         h         Mat  Lay      Beta           Axz            Bxz            Dxz            Temp          Conc           SConc\n")
        for i, z in enumerate(z_nodes):
            x_hydrus = -z
            h_init = -150.0
            beta = float(beta_vals[i])
            conc = float(conc_prof[i])
            f.write(f"{i+1:5d}  {x_hydrus:12.4e}  {h_init:12.4e}    1    1  {beta:12.6e}  {1.0:12.6e}  {1.0:12.6e}  {1.0:12.6e}  {20.0:12.6e}  {conc:12.6e}  {0.0:12.6e}\n")
        f.write(f"{len(obs_indices):5d}\n")
        f.write(" ".join(f"{idx:5d}" for idx in obs_indices) + "\n")

    # ------------------------------------------------------------------ ATMOSPH.IN
    atmosph_path = os.path.join(project_dir, "ATMOSPH.IN")
    n_records = max(1, int(round(total_days)))
    with open(atmosph_path, "w") as f:
        f.write("*** BLOCK I: ATMOSPHERIC INFORMATION  **********************************\n")
        f.write("   MaxAL                    (MaxAL = number of atmospheric data-records)\n")
        f.write(f"   {n_records}\n")
        f.write(" hCritS                 (max. allowed pressure head at the soil surface)\n")
        f.write(" 1e+030\n")
        f.write("       tAtm        Prec       rSoil       rRoot      hCritA          rB          hB          ht        tTop        tBot        Ampl        cTop        cBot\n")
        for d in range(1, n_records + 1):
            t_start = float(d - 1)
            t_end = float(d)
            precip_cm_day = 0.0
            for start, dur, mm in water_events:
                overlap = max(0.0, min(start + dur, t_end) - max(start, t_start))
                if dur > 0.0:
                    frac = overlap / dur
                    precip_cm_day += (mm / 10.0) * frac / (t_end - t_start)
            f.write(f"  {t_end:10.2f}  {precip_cm_day:10.4f}  {float(evap_cm_day):10.4f}  "
                    f"{float(transpiration_cm_day):10.4f}  {10000.0:10.1f}      0.0000      0.0000      0.0000"
                    f"      0.0000      0.0000      0.0000  {float(ctop_mg_cm3):10.5f}      0.0000\n")
        f.write("end*** END OF INPUT FILE 'ATMOSPH.IN' **********************************\n")

    return project_dir
