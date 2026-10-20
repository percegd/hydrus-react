"""
Módulo de Exportação para Planilha Excel (.XLSX)
Gera arquivos Excel estruturados com os perfis de solo (Concentração e Umidade vs Profundidade),
séries temporais (BTC) e parâmetros físicos/químicos da simulação.
"""

import os
from typing import Dict, Any, Optional
import pandas as pd
import numpy as np


def _water_balance_summary_rows(p: Dict[str, Any]):
    """Resumo (parâmetro, valor) do balanço hídrico para o modo "Somente água".

    Usado nas abas "Parametros_e_Balanco" no lugar do balanço de massa de soluto.
    """
    theta_r = float(p.get("theta_r", 0.0) or 0.0)
    theta_s = float(p.get("theta_s", 0.0) or 0.0)
    alpha = float(p.get("alpha", 0.0) or 0.0)
    n = float(p.get("n", 1.5) or 1.5)
    m = 1.0 - (1.0 / n) if n > 1.0 else 0.3
    theta_cc = theta_r + (theta_s - theta_r) / ((1.0 + (alpha * 100.0) ** n) ** m)
    _drain = p.get("drainage_mm")
    drainage_mm = float(_drain) if _drain is not None else float(p.get("q_bottom_cm", 0.0) or 0.0) * 10.0

    rows = [
        ("Modo de Simulação", "Somente água (sem transporte de soluto)"),
        ("Tipo de Simulação", p.get("sim_type", "Coluna 1D")),
        ("Solo", p.get("soil_name", "-")),
        ("θr [cm³/cm³]", theta_r),
        ("θs [cm³/cm³]", theta_s),
        ("α [1/cm]", alpha),
        ("n [-]", n),
        ("Ks [cm/dia]", p.get("ks", 0.0)),
        ("θcc (h = -100 cm) [cm³/cm³]", round(theta_cc, 4)),
        ("Densidade Aparente [g/cm³]", p.get("bulk_density", 0.0)),
        ("Profundidade do Perfil [cm]", p.get("profile_depth_cm", p.get("root_depth_cm", 0.0))),
        ("Cultura", p.get("crop_name", "-")),
        ("Lâmina de Água / Entrada [mm]", p.get("rain_mm", 0.0)),
        ("Duração da Simulação [dias]", p.get("total_days", 0.0)),
        ("Drenagem no Fundo [mm]", drainage_mm),
        ("Escoamento Superficial [mm]", p.get("runoff_mm", 0.0)),
        ("Δ Armazenamento no Perfil [mm]", p.get("storage_mm", 0.0)),
    ]
    obs = p.get("obs_depths_cm") or []
    if obs:
        rows.append(("Nós de Observação [cm]", ", ".join(f"{float(d):.0f}" for d in obs)))
    return rows


def export_soil_profile_excel(
    results_obj: Any,
    out_path: str,
    sim_params: Optional[Dict[str, Any]] = None,
    mode: str = "column"
) -> str:
    """
    Exporta a distribuição do perfil do solo (dados do gráfico) para um arquivo Excel (.xlsx).
    Suporta simulações em coluna (laboratório/campo) e simulações sazonais regionais (365 dias).
    """
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    p = sim_params or {}

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        if mode == "seasonal":
            _export_seasonal_sheets(writer, results_obj, p)
        else:
            _export_column_sheets(writer, results_obj, p)

    return out_path


def _excel_peak_label(results: Any, p: Dict[str, Any]) -> Any:
    """Pico para Excel: prefere results (NaN preservado), fallback p. Retorna 'indefinido' se NaN."""
    import math as _mm
    _v = None
    try:
        _v = getattr(results, "peak_depth_cm", None)
        if isinstance(_v, dict):
            _v = None
    except (TypeError, ValueError, AttributeError):
        _v = None
    if _v is None:
        try:
            _nr = getattr(results, "nutrient_results", None) or p.get("nutrient_results") or {}
            if isinstance(_nr, dict) and len(_nr) == 1:
                _v = next(iter(_nr.values())).get("peak_depth_cm", None)
        except (TypeError, ValueError, AttributeError):
            _v = None
    if _v is None:
        _v = p.get("peak_depth_cm", None)
    if _v is None:
        return "indefinido"
    try:
        return "indefinido" if _mm.isnan(float(_v)) else float(_v)
    except (TypeError, ValueError):
        return _v

def _export_column_sheets(writer: pd.ExcelWriter, results: Any, p: Dict[str, Any]):
    # 1. Perfil em Profundidade
    z = getattr(results, "z", None)
    if z is None:
        z = np.arange(0.0, 70.0 + 1.0, 1.0)
    else:
        z = np.array(z)

    data = {"Profundidade [cm]": np.round(z, 2)}

    theta_profiles = getattr(results, "theta_profiles", [])
    if theta_profiles and len(theta_profiles) > 0:
        data["Umidade_Inicial [cm³/cm³]"] = np.round(theta_profiles[0], 4)

    print_profiles = getattr(results, "print_profiles", None) or {}
    sorted_pdays = sorted(print_profiles.keys()) if isinstance(print_profiles, dict) else []
    for d_val in sorted_pdays:
        snap = print_profiles.get(d_val) or {}
        th_d = snap.get("theta")
        if th_d is not None and len(th_d) == len(z):
            d_lbl = f"{int(d_val)}" if float(d_val).is_integer() else f"{float(d_val):g}"
            data[f"Umidade_Dia_{d_lbl} [cm³/cm³]"] = np.round(th_d, 4)

    if theta_profiles and len(theta_profiles) > 0:
        data["Umidade_Final [cm³/cm³]"] = np.round(theta_profiles[-1], 4)

    is_multi = getattr(results, "nutrient_results", None) and len(results.nutrient_results) > 1
    nutr_sym = p.get("nutrient_symbol", "Soluto")

    if not p.get("water_only"):
        for d_val in sorted_pdays:
            snap = print_profiles.get(d_val) or {}
            c_tot_map = snap.get("c_total") or {}
            d_lbl = f"{int(d_val)}" if float(d_val).is_integer() else f"{float(d_val):g}"
            for sym_k, c_arr in c_tot_map.items():
                if c_arr is not None and len(c_arr) == len(z):
                    col_sym = sym_k if is_multi else (nutr_sym if nutr_sym != "Soluto" else sym_k)
                    data[f"Concentracao_{col_sym}_Dia_{d_lbl} [mg/cm³]"] = np.round(c_arr, 5)

    if is_multi:
        for sym, n_data in results.nutrient_results.items():
            c_prof = n_data.get("final_profile", [])
            if len(c_prof) == len(z):
                data[f"Concentracao_{sym} [mg/cm³]"] = np.round(c_prof, 5)
    else:
        n_profiles = getattr(results, "n_profiles", [])
        if n_profiles and len(n_profiles) > 0 and len(n_profiles[-1]) == len(z):
            data[f"Concentracao_{nutr_sym} [mg/cm³]"] = np.round(n_profiles[-1], 5)

    df_profile = pd.DataFrame(data)
    df_profile.to_excel(writer, sheet_name="Perfil_Solo_Cz_Theta", index=False)

    # 2. Curvas de Avanço no Tempo (BTC) nos Nós de Observação (se houver)
    times = getattr(results, "obs_times_days", [])
    depths = getattr(results, "obs_depths_cm", [])
    obs_c = getattr(results, "obs_c_series", {})
    obs_theta = getattr(results, "obs_theta_series", {})

    if times and len(times) > 1 and depths:
        btc_data = {"Tempo [dias]": np.round(times, 3)}
        # Solute concentration: todos os solutos (um bloco de colunas por soluto)
        if obs_c:
            for sym_key in obs_c.keys():
                c_series = obs_c.get(sym_key, {})
                for d in depths:
                    vals = c_series.get(d, [])
                    if len(vals) == len(times):
                        btc_data[f"Conc_{sym_key}_z_{int(d)}cm [mg/L]"] = np.round(vals, 4)
        # Moisture
        if obs_theta:
            for d in depths:
                vals = obs_theta.get(d, [])
                if len(vals) == len(times):
                    btc_data[f"Umidade_z_{int(d)}cm [cm³/cm³]"] = np.round(vals, 4)

        df_btc = pd.DataFrame(btc_data)
        df_btc.to_excel(writer, sheet_name="Curvas_BTC_ObsNode", index=False)

    # 3. Parâmetros e Balanço
    if p.get("water_only"):
        summary_rows = _water_balance_summary_rows(p)
    else:
        # Base raiz/camada: leaching_ratio/retained_root sobre dose+residual,
        # sem recorte — retido+abaixo+fundo+absorvido+cápsula ≈ 100% (±1%).
        _nr_p = p.get("nutrient_results") or {}
        if isinstance(_nr_p, dict) and len(_nr_p) > 1:
            _tot_d = sum(float((_d or {}).get("dose_kg_ha", 0.0) or 0.0) for _d in _nr_p.values()) or 1.0

            def _wavg(_key: str) -> float:
                return sum(float((_d or {}).get(_key, 0.0) or 0.0) * float((_d or {}).get("dose_kg_ha", 0.0) or 0.0) for _d in _nr_p.values()) / _tot_d

            _leach = _wavg("leaching_ratio_pct")
            _ret_r = _wavg("retained_root_pct")
            _upt = _wavg("uptaken_pct")
            _cap = _wavg("capsule_pct")
            _inp_tot = sum(float((_d or {}).get("input_kg_ha", float((_d or {}).get("dose_kg_ha", 0.0) or 0.0))) for _d in _nr_p.values())
            _res_tot = sum(float((_d or {}).get("residual_kg_ha", 0.0) or 0.0) for _d in _nr_p.values())
            _capped_any = any(bool((_d or {}).get("uptake_capped")) for _d in _nr_p.values())
        elif isinstance(_nr_p, dict) and len(_nr_p) == 1:
            _only = next(iter(_nr_p.values()))
            _leach = float((_only or {}).get("leaching_ratio_pct", p.get("leaching_pct", p.get("leached_bottom_pct", 0.0))) or 0.0)
            _ret_r = float((_only or {}).get("retained_root_pct", p.get("retained_pct", p.get("retained_profile_pct", 0.0))) or 0.0)
            _upt = float((_only or {}).get("uptaken_pct", p.get("uptaken_pct", 0.0)) or 0.0)
            _cap = float((_only or {}).get("capsule_pct", 0.0) or 0.0)
            _inp_tot = float((_only or {}).get("input_kg_ha", (_only or {}).get("dose_kg_ha", 0.0)) or 0.0)
            _res_tot = float((_only or {}).get("residual_kg_ha", 0.0) or 0.0)
            _capped_any = bool((_only or {}).get("uptake_capped"))
        else:
            _leach = float(p.get("leaching_pct", p.get("leaching_ratio_pct", 0.0)) or 0.0)
            _ret_r = float(p.get("retained_pct", p.get("retained_root_pct", 0.0)) or 0.0)
            _upt = float(p.get("uptaken_pct", 0.0) or 0.0)
            _cap = 0.0
            _inp_tot = float(p.get("elemental_dose", p.get("gross_dose", 0.0)) or 0.0)
            _res_tot = 0.0
            _capped_any = False
        _ret = float(_ret_r)
        _teto_period = "-"
        try:
            if _capped_any and isinstance(_nr_p, dict) and _nr_p:
                _vals = []
                for _dd in _nr_p.values():
                    if bool((_dd or {}).get("uptake_capped")):
                        _v = (_dd or {}).get("uptake_cap_kg_ha", None)
                        if _v is not None:
                            _vals.append(float(_v))
                if _vals:
                    _teto_period = round(float(sum(_vals)), 2)
        except Exception:
            _teto_period = "-"
        # (L10) Kd efetivo médio quando disponível
        _kd_eff_txt = p.get("kd", 0.0)
        try:
            if isinstance(_nr_p, dict) and _nr_p:
                import numpy as _np
                _kes = []
                for _dd in _nr_p.values():
                    _ke = (_dd or {}).get("kd_eff", (_dd or {}).get("kd", None))
                    if _ke is None:
                        continue
                    try:
                        if hasattr(_ke, "__len__") and not isinstance(_ke, (float, int)):
                            _ke = float(_np.mean(_np.asarray(_ke, dtype=float)))
                        else:
                            _ke = float(_ke)
                        _kes.append(_ke)
                    except Exception:
                        continue
                if _kes:
                    _kd_eff_txt = f"{float(p.get('kd', 0.0)):.4f} (efet. {sum(_kes)/len(_kes):.4f})"
        except Exception:
            pass
        summary_rows = [
            ("Tipo de Simulação", p.get("sim_type", "Coluna 1D")),
            ("Solo", p.get("soil_name", "-")),
            ("Nutriente Avaliado", p.get("nutrient_label", p.get("nutrient_symbol", "-"))),
            ("Símbolo do Nutriente", p.get("nutrient_symbol", "-")),
            ("Dose Aplicada [kg/ha]", p.get("elemental_dose", p.get("gross_dose", 0.0))),
            ("Massa de Entrada — dose + residual [kg/ha]", round(float(_inp_tot), 2)),
            ("Residual Inicial [kg/ha]", round(float(_res_tot), 2)),
            ("Lâmina de Água / Irrigação [mm]", p.get("rain_mm", 0.0)),
            ("Duração da Simulação [dias]", p.get("total_days", 0.0)),
            ("Coeficiente Kd nominal [cm³/g]", p.get("kd", 0.0)),
            ("Kd efetivo usado [cm³/g]", _kd_eff_txt),
            ("Dispersividade Longitudinal [cm]", p.get("dispersivity", 0.0)),
            ("Camada de Avaliação [cm]", p.get("root_depth_cm", 30.0)),
            ("Retenção na Camada [%]", round(_ret, 2)),
            ("Lixiviação / Deslocamento Além da Camada [%]", _leach),
            ("Ainda no Grânulo (não liberado) [%]", round(float(_cap), 2)),
            ("Absorção pela Cultura [%] (limitada pela demanda)", round(float(_upt), 2)),
            ("Absorção limitada pela demanda em parte do período", "sim" if _capped_any else "não"),
            ("Teto no período [kg/ha]", _teto_period),
            ("Profundidade do Pico Máximo [cm]", _excel_peak_label(results, p)),
            ("Drenagem Acumulada no Fundo [mm]", float(p.get("drainage_mm", float(p.get("q_bottom_cm", 0.0)) * 10.0))),
            ("Δ Armazenamento no Perfil [mm]", float(p.get("storage_mm", 0.0))),
            ("Escoamento Superficial [mm]", float(p.get("runoff_mm", 0.0))),
        ]
        # (L12) Nota de unidade quando P está entre os solutos
        try:
            _syms_c = set((_nr_p.keys() if isinstance(_nr_p, dict) else []) or {p.get("nutrient_symbol", "")})
        except Exception:
            _syms_c = {p.get("nutrient_symbol", "")}
        if "P" in _syms_c:
            summary_rows.append(("Nota de unidade (P)", "Perfil = P total (dissolvido+adsorvido, mg/cm³); BTC/dias = P dissolvido (mg/L)"))
    df_sum = pd.DataFrame(summary_rows, columns=["Parâmetro / Indicador", "Valor"])
    df_sum.to_excel(writer, sheet_name="Parametros_e_Balanco", index=False)


def _export_seasonal_sheets(writer: pd.ExcelWriter, res: Any, p: Dict[str, Any]):
    # 1. Perfil em Profundidade Sazonal
    z = getattr(res, "z", None)
    if z is None:
        z = np.arange(0.0, 100.0 + 1.0, 1.0)
    else:
        z = np.array(z)

    data = {"Profundidade [cm]": np.round(z, 2)}
    print_days = getattr(res, "print_days", [60, 120, 240, 365])
    sym = getattr(res, "nutrient_symbol", p.get("nutrient_symbol", "K"))

    _aq = getattr(res, "conc_aq_profiles", None) or {}
    _tot = getattr(res, "conc_total_profiles", None) or {}
    conc_profiles = getattr(res, "conc_profiles", {})
    theta_profiles = getattr(res, "theta_profiles", {})

    for d in print_days:
        if d in theta_profiles and len(theta_profiles[d]) == len(z):
            data[f"Umidade_Dia_{d} [cm³/cm³]"] = np.round(theta_profiles[d], 4)

    for d in print_days:
        # Fonte correta: _tot (total) primeiro; fallback _aq (dissolvido, rotulado) — Lucio CONSENSO-FINAL
        if d in _tot and len(_tot[d]) == len(z):
            data[f"Conc_{sym}_Dia_{d} [mg/cm3 total (dissolvido+adsorvido)]"] = np.round(_tot[d], 5)
        elif d in _aq and len(_aq[d]) == len(z):
            data[f"Conc_{sym}_Dia_{d} [mg/L dissolvido]"] = np.round(_aq[d], 5)
        else:
            c = conc_profiles.get(d, [])
            if len(c) == len(z):
                data[f"Conc_{sym}_Dia_{d} [mg/cm3 total (dissolvido+adsorvido)]"] = np.round(c, 5)

    df_profile = pd.DataFrame(data)
    df_profile.to_excel(writer, sheet_name="Perfil_Solo_Sazonal", index=False)

    # 2. Parâmetros e Balanço Anual
    if p.get("water_only"):
        summary_rows = _water_balance_summary_rows(p)
        summary_rows.insert(1, ("Polo Agrícola", getattr(res, "hub_name", p.get("crop_name", "-"))))
        summary_rows.insert(2, ("Cenário Climatológico", getattr(res, "scenario_name", "-")))
    else:
        # (L1) Base raiz/camada também no sazonal; (L7) rótulos dinâmicos p/ janela.
        _nr_s = getattr(res, "nutrient_results", None) or p.get("nutrient_results") or {}
        if isinstance(_nr_s, dict) and _nr_s:
            _tot_ds = sum(float((_d or {}).get("dose_kg_ha", 0.0) or 0.0) for _d in _nr_s.values()) or 1.0
            _leach_s = sum(float((_d or {}).get("leaching_ratio_pct", 0.0) or 0.0) * float((_d or {}).get("dose_kg_ha", 0.0) or 0.0) for _d in _nr_s.values()) / _tot_ds
        else:
            _leach_s = float(getattr(res, "mass_leached_pct", p.get("leaching_pct", p.get("leaching_ratio_pct", 0.0))) or 0.0)
        _upt_s = float(p.get("uptaken_pct", 0.0) or 0.0)
        _cap_s = 0.0
        _capped_s = False
        _inp_s = float(p.get("elemental_dose", 100.0) or 0.0)
        _res_s = 0.0
        _ret_base = p.get("retained_pct", p.get("retained_root_pct", 100.0 - _leach_s))
        if isinstance(_nr_s, dict) and _nr_s:
            _tot_ds2 = sum(float((_d or {}).get("dose_kg_ha", 0.0) or 0.0) for _d in _nr_s.values()) or 1.0
            _ret_base = sum(float((_d or {}).get("retained_root_pct", 0.0) or 0.0) * float((_d or {}).get("dose_kg_ha", 0.0) or 0.0) for _d in _nr_s.values()) / _tot_ds2
            _upt_s = sum(float((_d or {}).get("uptaken_pct", 0.0) or 0.0) * float((_d or {}).get("dose_kg_ha", 0.0) or 0.0) for _d in _nr_s.values()) / _tot_ds2
            _cap_s = sum(float((_d or {}).get("capsule_pct", 0.0) or 0.0) * float((_d or {}).get("dose_kg_ha", 0.0) or 0.0) for _d in _nr_s.values()) / _tot_ds2
            _capped_s = any(bool((_d or {}).get("uptake_capped")) for _d in _nr_s.values())
            _inp_s = sum(float((_d or {}).get("input_kg_ha", float((_d or {}).get("dose_kg_ha", 0.0) or 0.0))) for _d in _nr_s.values())
            _res_s = sum(float((_d or {}).get("residual_kg_ha", 0.0) or 0.0) for _d in _nr_s.values())
        _ret_s = float(_ret_base or 0.0)
        _teto_period_s = "-"
        try:
            if _capped_s and isinstance(_nr_s, dict) and _nr_s:
                _vals_s = []
                for _dd in _nr_s.values():
                    if bool((_dd or {}).get("uptake_capped")):
                        _v = (_dd or {}).get("uptake_cap_kg_ha", None)
                        if _v is not None:
                            _vals_s.append(float(_v))
                if _vals_s:
                    _teto_period_s = round(float(sum(_vals_s)), 2)
        except Exception:
            _teto_period_s = "-"
        _mode_lbl = str(p.get("mode_label", "") or "")
        _is_full_year = ("ano cheio" in _mode_lbl) or ("1–365" in _mode_lbl) or ("janela" not in _mode_lbl.lower() and "dias" not in _mode_lbl.lower())
        # Heurística robusta: total_days >= 360 → anual; senão período.
        try:
            _td = float(p.get("total_days", getattr(res, "total_days", 365) or 365))
        except (TypeError, ValueError):
            _td = 365.0
        if _td >= 360:
            _chuva_lbl, _dren_lbl, _ret_lbl, _leach_lbl = ("Chuva Anual Total [mm]", "Drenagem Profunda Acumulada Anual [mm]", "Retenção Anual na Camada [%]", "Lixiviação Anual Além da Camada [%]")
        else:
            _chuva_lbl, _dren_lbl, _ret_lbl, _leach_lbl = ("Chuva no Período [mm]", "Drenagem no Período [mm]", "Retenção na Camada no Período [%]", "Lixiviação no Período Além da Camada [%]")
        summary_rows = [
            ("Tipo de Simulação", "Sazonal Anual Regional (INMET)" if _td >= 360 else str(p.get("sim_type", "Sazonal (janela de análise)"))),
            ("Polo Agrícola", getattr(res, "hub_name", p.get("crop_name", "-"))),
            ("Cenário Climatológico", getattr(res, "scenario_name", "-")),
            ("Solo", getattr(res, "soil_name", p.get("soil_name", "-"))),
            (_chuva_lbl, getattr(res, "total_rain_mm", p.get("rain_mm", 0.0))),
            ("Nutriente Avaliado", getattr(res, "nutrient_name", p.get("nutrient_label", sym))),
            ("Símbolo do Nutriente", sym),
            ("Dose Aplicada [kg/ha]", p.get("elemental_dose", 100.0)),
            ("Massa de Entrada — dose + residual [kg/ha]", round(float(_inp_s), 2)),
            ("Residual Inicial [kg/ha]", round(float(_res_s), 2)),
            ("Coeficiente Kd nominal [cm³/g]", getattr(res, "kd_used", p.get("kd", 0.0))),
            ("Dispersividade Longitudinal [cm]", p.get("dispersivity", 10.0)),
            ("Camada Útil / Raiz [cm]", getattr(res, "root_depth_cm", p.get("root_depth_cm", 40.0))),
            (_ret_lbl, round(_ret_s, 2)),
            (_leach_lbl, _leach_s),
            ("Ainda no Grânulo (não liberado) [%]", round(float(_cap_s), 2)),
            ("Absorção pela Cultura [%] (limitada pela demanda)", round(float(_upt_s), 2)),
            ("Absorção limitada pela demanda em parte do período", "sim" if _capped_s else "não"),
            ("Teto no período [kg/ha]", _teto_period_s),
            ("Profundidade do Pico Máximo no Fim do Ano [cm]", _excel_peak_label(res, p)),
            (_dren_lbl, float(p.get("drainage_mm", float(getattr(res, "drainage_cum_cm", 0.0)) * 10.0))),
            ("Δ Armazenamento no Perfil [mm]", float(p.get("storage_mm", 0.0))),
            ("Escoamento Superficial [mm]", float(p.get("runoff_mm", 0.0))),
        ]
        try:
            _syms_s = set((_nr_s.keys() if isinstance(_nr_s, dict) else []) or {sym})
        except Exception:
            _syms_s = {sym}
        if "P" in _syms_s:
            summary_rows.append(("Nota de unidade (P)", "Perfil = P total (dissolvido+adsorvido, mg/cm³); BTC/dias = P dissolvido (mg/L)"))
    df_sum = pd.DataFrame(summary_rows, columns=["Parâmetro / Indicador", "Valor"])
    df_sum.to_excel(writer, sheet_name="Parametros_e_Balanco", index=False)
