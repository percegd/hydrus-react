"use client";

import { useEffect, useState } from "react";
import ClimateTable, { APP_DAY_DEFAULT } from "./ClimateTable";
import HelpIcon from "./HelpIcon";
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
  hasCrop: boolean;
  cropKc: string;
  cropHeightM: string;
  seasonalMoisture: string;
  setSeasonalMoisture: (v: string) => void;
  advEt: boolean;
  setAdvEt: (v: boolean) => void;
  evap: string;
  setEvap: (v: string) => void;
  transp: string;
  setTransp: (v: string) => void;
  climateRows: ClimateRow[];
  setClimateRows: (rows: ClimateRow[]) => void;
  hubKey: string;
  setHubKey: (v: string) => void;
  hubLabel: string;
  setHubLabel: (v: string) => void;
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
};

function Field({ label, children, helpKey }: { label: string; children: React.ReactNode; helpKey?: string }) {
  return (
    <label className="field">
      <span className="field-label">
        <span className="field-label-row">
          {label}
          {helpKey && <HelpIcon helpKey={helpKey} />}
        </span>
      </span>
      {children}
    </label>
  );
}

function GlobeIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20" />
      <path d="M2 12h20" />
    </svg>
  );
}

function UploadSheetIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
      <path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z" />
      <path d="M14 2v4a2 2 0 0 0 2 2h4" />
      <path d="M12 12v6" />
      <path d="m15 15-3-3-3 3" />
    </svg>
  );
}

function DropIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z" />
    </svg>
  );
}

function SunIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2" />
      <path d="M12 20v2" />
      <path d="m4.93 4.93 1.41 1.41" />
      <path d="m17.66 17.66 1.41 1.41" />
      <path d="M2 12h2" />
      <path d="M20 12h2" />
      <path d="m6.34 17.66-1.41 1.41" />
      <path d="m19.07 4.93-1.41 1.41" />
    </svg>
  );
}

function SunCloudIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2v2" />
      <path d="m4.93 4.93 1.41 1.41" />
      <path d="M20 12h2" />
      <path d="m19.07 4.93-1.41 1.41" />
      <path d="M15.947 12.65a4 4 0 0 0-5.925-4.128" />
      <path d="M13 22H7a5 5 0 1 1 4.9-6H13a3 3 0 0 1 0 6Z" />
    </svg>
  );
}

function CloudRainIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242" />
      <path d="M16 14v6" />
      <path d="M8 14v6" />
      <path d="M12 16v6" />
    </svg>
  );
}

const WATER_SOURCES: { value: RainMode; label: string; icon: React.ReactNode }[] = [
  { value: "hub", label: "Série climática", icon: <GlobeIcon /> },
  { value: "upload", label: "Upload de série diária", icon: <UploadSheetIcon /> },
  { value: "uniform", label: "Lâmina de chuva/irrigação", icon: <DropIcon /> },
];

const SCENARIO_ICONS: Record<string, React.ReactNode> = {
  seco: <SunIcon />,
  medio: <SunCloudIcon />,
  chuvoso: <CloudRainIcon />,
};

export default function StepWater(props: Props) {
  const {
    days, setDays, rainMode, setRainMode, rainMm, setRainMm, moisture, setMoisture, et0, setEt0,
    hasCrop, cropKc, cropHeightM, seasonalMoisture, setSeasonalMoisture, advEt, setAdvEt, evap, setEvap, transp, setTransp,
    climateRows, setClimateRows, hubKey, setHubKey, hubLabel, setHubLabel, hubScenario, setHubScenario,
    hubAppDay, setHubAppDay, uploadAppDay, setUploadAppDay,
    analysisStart, setAnalysisStart, analysisEnd, setAnalysisEnd, printDays, setPrintDays,
  } = props;
  const [hubs, setHubs] = useState<HubInfo[]>([]);
  const [hubError, setHubError] = useState("");
  const [seriesInfo, setSeriesInfo] = useState("");
  const [uploadStatus, setUploadStatus] = useState("");
  const [uploadError, setUploadError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [exampleCsv, setExampleCsv] = useState("");
  const [mapOk, setMapOk] = useState(true);

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
    // Mantém o rótulo exato do seletor p/ series_source_label do laudo.
    if (hubKey && !hubLabel && hubs.length > 0) {
      const found = hubs.find((h) => h.key === hubKey);
      if (found) setHubLabel(found.label);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hubs, hubKey]);

  // Trocar polo/cenário preenche a tabela (como os handlers do Gradio).
  async function loadSeries(key: string, scenario: string) {
    if (!key) return;
    setHubError("");
    try {
      const s = await getHubSeries(key, scenario);
      setClimateRows(s.rows.map((r) => ({ ...r })));
      setHubLabel(s.hub_label);
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

  useEffect(() => {
    setMapOk(true);
  }, [hubKey]);

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

  // Repartição Kc dual FAO-56 cap. 7 (mesmas fórmulas do solver):
  // Tp = Kcb·ET0, Ep = Ke·ET0; Kcb = max(0,15; kc−0,05); Kc_max = max(1,2; Kcb+0,05);
  // fc = ((Kcb−0,15)/(Kc_max−0,15))^(1+0,5h); Ke = min(Kc_max−Kcb, (1−fc)·Kc_max, 1,0).
  const et0Num = parseFloat(String(et0).replace(",", ".")) || 0;
  const kcNum = hasCrop ? (parseFloat(String(cropKc).replace(",", ".")) || 0) : 0;
  const hRaw = parseFloat(String(cropHeightM ?? "1").replace(",", "."));
  const hNum = Number.isFinite(hRaw) ? hRaw : 1.0;
  const kcbCalc = hasCrop ? Math.max(0.15, kcNum - 0.05) : 0;
  const kcMaxCalc = Math.max(1.2, kcbCalc + 0.05);
  const fcCalc = kcbCalc <= 0.15
    ? 0
    : Math.min(0.99, Math.max(0, Math.pow((kcbCalc - 0.15) / Math.max(kcMaxCalc - 0.15, 1e-12), 1 + 0.5 * hNum)));
  const keCalc = hasCrop ? Math.min(kcMaxCalc - kcbCalc, (1 - fcCalc) * kcMaxCalc, 1.0) : 1.0;
  const transpCalc = Math.max(0, et0Num * (hasCrop ? kcbCalc : 0));
  const evapCalc = Math.max(0, et0Num * (hasCrop ? Math.min(1, Math.max(0, keCalc)) : 1));

  return (
    <>
      <div className="choice-cards-3" role="radiogroup" aria-label="Fonte de água">
        {WATER_SOURCES.map((o) => (
          <label key={o.value} className={`choice-card${rainMode === o.value ? " selected" : ""}`}>
            <input
              type="radio"
              name="water-source"
              value={o.value}
              checked={rainMode === o.value}
              onChange={() => setRainMode(o.value)}
            />
            <span className="choice-icon">{o.icon}</span>
            {o.label}
          </label>
        ))}
      </div>

      {isUniform && (
        <>
          <div className="form-row" style={{ marginTop: 16 }}>
            <Field label="Lâmina de Chuva / Irrigação [mm]" helpKey="rain_mm">
              <input value={rainMm} onChange={(e) => setRainMm(e.target.value)} inputMode="decimal" />
            </Field>
            <Field label="Umidade Prévia do Solo [% do intervalo residual→CC]" helpKey="moisture">
              <input value={moisture} onChange={(e) => setMoisture(e.target.value)} inputMode="decimal" />
            </Field>
            <Field label="Duração do Ensaio [dias]" helpKey="total_days">
              <input value={days} onChange={(e) => setDays(e.target.value)} inputMode="decimal" />
            </Field>
          </div>
          <div className="step-section-title">Evapotranspiração</div>
          <div className="form-row">
            <Field label="ET0 - Evapotranspiração de referência [mm/dia]" helpKey="et0">
              <input value={et0} onChange={(e) => setEt0(e.target.value)} inputMode="decimal" />
            </Field>
          </div>
          <div className="custom-toggle-chk et-adv-toggle">
            <label>
              <input
                type="checkbox"
                className="switch"
                checked={advEt}
                onChange={(e) => setAdvEt(e.target.checked)}
              />
              Avançado: informar evaporação/transpiração manualmente
            </label>
          </div>
          {!advEt && (
            <div className="et-split-info">
              {hasCrop ? (
                <><b>Transpiração (Tp = Kcb·ET0)</b> = {transpCalc.toFixed(2)} mm/dia &nbsp;•&nbsp; <b>Evaporação do solo (Ep = Ke·ET0)</b> = {evapCalc.toFixed(2)} mm/dia</>
              ) : (
                <><b>Evaporação do solo</b> = {evapCalc.toFixed(2)} mm/dia <span style={{ color: "#64748b" }}>(solo nu: 100% do ET0)</span></>
              )}
            </div>
          )}
          {advEt && (
            <div className="form-row et-adv-inputs">
              <Field label="Evaporação do solo [mm/dia] (0 = derivar de ET0 — Kc dual FAO-56)" helpKey="evap">
                <input value={evap} onChange={(e) => setEvap(e.target.value)} inputMode="decimal" />
              </Field>
              {hasCrop && (
                <Field label="Transpiração [mm/dia] (0 = derivar de ET0 — Kc dual FAO-56)" helpKey="transp">
                  <input value={transp} onChange={(e) => setTransp(e.target.value)} inputMode="decimal" />
                </Field>
              )}
            </div>
          )}
        </>
      )}

      {isHub && (
        <div style={{ marginTop: 16 }}>
          <div className="polo-layout-row">
            <div className="polo-map-col">
              {mapOk && hubKey ? (
                <div className="polo-map">
                  <img
                    src={`/maps/${hubKey}.png`}
                    alt={`Mapa do polo ${hubKey}`}
                    onError={() => setMapOk(false)}
                  />
                </div>
              ) : null}
            </div>
            <div className="polo-controls-col">
              <Field label="Polo agrícola">
                <select value={hubKey} onChange={(e) => setHubKey(e.target.value)}>
                  {hubs.map((h) => (
                    <option key={h.key} value={h.key}>{h.label}</option>
                  ))}
                </select>
              </Field>
              <div className="choice-cards-3" role="radiogroup" aria-label="Regime de chuva" style={{ gridTemplateColumns: "repeat(3, 1fr)" }}>
                {SCENARIO_OPTIONS.map((o) => (
                  <label key={o.value} className={`choice-card${hubScenario === o.value ? " selected" : ""}`} style={{ padding: "16px 10px 14px 10px" }}>
                    <input
                      type="radio"
                      name="scenario"
                      value={o.value}
                      checked={hubScenario === o.value}
                      onChange={() => setHubScenario(o.value)}
                    />
                    <span className="choice-icon sm">{SCENARIO_ICONS[o.value]}</span>
                    <span style={{ fontSize: 13.5 }}>{o.label}</span>
                  </label>
                ))}
              </div>
              <div className="app-day-chip">
                <Field label="Dia da aplicação do fertilizante [1 - 365]" helpKey="app_day">
                  <input value={hubAppDay} onChange={(e) => setHubAppDay(e.target.value)} placeholder={APP_DAY_DEFAULT} inputMode="decimal" />
                </Field>
              </div>
            </div>
          </div>
          {hubError && <p className="error-text">{hubError}</p>}
          {seriesInfo && <p className="hint-text">{seriesInfo}</p>}
          <div className="upload-note">
            <div><b>Tabela editável (365 dias):</b> edite células diretamente ou cole dados do Excel (Ctrl+V). <HelpIcon helpKey="water_series" /></div>
          </div>
          <ClimateTable rows={climateRows} setRows={setClimateRows} appDay={hubAppDay} setAppDay={setHubAppDay} hideAppDay />
        </div>
      )}

      {rainMode === "upload" && (
        <div style={{ marginTop: 16 }}>
          <div className="form-row">
            <Field label="Carregar planilha (.xlsx, .xls, .csv)">
              <input type="file" accept=".xlsx,.xls,.csv" onChange={handleFile} disabled={uploading} style={{ height: "auto", paddingTop: 10 }} />
            </Field>
            <span style={{ alignSelf: "end" }}>
              <button type="button" className="btn" onClick={downloadExample} disabled={!exampleCsv}>
                Baixar tabela-exemplo (.csv)
              </button>
            </span>
          </div>
          <div className="upload-note">
            <div><b>Série diária (365 dias):</b> a planilha importada preenche a tabela abaixo. São esperadas uma coluna de chuva (mm) e, opcionalmente, de ET0 (mm/dia). <HelpIcon helpKey="water_upload" /></div>
          </div>
          {uploadError && <p className="error-text">{uploadError}</p>}
          {uploadStatus && <p className="hint-text">{uploadStatus}</p>}
          <div className="app-day-chip" style={{ marginBottom: 8 }}>
            <Field label="Dia da aplicação do fertilizante [1 - 365]" helpKey="app_day">
              <input value={uploadAppDay} onChange={(e) => setUploadAppDay(e.target.value)} placeholder={APP_DAY_DEFAULT} inputMode="decimal" />
            </Field>
          </div>
          <ClimateTable rows={climateRows} setRows={setClimateRows} appDay={uploadAppDay} setAppDay={setUploadAppDay} hideAppDay />
        </div>
      )}

      {!isUniform && (
        <>
          <div className="form-row" style={{ marginTop: 12 }}>
            <Field label="Umidade inicial do perfil [% do intervalo residual→CC]" helpKey="seasonal_moisture">
              <input value={seasonalMoisture} onChange={(e) => setSeasonalMoisture(e.target.value)} inputMode="decimal" />
            </Field>
          </div>
          <div className="form-row" style={{ marginTop: 12 }}>
            <Field label="Início da janela de análise [dia do ano]" helpKey="window_start">
              <input value={analysisStart} onChange={(e) => setAnalysisStart(e.target.value)} inputMode="decimal" />
            </Field>
            <Field label="Fim da janela de análise [dia do ano]" helpKey="window_end">
              <input value={analysisEnd} onChange={(e) => setAnalysisEnd(e.target.value)} inputMode="decimal" />
            </Field>
          </div>
          <div className="form-row">
            <Field label="Dias de leitura [dia do ensaio] (ex: 55,128,237,365)" helpKey="print_days">
              <input value={printDays} onChange={(e) => setPrintDays(e.target.value)} placeholder="obrigatório — ex: 55, 128, 237, 365" />
            </Field>
          </div>
        </>
      )}

    </>
  );
}

export { APP_DAY_DEFAULT, emptyRows };
