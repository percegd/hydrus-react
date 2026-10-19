"use client";

import ProfileChart from "./ProfileChart";
import type { SimulateResponse } from "../lib/api";

const ACCENTS: Record<string, [string, string]> = {
  N: ["#fff7ed", "#c2410c"],
  K: ["#f5f3ff", "#6d28d9"],
  P: ["#f7fee7", "#4d7c0f"],
  S: ["#fefce8", "#a16207"],
  Ca: ["#ecfdf5", "#047857"],
  Mg: ["#fdf2f8", "#be185d"],
};

type Props = {
  jobState: string;
  elapsed: number;
  result: SimulateResponse | null;
  report: string;
  error: string;
  fieldErrors: string[];
  cropName: string;
  rootDepth: number;
  onEdit: () => void;
  onDownloadExcel: () => void;
  onLoadReport: () => void;
  onNewSimulation: () => void;
};

export default function Results(props: Props) {
  const { jobState, elapsed, result, report, error, fieldErrors, cropName, rootDepth, onEdit, onDownloadExcel, onLoadReport, onNewSimulation } = props;
  return (
    <>
      <div className="btn-row" style={{ marginTop: 0, marginBottom: 12 }}>
        <button className="btn" onClick={onEdit}>← Editar</button>
        {jobState === "done" && (
          <>
            <button className="btn" onClick={onDownloadExcel}>Baixar Excel</button>
            <button className="btn" onClick={onLoadReport}>Ver laudo</button>
          </>
        )}
        <button className="btn" onClick={onNewSimulation}>Nova simulação</button>
      </div>
      <p className="muted">Status: <strong>{jobState || "—"}</strong> {jobState === "running" && <span>({elapsed}s)</span>}</p>
      {fieldErrors.length > 0 && (
        <ul className="error-text">
          {fieldErrors.map((m, i) => <li key={i}>{m}</li>)}
        </ul>
      )}
      {error && <p className="error-text">{error}</p>}
      {result && (
        <>
          <div className="metrics-card-grid">
            <div className="metric-card">
              <div className="metric-icon">↓</div>
              <div className="metric-value">{result.drainage_mm.toFixed(1)} mm</div>
              <div className="metric-label">Drenagem no período</div>
              <div className="metric-sub">{cropName} · raiz {rootDepth} cm</div>
            </div>
            {result.solutes.map((s) => {
              const [bg, fg] = ACCENTS[s.symbol] ?? ["#f1f5f9", "#334155"];
              const dose = s.dose_kg_ha;
              return (
                <div className="metric-card" key={s.symbol}>
                  <div className="metric-nutr-head">
                    <span className="metric-nutr-sym" style={{ background: bg, color: fg }}>{s.symbol}</span>
                    <span className="metric-nutr-name">{s.name}</span>
                  </div>
                  <div className="metric-value">{s.retained_root_pct.toFixed(1)}%</div>
                  <div className="metric-label">Retido na camada avaliada (0–{rootDepth} cm)</div>
                  <div className="metric-sub">{(dose * s.retained_root_pct / 100).toFixed(1)} kg/ha de {dose.toFixed(0)} kg/ha aplicados</div>
                  <div className="metric-nutr-rows">
                    <div className="metric-nutr-row"><span>Abaixo da camada (no perfil)</span><b>{s.below_profile_pct.toFixed(1)}% · {(dose * s.below_profile_pct / 100).toFixed(1)} kg/ha</b></div>
                    <div className="metric-nutr-row"><span>Atravessou o fundo</span><b>{s.bottom_pct.toFixed(1)}% · {(dose * s.bottom_pct / 100).toFixed(1)} kg/ha</b></div>
                    <div className="metric-nutr-row"><span>Absorvido (passivo, sem teto nutricional)</span><b>{s.uptaken_pct.toFixed(1)}% · {(dose * s.uptaken_pct / 100).toFixed(1)} kg/ha</b></div>
                    <div className="metric-nutr-row"><span>Pico no perfil</span><b>{s.peak_depth_cm ?? "indefinido"} cm</b></div>
                  </div>
                </div>
              );
            })}
          </div>
          {result.profiles && (
            <div className="wizard-step-box" style={{ padding: 16, marginBottom: 16 }}>
              <ProfileChart profiles={result.profiles as never} rootDepth={rootDepth} />
            </div>
          )}
          {result.plots_png_base64 && Object.keys(result.plots_png_base64).length > 0 ? (
            Object.entries(result.plots_png_base64).map(([sym, b64]) => (
              <div key={sym} className="wizard-step-box" style={{ padding: 16, marginBottom: 16 }}>
                <div className="muted" style={{ marginBottom: 8 }}>Perfil — {sym}</div>
                <img src={`data:image/png;base64,${b64}`} alt={`Perfil ${sym}`} style={{ width: "100%" }} />
              </div>
            ))
          ) : (
            result.plot_png_base64 && (
              <div className="wizard-step-box" style={{ padding: 16, marginBottom: 16 }}>
                <img src={`data:image/png;base64,${result.plot_png_base64}`} alt="Perfil" style={{ width: "100%" }} />
              </div>
            )
          )}
          {report && <div className="wizard-step-box" style={{ padding: 16 }}><pre className="laudo-pre">{report}</pre></div>}
        </>
      )}
    </>
  );
}
