"use client";

import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
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
  appliedMm: number | null;
  onEdit: () => void;
  onDownloadExcel: () => void;
  onLoadReport: () => void;
  onNewSimulation: () => void;
};

export default function Results(props: Props) {
  const { jobState, elapsed, result, report, error, fieldErrors, cropName, rootDepth, appliedMm, onEdit, onDownloadExcel, onLoadReport, onNewSimulation } = props;

  const gallery: Record<string, string> = (() => {
    if (result?.plots_png_base64 && Object.keys(result.plots_png_base64).length > 0) {
      return result.plots_png_base64;
    }
    if (result?.plot_png_base64) {
      const fallbackSym = result.solutes[0]?.symbol ?? "perfil";
      return { [fallbackSym]: result.plot_png_base64 };
    }
    return {};
  })();
  const symbols = Object.keys(gallery);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    setSelected(symbols.length > 0 ? symbols[0] : null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [result]);

  const selectedB64 = selected ? gallery[selected] : null;

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
            {result.water_balance ? (
              <>
                <div className="metric-card">
                  <div className="metric-icon">💧</div>
                  <div className="metric-value">{result.water_balance.applied_mm.toFixed(1)} mm</div>
                  <div className="metric-label">{result.water_balance.applied_label}</div>
                </div>
                <div className="metric-card">
                  <div className="metric-icon">↓</div>
                  <div className="metric-value">{result.water_balance.drainage_mm.toFixed(1)} mm</div>
                  <div className="metric-label">{result.water_balance.drainage_label}</div>
                  <div className="metric-sub">{cropName} · raiz {rootDepth} cm</div>
                </div>
                <div className="metric-card">
                  <div className="metric-icon">🌊</div>
                  <div className="metric-value">{result.water_balance.storage_mm >= 0 ? "+" : ""}{result.water_balance.storage_mm.toFixed(1)} mm</div>
                  <div className="metric-label">{result.water_balance.storage_mm >= 0 ? "Ganho de Água no Perfil (θf − θi)" : "Perda de Água no Perfil (θf − θi)"}</div>
                </div>
                <div className="metric-card">
                  <div className="metric-icon">≈</div>
                  <div className="metric-value">{result.water_balance.runoff_mm.toFixed(1)} mm</div>
                  <div className="metric-label">Escoamento Superficial</div>
                </div>
              </>
            ) : (
              <>
                <div className="metric-card">
                  <div className="metric-icon">💧</div>
                  <div className="metric-value">{appliedMm != null ? `${appliedMm.toFixed(0)} mm` : "—"}</div>
                  <div className="metric-label">Lâmina Aplicada</div>
                </div>
                <div className="metric-card">
                  <div className="metric-icon">↓</div>
                  <div className="metric-value">{result.drainage_mm.toFixed(1)} mm</div>
                  <div className="metric-label">Drenagem no Fundo</div>
                  <div className="metric-sub">{cropName} · raiz {rootDepth} cm</div>
                </div>
              </>
            )}
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
          {result.water_balance?.evap_mm != null && result.water_balance?.transp_mm != null && (
            <p className="muted">
              Evapotranspiração (E+T): {(result.water_balance.evap_mm + result.water_balance.transp_mm).toFixed(1)} mm
              {" "}(E {result.water_balance.evap_mm.toFixed(1)} + T {result.water_balance.transp_mm.toFixed(1)} mm)
            </p>
          )}
          {result.profiles && Object.keys(result.profiles.solutes ?? {}).length > 0 && (
            <div className="wizard-step-box" style={{ padding: 16, marginBottom: 16 }}>
              <ProfileChart profiles={result.profiles as never} rootDepth={rootDepth} />
            </div>
          )}
          {symbols.length > 0 && (
            <div className="wizard-step-box" style={{ padding: 16, marginBottom: 16 }}>
              <div className="section-title">Por Soluto</div>
              <div className="btn-row" style={{ marginTop: 0, marginBottom: 12 }} role="tablist" aria-label="Gráficos por soluto">
                {symbols.map((sym) => (
                  <button
                    key={sym}
                    role="tab"
                    aria-selected={selected === sym}
                    className={selected === sym ? "btn btn-primary" : "btn"}
                    onClick={() => setSelected(sym)}
                  >
                    {sym}
                  </button>
                ))}
              </div>
              {selected && selectedB64 && (
                <div>
                  <div className="muted" style={{ marginBottom: 8 }}>Perfil — {selected}</div>
                  <img src={`data:image/png;base64,${selectedB64}`} alt={`Perfil ${selected}`} style={{ width: "100%" }} />
                  <div className="btn-row">
                    <a
                      className="btn"
                      href={`data:image/png;base64,${selectedB64}`}
                      download={`perfil_${selected}.png`}
                    >
                      Baixar PNG
                    </a>
                  </div>
                </div>
              )}
            </div>
          )}
          {report && (
            <div className="wizard-step-box" style={{ padding: 16 }}>
              <div className="section-title">Laudo</div>
              <div className="laudo-md">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{report}</ReactMarkdown>
              </div>
            </div>
          )}
        </>
      )}
    </>
  );
}
