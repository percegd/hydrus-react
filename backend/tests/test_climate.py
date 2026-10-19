"""T8 (polos climáticos) + T7 (upload de planilha) — endpoints /hubs e /climate."""

import io

from fastapi.testclient import TestClient

from app.main import app

HUB_KEYS = ["piracicaba_sp", "sorriso_mt", "rio_verde_go", "lem_ba", "londrina_pr", "passo_fundo_rs"]


def _client():
    return TestClient(app)


# ---------- T8: GET /hubs ----------


def test_hubs_lists_six_poles_in_order() -> None:
    with _client() as client:
        response = client.get("/hubs")
    assert response.status_code == 200, response.text
    hubs = response.json()
    assert [h["key"] for h in hubs] == HUB_KEYS
    for h in hubs:
        assert isinstance(h["label"], str) and h["label"].strip(), h
        assert isinstance(h["name"], str) and h["name"].strip(), h
        assert h["lat"] is not None and h["lon"] is not None, h
        assert h["mean_annual_mm"] and h["mean_annual_mm"] > 500, h
    # Rótulo como no Gradio: nome + " - NNNN mm".
    pira = hubs[0]
    assert "Piracicaba" in pira["label"] and "mm" in pira["label"], pira


# ---------- T8: GET /hubs/{key}/series ----------


def _expected_series(hub_key: str, scenario: str):
    """Série esperada pela mesma regra do Gradio (dados reais + fallback)."""
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
    return [round(float(v), 1) for v in rain], [round(float(v), 2) for v in et0], year


def test_series_matches_gradio_build_for_all_hubs_and_scenarios() -> None:
    with _client() as client:
        for hub in HUB_KEYS:
            for scenario, data_key in (("seco", "seco"), ("medio", "medio"), ("umido", "chuvoso")):
                response = client.get(f"/hubs/{hub}/series", params={"scenario": scenario})
                assert response.status_code == 200, (hub, scenario, response.text)
                payload = response.json()
                exp_rain, exp_et0, exp_year = _expected_series(hub, data_key)
                assert payload["days"] == 365 == len(exp_rain) == len(exp_et0)
                assert payload["rain_series"] == exp_rain, hub
                assert payload["et0_series"] == exp_et0, hub
                assert len(payload["rows"]) == 365
                assert payload["rows"][0] == {
                    "day": 1,
                    "rain_mm": exp_rain[0],
                    "et0_mm": exp_et0[0],
                }
                assert payload["year"] == exp_year
                assert payload["total_rain_mm"] == round(sum(exp_rain), 1)


def test_series_scenario_labels_like_gradio() -> None:
    with _client() as client:
        labels = {}
        for scenario in ("seco", "medio", "umido"):
            r = client.get("/hubs/piracicaba_sp/series", params={"scenario": scenario})
            assert r.status_code == 200, r.text
            labels[scenario] = r.json()["scenario_label"]
    assert labels == {"seco": "Ano Seco", "medio": "Ano Médio", "umido": "Ano Chuvoso"}
    # Alias "chuvoso" do Gradio dá a mesma série do "umido".
    with _client() as client:
        a = client.get("/hubs/piracicaba_sp/series", params={"scenario": "umido"}).json()
        b = client.get("/hubs/piracicaba_sp/series", params={"scenario": "chuvoso"}).json()
    assert a["rain_series"] == b["rain_series"]
    assert a["et0_series"] == b["et0_series"]


def test_series_unknown_hub_returns_404() -> None:
    with _client() as client:
        response = client.get("/hubs/fazenda_xyz/series")
    assert response.status_code == 404, response.text


def test_series_unknown_scenario_returns_422() -> None:
    with _client() as client:
        response = client.get("/hubs/piracicaba_sp/series", params={"scenario": "gelado"})
    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert isinstance(detail, list) and detail[0]["field"] == "scenario"
    assert detail[0]["message"].strip(), detail


def test_climate_example_table_shape() -> None:
    with _client() as client:
        response = client.get("/climate/example")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["headers"] == ["Dia", "Chuva (mm)", "ET0 (mm/dia)"]
    assert payload["filename"] == "serie_exemplo.csv"
    assert payload["csv"].splitlines()[0] == "Dia,Chuva (mm),ET0 (mm/dia)"
    assert payload["rows"], payload
    for row in payload["rows"]:
        assert set(row) == {"day", "rain_mm", "et0_mm"}, row


# ---------- T7: POST /climate/parse ----------


def _csv_bytes(rows: list[tuple], header: str = "Dia,Chuva (mm),ET0 (mm/dia)") -> bytes:
    lines = [header] + [f"{d},{r},{e}" for d, r, e in rows]
    return ("\n".join(lines) + "\n").encode("utf-8")


def _xlsx_bytes(rows: list[tuple], header=("Dia", "Chuva (mm)", "ET0 (mm/dia)")) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(list(header))
    for d, r, e in rows:
        ws.append([d, r, e])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_parse_csv_returns_365_rows_with_gradio_message() -> None:
    data = [(i + 1, float(i % 7), 4.0 + (i % 3) * 0.1) for i in range(10)]
    with _client() as client:
        response = client.post(
            "/climate/parse",
            files={"file": ("serie.csv", _csv_bytes(data), "text/csv")},
        )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["records_read"] == 10
    assert len(payload["rows"]) == 365
    assert payload["rows"][0] == {"day": 1, "rain_mm": 0.0, "et0_mm": 4.0}
    assert payload["rows"][6] == {"day": 7, "rain_mm": 6.0, "et0_mm": 4.0}
    # Dias além dos registros: chuva 0 / ET0 4.0 (regra do Gradio).
    assert payload["rows"][364] == {"day": 365, "rain_mm": 0.0, "et0_mm": 4.0}
    assert "Planilha carregada com sucesso!" in payload["message"]
    assert "10 registros lidos" in payload["message"]


def test_parse_xlsx_returns_365_rows() -> None:
    data = [(i + 1, 2.5, 3.8) for i in range(365)]
    with _client() as client:
        response = client.post(
            "/climate/parse",
            files={
                "file": (
                    "serie.xlsx",
                    _xlsx_bytes(data),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["records_read"] == 365
    assert len(payload["rows"]) == 365
    assert payload["total_rain_mm"] == round(2.5 * 365, 1)


def test_parse_csv_without_et0_defaults_to_4() -> None:
    content = "Dia,Chuva (mm)\n1,5.0\n2,0.0\n".encode("utf-8")
    with _client() as client:
        response = client.post("/climate/parse", files={"file": ("s.csv", content, "text/csv")})
    assert response.status_code == 200, response.text
    rows = response.json()["rows"]
    assert rows[0] == {"day": 1, "rain_mm": 5.0, "et0_mm": 4.0}
    assert rows[1] == {"day": 2, "rain_mm": 0.0, "et0_mm": 4.0}


def test_parse_unsupported_format_returns_422() -> None:
    with _client() as client:
        response = client.post(
            "/climate/parse", files={"file": ("serie.txt", b"1,2,3\n", "text/plain")}
        )
    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert detail[0]["field"] == "file" and detail[0]["message"].strip(), detail


def test_parse_oversized_file_returns_422() -> None:
    big = b"Dia,Chuva (mm),ET0 (mm/dia)\n" + b"1,12.5,4.2\n" * 220000
    assert len(big) > 2 * 1024 * 1024
    with _client() as client:
        response = client.post("/climate/parse", files={"file": ("big.csv", big, "text/csv")})
    assert response.status_code == 422, response.text
    assert "2 MB" in response.json()["detail"][0]["message"]


def test_parse_empty_file_returns_422() -> None:
    with _client() as client:
        response = client.post("/climate/parse", files={"file": ("vazia.csv", b"", "text/csv")})
    assert response.status_code == 422, response.text


def test_parse_header_only_returns_422_with_gradio_message() -> None:
    content = "Dia,Chuva (mm),ET0 (mm/dia)\n".encode("utf-8")
    with _client() as client:
        response = client.post("/climate/parse", files={"file": ("s.csv", content, "text/csv")})
    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert detail[0]["field"] == "file"
    assert "Erro ao ler arquivo" in detail[0]["message"], detail


def test_parse_negative_value_returns_422() -> None:
    content = "Dia,Chuva (mm),ET0 (mm/dia)\n1,-3.0,4.0\n".encode("utf-8")
    with _client() as client:
        response = client.post("/climate/parse", files={"file": ("s.csv", content, "text/csv")})
    assert response.status_code == 422, response.text
    assert "Erro ao ler arquivo" in response.json()["detail"][0]["message"]


def test_parse_garbled_content_returns_422_with_gradio_message() -> None:
    with _client() as client:
        response = client.post(
            "/climate/parse",
            files={"file": ("s.xlsx", b"\x00\x01\x02not-an-xlsx", "application/octet-stream")},
        )
    # Extensão .xlsx passa na porta de formato; o conteúdo quebra a leitura.
    assert response.status_code == 422, response.text
    assert "Erro ao ler arquivo" in response.json()["detail"][0]["message"]
