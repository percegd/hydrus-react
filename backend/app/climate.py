"""Série climática dos polos + parse de planilha (paridade com app_gradio.py).

Porta a lógica que vive só no Gradio legado:
- ``hub_label`` / ``HUB_CHOICES`` / ``SCENARIO_CHOICES``,
- ``build_climate_table_rows`` (série diária de 365 dias do polo/cenário),
- ``handle_climate_upload`` (leitura de .xlsx/.csv em tabela de 365 dias).

A física (chuva real NASA POWER + ET0 FAO-56) vem do ``hydrus_core``
(``hub_climate`` + fallback sintético de ``literature_database``) — este
módulo só formata como o Gradio.
"""

from __future__ import annotations

import io
from typing import Optional

_HUB_ORDER = ["piracicaba_sp", "sorriso_mt", "rio_verde_go", "lem_ba", "londrina_pr", "passo_fundo_rs"]

# Rótulos do radio de cenário do Gradio (app_gradio.py :: SCENARIO_CHOICES).
SCENARIO_LABELS = {
    "seco": "Ano Seco",
    "medio": "Ano Médio",
    "chuvoso": "Ano Chuvoso",
}
# "Úmido" é alias da tarefa para o "Ano Chuvoso" do Gradio.
_SCENARIO_ALIASES = {
    "seco": "seco",
    "medio": "medio",
    "médio": "medio",
    "chuvoso": "chuvoso",
    "umido": "chuvoso",
    "úmido": "chuvoso",
}

CLIMATE_TABLE_HEADERS = ["Dia", "Chuva (mm)", "ET0 (mm/dia)"]

MAX_UPLOAD_BYTES = 2 * 1024 * 1024


def _normalize_scenario(value: object) -> Optional[str]:
    """Normaliza o cenário p/ a chave dos dados (seco|medio|chuvoso) ou None."""
    import unicodedata

    if value is None:
        return None
    s = str(value).strip().lower()
    # "Ano Seco" -> "seco" (remove prefixo + acentos p/ comparar).
    s = s.replace("ano ", "").strip()
    s_nfd = "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )
    for alias, key in _SCENARIO_ALIASES.items():
        a_nfd = "".join(
            c for c in unicodedata.normalize("NFD", alias) if unicodedata.category(c) != "Mn"
        )
        if s_nfd == a_nfd:
            return key
    return None


def hub_label(hub_key: str) -> str:
    """Rótulo do polo como no Gradio (nome + precipitação média anual NASA POWER)."""
    from hydrus_core.hub_climate import hub_mean_annual_mm
    from hydrus_core.literature_database import AGRICULTURAL_HUBS

    base = (AGRICULTURAL_HUBS.get(hub_key) or {}).get("name", hub_key)
    mm = hub_mean_annual_mm(hub_key)
    if mm is None:
        return base
    txt = f"{mm:,.0f}".replace(",", ".")
    return (base[:-1] + f" - {txt} mm)") if base.endswith(")") else f"{base} - {txt} mm"


def list_hubs() -> list[dict]:
    """Polos como no dropdown hub_choice do Gradio (ordem fixa)."""
    from hydrus_core.hub_climate import hub_mean_annual_mm
    from hydrus_core.literature_database import AGRICULTURAL_HUBS

    coords: dict = {}
    try:
        from hydrus_core import hub_climate as _hc

        raw = _hc._load()  # type: ignore[attr-defined]
        for k, v in (raw or {}).items():
            if isinstance(v, dict):
                coords[k] = v
    except Exception:
        coords = {}
    out = []
    for key in _HUB_ORDER:
        hub = AGRICULTURAL_HUBS.get(key) or {}
        c = coords.get(key) or {}
        out.append(
            {
                "key": key,
                "label": hub_label(key),
                "name": hub.get("name", key),
                "lat": c.get("lat"),
                "lon": c.get("lon"),
                "mean_annual_mm": hub_mean_annual_mm(key),
            }
        )
    return out


def build_series_rows(hub_key: str, scenario: str) -> tuple[list[float], list[float], object]:
    """Série diária (chuva, et0) exatamente como o Gradio monta (build_climate_table_rows).

    Usa os dados reais NASA POWER do ano observado do cenário (chuva direta,
    ET0 FAO-56 do met do mesmo ano); sem dados, cai na climatologia sintética
    do polo (mesmo fallback do Gradio).
    """
    import numpy as _np

    from hydrus_core.hub_climate import hub_climate_series
    from hydrus_core.literature_database import generate_hub_et0_series, generate_hub_rainfall_series

    real = hub_climate_series(hub_key, scenario)
    if real is not None:
        rain = _np.asarray(real["rain"], dtype=float).ravel()
        et0 = _np.asarray(real["et0"], dtype=float).ravel()
        year = real.get("year")
    else:
        rain = _np.asarray(generate_hub_rainfall_series(hub_key, scenario), dtype=float).ravel()
        et0 = _np.asarray(generate_hub_et0_series(hub_key, scenario), dtype=float).ravel()
        year = None
    n = min(len(rain), len(et0))
    return (
        [round(float(rain[i]), 1) for i in range(n)],
        [round(float(et0[i]), 2) for i in range(n)],
        year,
    )


def series_payload(hub_key: str, scenario_raw: str) -> dict:
    """Payload do GET /hubs/{key}/series (tabela-exemplo incluída como rows)."""
    scenario = _normalize_scenario(scenario_raw)
    if scenario is None:
        raise ValueError(
            f"Cenário desconhecido: {scenario_raw}. Use seco, medio ou umido."
        )
    rain, et0, year = build_series_rows(hub_key, scenario)
    rows = [{"day": i + 1, "rain_mm": rain[i], "et0_mm": et0[i]} for i in range(len(rain))]
    return {
        "hub_key": hub_key,
        "hub_label": hub_label(hub_key),
        "scenario": scenario,
        "scenario_label": SCENARIO_LABELS[scenario],
        "year": year,
        "days": len(rain),
        "rain_series": rain,
        "et0_series": et0,
        "rows": rows,
        "total_rain_mm": round(float(sum(rain)), 1),
    }


def example_table(n_days: int = 5) -> dict:
    """Tabela-exemplo do formato esperado no upload (cabeçalho + amostra)."""
    sample = [[i + 1, 0.0, 4.0] for i in range(max(1, min(n_days, 365)))]
    csv_lines = ["Dia,Chuva (mm),ET0 (mm/dia)"] + [f"{d},{r},{e}" for d, r, e in sample]
    return {
        "headers": list(CLIMATE_TABLE_HEADERS),
        "rows": [{"day": d, "rain_mm": r, "et0_mm": e} for d, r, e in sample],
        "filename": "serie_exemplo.csv",
        "csv": "\n".join(csv_lines) + "\n",
    }


def _find_column(columns, *keywords: str):
    for col in columns:
        c_low = str(col).lower()
        if any(k in c_low for k in keywords):
            return col
    return None


def parse_upload_file(filename: str, content: bytes) -> dict:
    """Porta handle_climate_upload do Gradio: planilha -> 365 linhas.

    Retorna {"rows", "records_read", "total_rain_mm", "message"} com a mensagem
    de sucesso do Gradio. Erros levantam ValueError com a mensagem do Gradio
    ("Erro ao ler arquivo: ...") para o handler transformar em 422.
    """
    import pandas as _pd

    lname = (filename or "").lower()
    try:
        if lname.endswith(".csv"):
            try:
                df = _pd.read_csv(io.BytesIO(content))
            except UnicodeDecodeError:
                df = _pd.read_csv(io.BytesIO(content), encoding="latin-1")
        else:
            xl = _pd.ExcelFile(io.BytesIO(content))
            sheet = xl.sheet_names[0]
            for s in xl.sheet_names:
                if "seco" in s.lower() or "1921" in s.lower():
                    sheet = s
                    break
            df = xl.parse(sheet)
    except Exception as exc:
        raise ValueError(f"Erro ao ler arquivo: {exc}")

    try:
        rain_col = _find_column(df.columns, "chuva", "rain", "precip", "mm")
        if rain_col is None and len(df.columns) >= 2:
            rain_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]
        if rain_col is None:
            raise ValueError("coluna de chuva (mm) não encontrada")
        et0_col = _find_column(df.columns, "et0", "eto", "evap")
        rain_vals = df[rain_col].dropna().values
        et0_vals = df[et0_col].dropna().values if et0_col is not None else []
        if len(rain_vals) == 0:
            raise ValueError("arquivo vazio ou sem dados válidos")
        rows = []
        for i in range(365):
            dia = i + 1
            try:
                r = float(rain_vals[i]) if i < len(rain_vals) else 0.0
            except (TypeError, ValueError):
                raise ValueError(f"valor inválido de chuva na linha {i + 1} (use apenas números ≥ 0)")
            try:
                e = float(et0_vals[i]) if i < len(et0_vals) else 4.0
            except (TypeError, ValueError):
                raise ValueError(f"valor inválido de ET0 na linha {i + 1} (use apenas números ≥ 0)")
            import math as _math

            if _math.isnan(r) or _math.isinf(r) or r < 0:
                raise ValueError(f"valor inválido de chuva na linha {dia} (use apenas números ≥ 0)")
            if _math.isnan(e) or _math.isinf(e) or e < 0:
                raise ValueError(f"valor inválido de ET0 na linha {dia} (use apenas números ≥ 0)")
            rows.append({"day": dia, "rain_mm": round(r, 1), "et0_mm": round(e, 2)})
        tot_rain = sum(r["rain_mm"] for r in rows)
        message = (
            f"Planilha carregada com sucesso! {len(rain_vals)} registros lidos. "
            f"Precipitação total: {tot_rain:.1f} mm."
        )
        return {
            "rows": rows,
            "records_read": int(len(rain_vals)),
            "total_rain_mm": round(float(tot_rain), 1),
            "message": message,
        }
    except ValueError as exc:
        msg = str(exc)
        if msg.startswith("Erro ao ler arquivo"):
            raise
        raise ValueError(f"Erro ao ler arquivo: {msg}")
