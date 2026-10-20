"""Gráficos extras por job — porte de _build_individual_graphs_folder (app_gradio.py ~821).

Gera 1 PNG por painel (como o Gradio): perfil de umidade θ(z), perfis de
concentração C(z) por soluto (+ combinado), curvas de avanço θ(t)/C(t) e
evolução nos dias de leitura — usando hydrus_core.visualizer exatamente
como o Gradio chama.
"""

import matplotlib

matplotlib.use("Agg")

import base64
import os
import zipfile


def _safe_sym(s: str) -> str:
    return "".join(ch if (ch.isalnum() or ch in ("_", "-")) else "_" for ch in str(s))


TITLES = {
    "perfil_umidade": "Perfil de Umidade do Solo θ(z)",
    "perfil_combinado": "Perfil Combinado em Profundidade (Multi-Nutriente)",
    "avanco_tempo_umidade": "Avanço da Umidade no Tempo θ(t)",
    "evolucao_dias_umidade": "Evolução do Perfil de Umidade nos Dias de Leitura",
}


def _title_perfil(sym: str, name: str) -> str:
    return f"Perfil em Profundidade — {name} ({sym})"


def _title_btc(sym: str, name: str) -> str:
    return f"Curva de Avanço (BTC) — {name} ({sym})"


def _title_evolucao(sym: str, name: str) -> str:
    return f"Evolução do Perfil — {name} ({sym}) nos Dias de Leitura"


def build_graph_files(
    results,
    soil,
    crop_obj,
    rain_mm: float,
    dose: float,
    rel_type: str,
    rel_days: float,
    depth: float,
    out_dir: str,
    nutrients_list: list,
    water_only: bool = False,
) -> list[dict]:
    """Gera os PNGs (1 painel por arquivo) em out_dir; retorna [{key,title,path}]."""
    from hydrus_core.visualizer import (
        plot_breakthrough_curves,
        plot_nutrient_profile,
        plot_profiles_at_days,
        plot_water_profile,
    )

    os.makedirs(out_dir, exist_ok=True)

    solutes = [] if water_only else [str(n.get("symbol")) for n in (nutrients_list or [])]
    _nr_all = getattr(results, "nutrient_results", {}) or {}
    if not water_only and not solutes and _nr_all:
        solutes = list(_nr_all.keys())

    _gx = 0.0
    for _d in _nr_all.values():
        try:
            import numpy as _np

            _gx = max(_gx, float(_np.max(_np.asarray(_d.get("final_profile", [0.0]), dtype=float))))
        except Exception:
            pass
    if not (_gx > 0):
        _gx = None

    files: list[dict] = []

    def _add(key: str, title: str, path: str) -> None:
        if os.path.isfile(path):
            files.append({"key": key, "title": title, "path": path})

    # 1) Perfil de umidade em profundidade θ(z) (1 gráfico)
    try:
        _p = os.path.join(out_dir, "01_perfil_profundidade_umidade.png")
        plot_water_profile(
            results=results,
            output_path=_p,
            title="Perfil de Umidade do Solo θ(z)",
            soil=soil,
            root_depth_cm=(float(crop_obj.root_depth_cm) if crop_obj else None),
            crop=crop_obj,
        )
        _add("perfil_umidade", TITLES["perfil_umidade"], _p)
    except Exception:
        pass

    # 2) Perfis de concentração em profundidade C(z) (1 gráfico por PNG)
    if not water_only:
        if len(solutes) > 1:
            try:
                _p = os.path.join(out_dir, "02_perfil_profundidade_combinado.png")
                plot_nutrient_profile(
                    results=results, soil=soil, crop=crop_obj,
                    rain_mm=float(rain_mm), fertilizer_kg_ha=float(dose),
                    nutrient_symbol=solutes[0], nutrient_name="Multi-Nutriente",
                    output_path=_p,
                    release_type=rel_type, release_days=float(rel_days),
                    target_depth_cm=float(depth),
                    include_moisture=False, banner=True,
                )
                _add("perfil_combinado", TITLES["perfil_combinado"], _p)
            except Exception:
                pass
        for sym in solutes:
            try:
                name = next((str(n.get("name", sym)) for n in (nutrients_list or []) if str(n.get("symbol")) == sym), sym)
                _p = os.path.join(out_dir, f"perfil_profundidade_{_safe_sym(sym)}.png")
                plot_nutrient_profile(
                    results=results, soil=soil, crop=crop_obj,
                    rain_mm=float(rain_mm), fertilizer_kg_ha=float(dose),
                    nutrient_symbol=sym, nutrient_name=name,
                    output_path=_p,
                    release_type=rel_type, release_days=float(rel_days),
                    target_depth_cm=float(depth),
                    solute_filter=sym, include_moisture=False, banner=True,
                    x_max=_gx,
                )
                _add(f"perfil_{_safe_sym(sym)}", _title_perfil(sym, name), _p)
            except Exception:
                pass

    # 3) Curvas de avanço no tempo θ(t) e C(t) (1 gráfico por PNG)
    try:
        _p = os.path.join(out_dir, "avanco_tempo_umidade.png")
        plot_breakthrough_curves(
            results=results,
            output_path=_p,
            crop=crop_obj,
            only_moisture=True,
        )
        _add("avanco_tempo_umidade", TITLES["avanco_tempo_umidade"], _p)
    except Exception:
        pass

    if not water_only:
        for sym in solutes:
            try:
                name = next((str(n.get("name", sym)) for n in (nutrients_list or []) if str(n.get("symbol")) == sym), sym)
                _p = os.path.join(out_dir, f"avanco_tempo_{_safe_sym(sym)}.png")
                plot_breakthrough_curves(
                    results=results,
                    nutrient_symbol=sym,
                    focus_symbol=sym,
                    output_path=_p,
                    crop=crop_obj,
                    include_moisture=False,
                )
                _add(f"avanco_tempo_{_safe_sym(sym)}", _title_btc(sym, name), _p)
            except Exception:
                pass

    # 4) Evolução temporal nos dias de leitura (1 gráfico por PNG)
    if getattr(results, "print_profiles", None):
        try:
            _p = os.path.join(out_dir, "evolucao_dias_umidade.png")
            plot_profiles_at_days(
                results=results,
                soil=soil,
                output_path=_p,
                only_moisture=True,
            )
            _add("evolucao_dias_umidade", TITLES["evolucao_dias_umidade"], _p)
        except Exception:
            pass

        if not water_only:
            for sym in solutes:
                try:
                    name = next((str(n.get("name", sym)) for n in (nutrients_list or []) if str(n.get("symbol")) == sym), sym)
                    _p = os.path.join(out_dir, f"evolucao_dias_{_safe_sym(sym)}.png")
                    plot_profiles_at_days(
                        results=results,
                        soil=soil,
                        nutrient_symbol=sym,
                        nutrient_name=name,
                        focus_symbol=sym,
                        output_path=_p,
                        include_moisture=False,
                    )
                    _add(f"evolucao_dias_{_safe_sym(sym)}", _title_evolucao(sym, name), _p)
                except Exception:
                    pass

    return files


def expected_descriptors(
    results,
    nutrients_list: list | None = None,
    water_only: bool = False,
) -> list[dict]:
    """Lista {key,title} esperada sem renderizar (para resposta imediata do job).

    Espelha as chaves que build_graph_files geraria se todos os plots
    tiverem sucesso; a validação do endpoint /plots/{key}.png usa esta lista.
    """
    nutrients_list = nutrients_list or []
    if water_only:
        solutes: list[str] = []
    else:
        solutes = [str(n.get("symbol")) for n in (nutrients_list or []) if str(n.get("symbol"))]
        if not solutes:
            try:
                _nr_all = getattr(results, "nutrient_results", {}) or {}
                solutes = list(_nr_all.keys())
            except Exception:
                solutes = []
    names = {str(n.get("symbol")): str(n.get("name", n.get("symbol"))) for n in (nutrients_list or [])}

    out: list[dict] = []
    out.append({"key": "perfil_umidade", "title": TITLES["perfil_umidade"]})
    if not water_only:
        if len(solutes) > 1:
            out.append({"key": "perfil_combinado", "title": TITLES["perfil_combinado"]})
        for sym in solutes:
            out.append({"key": f"perfil_{_safe_sym(sym)}", "title": _title_perfil(sym, names.get(sym, sym))})
    out.append({"key": "avanco_tempo_umidade", "title": TITLES["avanco_tempo_umidade"]})
    if not water_only:
        for sym in solutes:
            out.append({"key": f"avanco_tempo_{_safe_sym(sym)}", "title": _title_btc(sym, names.get(sym, sym))})
    try:
        has_print = bool(getattr(results, "print_profiles", None))
    except Exception:
        has_print = False
    if has_print:
        out.append({"key": "evolucao_dias_umidade", "title": TITLES["evolucao_dias_umidade"]})
        if not water_only:
            for sym in solutes:
                out.append({"key": f"evolucao_dias_{_safe_sym(sym)}", "title": _title_evolucao(sym, names.get(sym, sym))})
    return out


def plot_filename(key: str) -> str | None:
    """Nome do PNG no graphs_dir para uma chave de gráfico extra."""
    k = str(key or "")
    if k == "perfil_umidade":
        return "01_perfil_profundidade_umidade.png"
    if k == "perfil_combinado":
        return "02_perfil_profundidade_combinado.png"
    if k.startswith("perfil_"):
        return f"perfil_profundidade_{k[len('perfil_'):]}.png"
    if k.startswith("avanco_tempo_") or k.startswith("evolucao_dias_"):
        return f"{k}.png"
    return None


def encode_files(files: list[dict]) -> list[dict]:
    """Lê os PNGs e retorna [{key, title, png_base64}]."""
    out: list[dict] = []
    for f in files:
        try:
            with open(f["path"], "rb") as fh:
                out.append({
                    "key": str(f["key"]),
                    "title": str(f["title"]),
                    "png_base64": base64.b64encode(fh.read()).decode(),
                })
        except OSError:
            continue
    return out


def write_zip(files: list[dict], zip_path: str, folder_name: str = "graficos_simulacao") -> str:
    """Empacota os PNGs (1 painel por arquivo) no zip, como o Gradio."""
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(files, key=lambda x: os.path.basename(x["path"])):
            fp = f["path"]
            if os.path.isfile(fp) and fp.lower().endswith(".png"):
                zf.write(fp, arcname=os.path.join(folder_name, os.path.basename(fp)))
    return zip_path
