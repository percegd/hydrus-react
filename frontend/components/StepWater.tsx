"use client";

import { useEffect, useState } from "react";
import ClimateTable, { APP_DAY_DEFAULT } from "./ClimateTable";
import {
  ApiError,
  getClimateExample,
  getHubSeries,
  getHubs,
  parseClimateFile,
  type ClimateRow,
  type HubInfo,
} from "../lib/api";

export type RainMode = "uniform" | "hub" | "upload";

// Rótulos iguais aos do Gradio (app_gradio.py).
export const WATER_SOURCE_OPTIONS = [
  "Série climática",
  "Upload de série diária",
  "Lâmina de chuva/irrigação",
] as const;

export const SCENARIO_OPTIONS = [
  { value: "seco", label: "Ano Seco" },
  { value: "medio", label: "Ano Médio" },
  { value: "chuvoso", label: "Ano Chuvoso" },
] as const;

export function rainModeToWaterSource(mode: RainMode): string {
  if (mode === "hub") return "Série climática";
  if (mode === "upload") return "Upload de série diária";
  return "Lâmina de chuva/irrigação";
}

export function waterSourceToRainMode(source: string): RainMode {
  if (source === "Série climática") return "hub";
  if (source === "Upload de série diária") return "upload";
  return "uniform";
}

function emptyRows(n = 365): ClimateRow[] {
  return Array.from({ length: n }, (_, i) => ({ day: i + 1, rain_mm: 0, et0_mm: 4.0 }));
}

type Props = {
  days: string;
  setDays: (v: string) => void;
  rainMode: RainMode;
  setRainMode: (v: RainMode) => void;
  rainMm: string;
  setRainMm: (v: string) => void;
  moisture: string;
  setMoisture: (v: string) => void;
  et0: string;
  setEt0: (v: string) => void;
  climateRows: ClimateRow[];
  setClimateRows: (rows: ClimateRow[]) => void;
  hubKey: string;
  setHubKey: (v: string) => void;
  hubScenario: string;
  setHubScenario: (v: string) => void;
  hubAppDay: string;
  setHubAppDay: (v: string) => void;
  uploadAppDay: string;
  setUploadAppDay: (v: string) => void;
  analysisStart: string;
  setAnalysisStart: (v: string) => void;
  analysisEnd: string;
  setAnalysisEnd: (v: string) => void;
  printDays: string;
  setPrintDays: (v: string) => void;
  error: string;
  fieldErrors: string[];
  onBack: () => void;
  onRun: () => void;
};

export default function StepWater(props: Props) {
  const {
    days, setDays, rainMode, setRainMode, rainMm, setRainMm, moisture, setMoisture, et0, setEt0,
    climateRows, setClimateRows, hubKey, setHubKey, hubScenario, setHubScenario,
    hubAppDay, setHubAppDay, uploadAppDay, setUploadAppDay,
    analysisStart, setAnalysisStart, analysisEnd, setAnalysisEnd, printDays, setPrintDays,
    error, fieldErrors, onBack, onRun,
  } = props;
  const [hubs, setHubs] = useState<HubInfo[]>([]);
  const [hubError, setHubError] = useState("");
  const [seriesInfo, setSeriesInfo] = useState("");
  const [uploadStatus, setUploadStatus] = useState("");
  const [uploadError, setUploadError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [exampleCsv, setExampleCsv] = useState("");

  useEffect(() => {
    getHubs().then(setHubs).catch((e) => setHubError(e instanceof Error ? e.message : String(e)));
    getClimateExample().then((ex) => setExampleCsv(ex.csv)).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Polo padrão: Piracicaba (default do Gradio).
  useEffect(() => {
    if (!hubKey && hubs.length > 0) {
      const def = hubs.find((h) => h.key === "piracicaba_sp") ?? hubs[0];
      setHubKey(def.key);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hubs]);

  // Trocar polo/cenário preenche a tabela (como os handlers do Gradio).
  async function loadSeries(key: string, scenario: string) {
    if (!key) return;
    setHubError("");
    try {
      const s = await getHubSeries(key, scenario);
      setClimateRows(s.rows.map((r) => ({ ...r })));
      const yr = s.year ? ` (ano observado ${s.year})` : "";
      setSeriesInfo(`${s.hub_label} — ${s.scenario_label}${yr}: ${s.total_rain_mm.toFixed(1)} mm em ${s.days} dias.`);
    } catch (e) {
      setHubError(e instanceof ApiError ? e.message : String(e instanceof Error ? e.message : e));
    }
  }

  useEffect(() => {
    if (rainMode === "hub" && hubKey) {
      loadSeries(hubKey, hubScenario);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rainMode, hubKey, hubScenario]);

  async function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    setUploadError("");
    setUploadStatus("");
    const f = e.target.files?.[0];
    if (!f) return;
    setUploading(true);
    try {
      const parsed = await parseClimateFile(f);
      setClimateRows(parsed.rows.map((r) => ({ ...r })));
      setUploadStatus(parsed.message);
    } catch (err) {
      setUploadError(err instanceof ApiError ? err.message : String(err instanceof Error ? err.message : err));
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  }

  function downloadExample() {
    const blob = new Blob([exampleCsv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "serie_exemplo.csv";
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  const isUniform = rainMode === "uniform";
  const isHub = rainMode === "hub";

  return (
    <>
      <div className="form-row">
        <label className="field">Regime hídrico
          <select value={rainModeToWaterSource(rainMode)} onChange={(e) => setRainMode(waterSourceToRainMode(e.target.value))}>
            {WATER_SOURCE_OPTIONS.map((o) => (
              <option key={o} value={o}>{o}</option>
            ))}
          </select>
        </label>
        {isUniform && (
          <>
            <label className="field">Duração do Ensaio [dias]
              <input value={days} onChange={(e) => setDays(e.target.value)} />
            </label>
            <label className="field">Lâmina de Chuva / Irrigação [mm]
              <input value={rainMm} onChange={(e) => setRainMm(e.target.value)} />
            </label>
          </>
        )}
        <label className="field">Umidade Prévia do Solo [% do intervalo residual→CC]
          <input value={moisture} onChange={(e) => setMoisture(e.target.value)} />
        </label>
        {isUniform && (
          <label className="field">ET0 - Evapotranspiração de referência [mm/dia]
            <input value={et0} onChange={(e) => setEt0(e.target.value)} />
          </label>
        )}
      </div>

      {isHub && (
        <>
          <div className="form-row" style={{ marginTop: 12 }}>
            <label className="field">Polo agrícola
              <select value={hubKey} onChange={(e) => setHubKey(e.target.value)}>
                {hubs.map((h) => (
                  <option key={h.key} value={h.key}>{h.label}</option>
                ))}
              </select>
            </label>
            <label className="field">Regime de chuva
              <select value={hubScenario} onChange={(e) => setHubScenario(e.target.value)}>
                {SCENARIO_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </label>
          </div>
          <div style={{ marginTop: 8 }} role="radiogroup" aria-label="Regime de chuva">
            {SCENARIO_OPTIONS.map((o) => (
              <label key={o.value} style={{ marginRight: 16 }}>
                <input
                  type="radio"
                  name="scenario"
                  checked={hubScenario === o.value}
                  onChange={() => setHubScenario(o.value)}
                />{" "}
                {o.label}
              </label>
            ))}
          </div>
          {hubError && <p className="error-text">{hubError}</p>}
          {seriesInfo && <p style={{ fontSize: 12 }}>{seriesInfo}</p>}
          <div style={{ marginTop: 8 }}>
            <ClimateTable rows={climateRows} setRows={setClimateRows} appDay={hubAppDay} setAppDay={setHubAppDay} />
          </div>
        </>
      )}

      {rainMode === "upload" && (
        <>
          <div className="form-row" style={{ marginTop: 12 }}>
            <label className="field">Carregar planilha (.xlsx, .xls, .csv)
              <input type="file" accept=".xlsx,.xls,.csv" onChange={handleFile} disabled={uploading} />
            </label>
            <span style={{ fontSize: 12, alignSelf: "end" }}>
              <button type="button" className="btn" onClick={downloadExample} disabled={!exampleCsv}>
                Baixar tabela-exemplo (.csv)
              </button>
            </span>
          </div>
          <p style={{ fontSize: 12, opacity: 0.8 }}>
            São esperadas uma coluna de chuva (mm) e, opcionalmente, de ET0 (mm/dia).
          </p>
          {uploadError && <p className="error-text">{uploadError}</p>}
          {uploadStatus && <p style={{ fontSize: 12 }}>{uploadStatus}</p>}
          <div style={{ marginTop: 8 }}>
            <ClimateTable rows={climateRows} setRows={setClimateRows} appDay={uploadAppDay} setAppDay={setUploadAppDay} />
          </div>
        </>
      )}

      {!isUniform && (
        <>
          <div className="form-row" style={{ marginTop: 12 }}>
            <label className="field">Início da janela de análise [dia do ano]
              <input value={analysisStart} onChange={(e) => setAnalysisStart(e.target.value)} />
            </label>
            <label className="field">Fim da janela de análise [dia do ano]
              <input value={analysisEnd} onChange={(e) => setAnalysisEnd(e.target.value)} />
            </label>
          </div>
          <div className="form-row" style={{ marginTop: 8 }}>
            <label className="field" style={{ flex: "1 1 100%" }}>Dias de leitura [dia do ensaio] (ex: 55,128,237,365)
              <input value={printDays} onChange={(e) => setPrintDays(e.target.value)} placeholder="obrigatório — ex: 55, 128, 237, 365" />
            </label>
          </div>
        </>
      )}
      {fieldErrors.length > 0 && (
        <ul className="error-text">
          {fieldErrors.map((m, i) => <li key={i}>{m}</li>)}
        </ul>
      )}
      {error && <p className="error-text">{error}</p>}
      <div className="btn-row">
        <button className="btn" onClick={onBack}>Voltar</button>
        <button className="btn btn-primary" onClick={onRun}>Calcular Resultados</button>
      </div>
    </>
  );
}

export { APP_DAY_DEFAULT, emptyRows };
