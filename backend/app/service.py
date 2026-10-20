"""Camada de serviço: traduz request HTTP -> hydrus-core -> response.

Regras de domínio (as mesmas do app legado):
- camada avaliada = raiz da cultura, ou perfil todo sem cultura;
- balanço em 3 vias: retido 0–raiz / abaixo no perfil / fundo (+ absorvido).
- gráficos PNG estáticos gerados com hydrus_core.visualizer (matplotlib),
  mesmos argumentos do Gradio no modo correspondente (coluna/lâmina vs
  sazonal/série) — ver app_gradio.run_wizard_simulation.
"""

import base64
import math
import os
import zipfile

import matplotlib

matplotlib.use("Agg")

from hydrus_core.crop import CROP_DATABASE
from hydrus_core.hydrus_solver import Hydrus1DSimulator, SimulationConfig
from hydrus_core.soil_physics import SOIL_DATABASE
from hydrus_core.visualizer import (
    plot_breakthrough_curves,
    plot_nutrient_profile,
    plot_profiles_at_days,
    plot_water_profile,
)

from .schemas import GalleryImage, ResultImages, SimulateRequest, SimulateResponse, SoluteBalance


def _peak_or_none(value) -> float | None:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) else v


def _kd_eff_mean(raw, nominal: float) -> float:
    """Kd efetivo médio (mesma regra dos cartões do legado)."""
    try:
        import numpy as _npk

        if raw is None:
            return float(nominal)
        if isinstance(raw, (float, int)):
            return float(raw)
        try:
            return float(_npk.mean(_npk.asarray(raw, dtype=float)))
        except Exception:
            return float(nominal)
    except Exception:
        try:
            return float(nominal)
        except (TypeError, ValueError):
            return 0.0


def _safe_sym(sym: str) -> str:
    return "".join(ch if (ch.isalnum() or ch in ("_", "-")) else "_" for ch in str(sym))


def _default_print_days(total_days: float) -> list[float]:
    # Mesmos marcos do Gradio quando o campo vem vazio: coluna usa
    # (0.25, 0.5, 0.75, 1.0); série longa usa (0.15, 0.35, 0.65, 1.0).
    fracs = (0.15, 0.35, 0.65, 1.0) if float(total_days) >= 180 else (0.25, 0.5, 0.75, 1.0)
    return sorted({max(1.0, round(float(total_days) * f)) for f in fracs})


def _default_obs_depths(is_series: bool, depth_cm: float) -> list[float] | None:
    # Gradio, modo série: sorted({20, 50, 100, profundidade}); modo coluna:
    # None (solver usa o padrão da config).
    if not is_series:
        return None
    return sorted(set([20.0, 50.0, 100.0, float(depth_cm)]))


def _run_core(req: SimulateRequest):
    """Executa o solver uma vez; retorna (results, soil, crop, root_depth, total_rain, total_days)."""
    soil = SOIL_DATABASE[req.soil_key]
    crop = CROP_DATABASE.get(req.crop_key) if req.crop_key else None
    root_depth = float(crop.root_depth_cm) if crop else float(req.depth_cm)
    if req.root_depth_cm and crop:
        root_depth = float(req.root_depth_cm)

    _pmode = (req.placement.mode or "surface")
    _ztop, _zbot = float(req.placement.z_top_cm), float(req.placement.z_bottom_cm)
    if _pmode == "furrow":
        _ztop, _zbot = 5.0, 10.0
    elif _pmode == "fertigation":
        _ztop, _zbot = 0.0, 0.0
    nutrients = [
        {
            "symbol": s.symbol,
            "name": s.name,
            "dose_kg_ha": float(s.dose_kg_ha),
            "kd": float(s.kd),
            "initial_residual_mg_dm3": float(s.initial_residual_mg_dm3),
            "dispersivity_cm": float(s.dispersivity_cm),
            "release_type": (s.release_type or "immediate"),
            "release_days": float(s.release_days or 60.0),
            "placement_mode": _pmode,
            "z_app_top_cm": _ztop,
            "z_app_bottom_cm": _zbot,
            "fertigation_c0_mg_l": float(req.placement.fertigation_c0_mg_l),
            "fertigation_pulse_days": float(req.placement.fertigation_pulse_days),
        }
        for s in req.solutes
    ]
    is_series = bool(req.rain_series)
    if is_series:
        series = [max(0.0, float(v or 0.0)) for v in req.rain_series]
        total_days = float(len(series))
        water_events = [(float(d), 1.0, float(v)) for d, v in enumerate(series) if v > 0.0]
        total_rain = float(sum(series))
    else:
        total_days = float(req.total_days)
        per_day = float(req.rain_mm) / max(total_days, 1.0)
        water_events = [(float(d) + 0.5, 1.0, per_day) for d in range(int(total_days))]
        total_rain = float(req.rain_mm)

    cfg = SimulationConfig(
        depth_cm=float(req.depth_cm),
        dz=1.0,
        total_days=total_days,
        target_depth_cm=root_depth,
    )
    sim = Hydrus1DSimulator(soil=soil, crop=crop, config=cfg)
    results = sim.run(
        initial_moisture_pct=float(req.initial_moisture_pct),
        fertilizer_dose_kg_ha=sum(n["dose_kg_ha"] for n in nutrients),
        water_events=water_events,
        et0_mm_day=([max(0.0, float(v or 0.0)) for v in req.et0_series] if req.et0_series else float(req.et0_mm_day)),
        kd=float(nutrients[0]["kd"]),
        dispersivity_cm=float(nutrients[0]["dispersivity_cm"]),
        nutrients=nutrients,
        application_day=float(req.placement.application_day),
        obs_depths_cm=_default_obs_depths(is_series, float(req.depth_cm)),
        print_days=_default_print_days(total_days),
    )
    return results, soil, crop, root_depth, total_rain, total_days


def _balances(req: SimulateRequest, results) -> list[SoluteBalance]:
    out: list[SoluteBalance] = []
    for s in req.solutes:
        d = (results.nutrient_results.get(s.symbol) or {})
        leach = float(d.get("leaching_ratio_pct", 0.0) or 0.0)
        bottom = float(d.get("leached_bottom_pct", 0.0) or 0.0)
        try:
            _kd_nom = float(d.get("kd", float(s.kd)))
        except (TypeError, ValueError):
            _kd_nom = float(s.kd)
        out.append(
            SoluteBalance(
                symbol=s.symbol,
                name=s.name,
                dose_kg_ha=float(s.dose_kg_ha),
                retained_root_pct=float(d.get("retained_root_pct", 0.0) or 0.0),
                below_profile_pct=max(0.0, leach - bottom),
                bottom_pct=bottom,
                uptaken_pct=float(d.get("uptaken_pct", 0.0) or 0.0),
                peak_depth_cm=_peak_or_none(d.get("peak_depth_cm")),
                kd=_kd_nom,
                kd_eff=_kd_eff_mean(d.get("kd_eff", _kd_nom), _kd_nom),
                initial_residual_mg_dm3=float(s.initial_residual_mg_dm3),
                leaching_ratio_pct=leach,
            )
        )
    return out


def _storage_mm(results) -> float:
    """Δ armazenamento no perfil (θf − θi) em mm — mesma conta dos cartões."""
    try:
        import numpy as _np

        z_arr = _np.asarray(getattr(results, "z", []), dtype=float)
        if z_arr.size < 2:
            return 0.0
        d_z = float(z_arr[1] - z_arr[0])
        th = getattr(results, "theta_profiles", []) or []
        if len(th) < 2:
            return 0.0
        return float(_np.sum(_np.asarray(th[-1], dtype=float) - _np.asarray(th[0], dtype=float)) * d_z) * 10.0
    except Exception:
        return 0.0


def _z_max_cm(results, fallback: float) -> float:
    try:
        import numpy as _np

        return float(_np.max(_np.asarray(getattr(results, "z", [fallback]), dtype=float)))
    except Exception:
        return float(fallback)


def _png_b64(path: str) -> str | None:
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return None


def _common_xmax(results) -> float | None:
    """Maior pico entre todos os solutos (escala X comum da galeria)."""
    try:
        import numpy as _np

        gx = 0.0
        for _d in ((getattr(results, "nutrient_results", {}) or {}).values()):
            try:
                gx = max(gx, float(_np.max(_np.asarray(_d.get("final_profile", [0.0]), dtype=float))))
            except Exception:
                continue
        return gx if gx > 0 else None
    except Exception:
        return None


def build_images(req: SimulateRequest, results, soil, crop, root_depth: float,
                 total_rain: float, job_dir: str) -> tuple[ResultImages, str | None]:
    """Gera todos os PNGs do Resultado (mesmos do Gradio) e o ZIP individual.

    Arquivos em ``job_dir``: perfil.png, btc.png, evolucao.png, agua.png,
    soluto_{SYM}.png e graficos_simulacao.zip. Retorna (images, zip_path).
    """
    import numpy as _np  # noqa: F401 — garante backend numérico disponível

    os.makedirs(job_dir, exist_ok=True)
    first = req.solutes[0]
    dose_total = sum(float(s.dose_kg_ha) for s in req.solutes)
    rel_type = (first.release_type or "immediate")
    rel_days = float(first.release_days or 60.0)
    depth = float(root_depth)
    nutrients_list = [{"symbol": s.symbol, "name": s.name} for s in req.solutes]
    syms = [str(s.symbol) for s in req.solutes]
    gx = _common_xmax(results)

    images = ResultImages()

    # 1) Perfil principal C(z) + umidade, com banner.
    try:
        plot_nutrient_profile(
            results=results, soil=soil, crop=crop,
            rain_mm=float(total_rain), fertilizer_kg_ha=float(dose_total),
            nutrient_symbol=first.symbol, nutrient_name=first.name,
            output_path=os.path.join(job_dir, "perfil.png"),
            release_type=rel_type, release_days=rel_days,
            target_depth_cm=depth,
        )
        images.perfil = _png_b64(os.path.join(job_dir, "perfil.png"))
    except Exception:
        images.perfil = None

    # 2) Curvas de avanço C(t) e θ(t) (pode retornar None sem dados).
    try:
        btc_path = plot_breakthrough_curves(
            results=results, nutrient_symbol=first.symbol,
            output_path=os.path.join(job_dir, "btc.png"), crop=crop,
        )
        images.btc = _png_b64(btc_path) if btc_path else None
    except Exception:
        images.btc = None

    # 3) Evolução temporal do perfil (só se há dias de leitura).
    try:
        if getattr(results, "print_profiles", None):
            plot_profiles_at_days(
                results=results, soil=soil,
                nutrient_symbol=first.symbol, nutrient_name=first.name,
                output_path=os.path.join(job_dir, "evolucao.png"),
            )
            images.evolucao = _png_b64(os.path.join(job_dir, "evolucao.png"))
        else:
            images.evolucao = None
    except Exception:
        images.evolucao = None

    # 4) Perfil de água θ(z).
    try:
        plot_water_profile(
            results=results,
            output_path=os.path.join(job_dir, "agua.png"),
            title="Solo 1D — Perfil de Umidade do Solo θ(z)",
            soil=soil,
            root_depth_cm=(float(root_depth) if crop is not None else None),
            crop=crop,
        )
        images.agua = _png_b64(os.path.join(job_dir, "agua.png"))
    except Exception:
        images.agua = None

    # 5) Galeria por soluto (só se >1 soluto).
    if len(syms) > 1:
        for sym in syms:
            try:
                name = next((str(s.name) for s in req.solutes if str(s.symbol) == sym), sym)
                out = os.path.join(job_dir, f"soluto_{_safe_sym(sym)}.png")
                plot_nutrient_profile(
                    results=results, soil=soil, crop=crop,
                    rain_mm=float(total_rain), fertilizer_kg_ha=float(dose_total),
                    nutrient_symbol=sym, nutrient_name=name,
                    output_path=out, release_type=rel_type, release_days=rel_days,
                    target_depth_cm=depth,
                    solute_filter=sym, include_moisture=False, banner=False,
                    x_max=gx,
                )
                b64 = _png_b64(out)
                if b64:
                    images.galeria.append(GalleryImage(symbol=sym, name=name, png=b64))
            except Exception:
                continue

    # 6) Pasta + ZIP com 1 painel por PNG (mesmos nomes do legado).
    zip_path = _build_individual_graphs(
        results, soil, crop, float(total_rain), float(dose_total),
        rel_type, rel_days, depth, job_dir, nutrients_list, gx,
    )
    return images, zip_path


def _build_individual_graphs(results, soil, crop, rain_mm: float, dose: float,
                             rel_type: str, rel_days: float, depth: float,
                             job_dir: str, nutrients_list: list, gx=None) -> str | None:
    """1 gráfico por PNG + ZIP (nomes idênticos ao _build_individual_graphs_folder)."""
    folder_path = os.path.join(job_dir, "graficos_simulacao")
    os.makedirs(folder_path, exist_ok=True)
    solutes = [str(n.get("symbol")) for n in (nutrients_list or [])]

    def _name(sym: str) -> str:
        return next((str(n.get("name", sym)) for n in (nutrients_list or []) if str(n.get("symbol")) == sym), sym)

    # 1) Perfil de umidade em profundidade θ(z).
    try:
        plot_water_profile(
            results=results,
            output_path=os.path.join(folder_path, "01_perfil_profundidade_umidade.png"),
            title="Solo 1D — Perfil de Umidade do Solo θ(z)",
            soil=soil,
            root_depth_cm=(float(crop.root_depth_cm) if crop is not None else None),
            crop=crop,
        )
    except Exception:
        pass

    # 2) Perfis de concentração em profundidade C(z).
    if len(solutes) > 1:
        try:
            plot_nutrient_profile(
                results=results, soil=soil, crop=crop,
                rain_mm=float(rain_mm), fertilizer_kg_ha=float(dose),
                nutrient_symbol=solutes[0], nutrient_name="Multi-Nutriente",
                output_path=os.path.join(folder_path, "02_perfil_profundidade_combinado.png"),
                release_type=rel_type, release_days=float(rel_days),
                target_depth_cm=float(depth),
                include_moisture=False, banner=True,
            )
        except Exception:
            pass
    for sym in solutes:
        try:
            plot_nutrient_profile(
                results=results, soil=soil, crop=crop,
                rain_mm=float(rain_mm), fertilizer_kg_ha=float(dose),
                nutrient_symbol=sym, nutrient_name=_name(sym),
                output_path=os.path.join(folder_path, f"perfil_profundidade_{_safe_sym(sym)}.png"),
                release_type=rel_type, release_days=float(rel_days),
                target_depth_cm=float(depth),
                solute_filter=sym, include_moisture=False, banner=True,
                x_max=gx,
            )
        except Exception:
            continue

    # 3) Curvas de avanço no tempo θ(t) e C(t).
    try:
        plot_breakthrough_curves(
            results=results,
            output_path=os.path.join(folder_path, "avanco_tempo_umidade.png"),
            crop=crop,
            only_moisture=True,
        )
    except Exception:
        pass
    for sym in solutes:
        try:
            plot_breakthrough_curves(
                results=results,
                nutrient_symbol=sym,
                focus_symbol=sym,
                output_path=os.path.join(folder_path, f"avanco_tempo_{_safe_sym(sym)}.png"),
                crop=crop,
                include_moisture=False,
            )
        except Exception:
            continue

    # 4) Evolução temporal nos dias de leitura.
    if getattr(results, "print_profiles", None):
        try:
            plot_profiles_at_days(
                results=results, soil=soil,
                output_path=os.path.join(folder_path, "evolucao_dias_umidade.png"),
                only_moisture=True,
            )
        except Exception:
            pass
        for sym in solutes:
            try:
                plot_profiles_at_days(
                    results=results, soil=soil,
                    nutrient_symbol=sym, nutrient_name=_name(sym),
                    focus_symbol=sym,
                    output_path=os.path.join(folder_path, f"evolucao_dias_{_safe_sym(sym)}.png"),
                    include_moisture=False,
                )
            except Exception:
                continue

    zip_path = os.path.join(job_dir, "graficos_simulacao.zip")
    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for fn in sorted(os.listdir(folder_path)):
                fp = os.path.join(folder_path, fn)
                if os.path.isfile(fp) and fn.lower().endswith(".png"):
                    zf.write(fp, arcname=os.path.join("graficos_simulacao", fn))
    except Exception:
        return None
    return zip_path if os.path.exists(zip_path) else None


def _build_response(req: SimulateRequest, results, soil, crop, root_depth: float,
                    total_rain: float, total_days: float, images: ResultImages) -> SimulateResponse:
    _ = total_days
    return SimulateResponse(
        drainage_mm=float(results.q_bottom_cum_cm) * 10.0,
        solutes=_balances(req, results),
        images=images,
        applied_mm=float(total_rain),
        eval_depth_cm=float(root_depth),
        target_depth_cm=float(root_depth),
        has_crop=bool(crop is not None),
        z_max_cm=_z_max_cm(results, float(req.depth_cm)),
        runoff_mm=float(getattr(results, "runoff_cum_cm", 0.0) or 0.0) * 10.0,
        storage_mm=_storage_mm(results),
    )


def run_simulation(req: SimulateRequest, with_plot: bool = True) -> SimulateResponse:
    import tempfile

    results, soil, crop, root_depth, total_rain, total_days = _run_core(req)
    images = ResultImages()
    if with_plot:
        with tempfile.TemporaryDirectory() as tmp:
            images, _zip = build_images(req, results, soil, crop, root_depth, total_rain, tmp)
    return _build_response(req, results, soil, crop, root_depth, total_rain, total_days, images)


def execute_job(req: SimulateRequest, job_dir: str) -> tuple[SimulateResponse, str, str]:
    """Roda uma vez e gera response + Excel + laudo no diretório do job."""
    os.makedirs(job_dir, exist_ok=True)
    results, soil, crop, root_depth, total_rain, total_days = _run_core(req)
    images, _zip = build_images(req, results, soil, crop, root_depth, total_rain, job_dir)
    resp = _build_response(req, results, soil, crop, root_depth, total_rain, total_days, images)
    excel_path = build_excel(req, results, soil, crop, root_depth, total_rain, total_days, job_dir)
    report_md = build_report(req, results, soil, crop, root_depth, total_rain, total_days)
    with open(os.path.join(job_dir, "laudo.md"), "w", encoding="utf-8") as f:
        f.write(report_md)
    return resp, excel_path, report_md


def _sim_params(req: SimulateRequest, results, soil, crop, root_depth: float, total_rain: float, total_days: float) -> dict:
    """Params mínimos p/ Excel e laudo (mesmas chaves do legado)."""
    dose_total = sum(float(s.dose_kg_ha) for s in req.solutes)
    first = req.solutes[0]
    nr = getattr(results, "nutrient_results", {}) or {}
    prim = nr.get(first.symbol, {}) or {}
    z = getattr(results, "z", [0.0])
    try:
        prof_depth = float(max(z))
    except Exception:
        prof_depth = float(req.depth_cm)
    return {
        "sim_type": "api",
        "nutrient_symbol": first.symbol,
        "fertilizer_name": first.name,
        "elemental_dose": dose_total,
        "soil_name": soil.name,
        "theta_r": float(soil.theta_r),
        "theta_s": float(soil.theta_s),
        "alpha": float(soil.alpha),
        "n": float(soil.n),
        "ks": float(soil.ks),
        "bulk_density": float(soil.bulk_density),
        "kd": float(first.kd),
        "kd_citation": "Referência para a textura (ajustável; não calibrado)",
        "dispersivity": float(first.dispersivity_cm),
        "crop_name": (crop.name if crop else "Perfil de solo nu (sem cultura)"),
        "root_depth_cm": float(root_depth),
        "rain_mm": float(total_rain),
        "total_days": float(total_days),
        "leaching_pct": float(prim.get("leaching_ratio_pct", 0.0) or 0.0),
        "retained_pct": float(prim.get("retained_root_pct", 0.0) or 0.0),
        "leaching_ratio_pct": float(prim.get("leaching_ratio_pct", 0.0) or 0.0),
        "retained_root_pct": float(prim.get("retained_root_pct", 0.0) or 0.0),
        "uptaken_pct": float(prim.get("uptaken_pct", 0.0) or 0.0),
        "peak_depth_cm": float(prim.get("peak_depth_cm", 0.0) or 0.0),
        "q_bottom_cm": float(getattr(results, "q_bottom_cum_cm", 0.0) or 0.0),
        "release_type": (first.release_type or "immediate"),
        "release_days": float(first.release_days or 60.0),
        "nutrient_results": nr,
        "water_only": False,
        "profile_depth_cm": float(prof_depth),
        "runoff_mm": float(getattr(results, "runoff_cum_cm", 0.0) or 0.0) * 10.0,
        "drainage_mm": float(getattr(results, "q_bottom_cum_cm", 0.0) or 0.0) * 10.0,
        "obs_depths_cm": list(getattr(results, "obs_depths_cm", []) or []),
    }


def build_excel(req: SimulateRequest, results, soil, crop, root_depth: float,
                total_rain: float, total_days: float, job_dir: str) -> str:
    from hydrus_core.export_excel import export_soil_profile_excel

    out = os.path.join(job_dir, "perfil.xlsx")
    mode = "seasonal" if float(total_days) >= 180 else "column"
    return export_soil_profile_excel(
        results, out,
        sim_params=_sim_params(req, results, soil, crop, root_depth, total_rain, total_days),
        mode=mode,
    )


def build_report(req: SimulateRequest, results, soil, crop, root_depth: float,
                 total_rain: float, total_days: float) -> str:
    from hydrus_core.agronomic_report import generate_advanced_report, generate_column_report

    first = req.solutes[0]
    dose_total = sum(float(s.dose_kg_ha) for s in req.solutes)
    if float(total_days) >= 180:
        report = generate_advanced_report(
            results=results, soil=soil, crop=crop, rain_mm=float(total_rain),
            fertilizer_dose_kg_ha=dose_total, nutrient_symbol=first.symbol,
            nutrient_name=first.name, kd_used=float(first.kd),
            release_type=(first.release_type or "immediate"),
            release_days=float(first.release_days or 60.0),
        )
    else:
        z = getattr(results, "z", [0.0])
        try:
            prof_depth = float(max(z))
        except Exception:
            prof_depth = float(req.depth_cm)
        report = generate_column_report(
            results=results, soil=soil, rain_mm=float(total_rain),
            fertilizer_dose_kg_ha=dose_total, target_depth_cm=float(root_depth),
            column_height_cm=float(prof_depth), nutrient_symbol=first.symbol,
            nutrient_name=first.name, kd_used=float(first.kd),
            release_type=(first.release_type or "immediate"),
            release_days=float(first.release_days or 60.0),
            total_days=float(total_days),
        )
    # Como no Gradio: laudo termina com o passo a passo da simulação.
    try:
        from hydrus_core.explanatory_pipeline import generate_simulation_step_by_step

        step_md = generate_simulation_step_by_step(
            _sim_params(req, results, soil, crop, root_depth, total_rain, total_days)
        )[0]
        report = f"{report}\n\n---\n\n{step_md}"
    except Exception:
        pass
    return report
