"use client";

import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import ProfileChart from "./ProfileChart";
import { plotUrl } from "../lib/api";
import type { ExtraPlot, SimulateResponse } from "../lib/api";

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
  jobId: string;
  result: SimulateResponse | null;
  report: string;
  steps: string;
  cropName: string;
  rootDepth: number;
  appliedMm: number | null;
  onDownloadExcel: () => void;
  onDownloadGraphs: () => void;
  onLoadReport: () => void;
  onLoadSteps: () => void;
};

function RainIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z" />
    </svg>
  );
}

function DrainIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <line x1="12" y1="4" x2="12" y2="20" />
      <polyline points="18 14 12 20 6 14" />
    </svg>
  );
}

function LayersIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 12h18" />
      <path d="M3 6h18" />
      <path d="M3 18h18" />
    </svg>
  );
}

type PlotGroup = "perfil" | "btc" | "evolucao";

function groupOf(key: string): PlotGroup {
  if (key.startsWith("avanco_tempo")) return "btc";
  if (key.startsWith("evolucao_dias")) return "evolucao";
  return "perfil";
}

const GROUP_LABELS: Record<PlotGroup | "todos", string> = {
  todos: "Todos",
  perfil: "Perfil em profundidade",
  btc: "Avanço no tempo (BTC)",
  evolucao: "Evolução nos dias de leitura",
};

function soluteOf(key: string): string {
  const m = key.match(/^(?:perfil|avanco_tempo|evolucao_dias)_(.+)$/);
  if (!m) return "";
  const rest = m[1];
  if (rest === "umidade" || rest === "combinado" || rest === "profundidade_umidade") return "";
  return rest;
}

export default function Results(props: Props) {
  const { jobState, elapsed, jobId, result, report, steps, cropName, rootDepth, appliedMm, onDownloadExcel, onDownloadGraphs, onLoadReport, onLoadSteps } = props;

  function extraSrc(p: ExtraPlot): string | null {
    if (p.url && jobId) return plotUrl(jobId, p.key);
    if (p.url) return p.url.startsWith("/api") ? p.url : `/api${p.url.startsWith("/") ? p.url : `/${p.url}`}`;
    if (p.png_base64) return `data:image/png;base64,${p.png_base64}`;
    return null;
  }

  const extra: ExtraPlot[] = useMemo(() => result?.extra_plots ?? [], [result]);
  const solutes = useMemo(() => {
    const set = new Set<string>();
    for (const p of extra) {
      const s = soluteOf(p.key);
      if (s) set.add(s);
    }
    for (const s of result?.solutes ?? []) set.add(s.symbol);
    return [...set];
  }, [extra, result]);

  const [tab, setTab] = useState<"resultados" | "laudo" | "passo">("resultados");
  const [group, setGroup] = useState<PlotGroup | "todos">("todos");
  const [solute, setSolute] = useState<string>("todos");

  useEffect(() => {
    setTab("resultados");
    setGroup("todos");
    setSolute("todos");
  }, [result]);

  useEffect(() => {
    if (tab === "laudo" && !report) onLoadReport();
    if (tab === "passo" && !steps) onLoadSteps();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  const filtered = extra.filter((p) => {
    if (group !== "todos" && groupOf(p.key) !== group) return false;
    if (solute !== "todos") {
      const s = soluteOf(p.key);
      if (s && s !== solute) return false;
      // Umidade/combinado aparecem em qualquer filtro de soluto? Não — só em "todos".
      if (solute !== "todos" && !s && p.key !== "perfil_combinado") return false;
    }
    return true;
  });

  const done = jobState === "done";

  return (
    <>
      {(jobState === "running" || jobState === "queued") && (
        <p className="results-status">
          <strong>{jobState === "queued" ? "Na fila" : "Calculando"}</strong> ({elapsed}s) — a página atualiza
          automaticamente ao concluir.
        </p>
      )}
      {jobState === "failed" && (
        <p className="error-text">Falha na simulação. Os detalhes foram exibidos no aviso.</p>
      )}
      {result && (
        <>
          <div className="results-tabs" role="tablist" aria-label="Abas de resultados">
            <button role="tab" aria-selected={tab === "resultados"} className={tab === "resultados" ? "results-tab selected" : "results-tab"} onClick={() => setTab("resultados")}>
              Resultados
            </button>
            <button role="tab" aria-selected={tab === "laudo"} className={tab === "laudo" ? "results-tab selected" : "results-tab"} onClick={() => setTab("laudo")}>
              Laudo
            </button>
            <button role="tab" aria-selected={tab === "passo"} className={tab === "passo" ? "results-tab selected" : "results-tab"} onClick={() => setTab("passo")}>
              Passo a passo
            </button>
          </div>

          {tab === "resultados" && (
            <>
              <div className="metrics-card-grid">
                {result.water_balance ? (
                  <>
                    <div className="metric-card">
                      <div className="metric-icon"><RainIcon /></div>
                      <div className="metric-value">{result.water_balance.applied_mm.toFixed(1)} mm</div>
                      <div className="metric-label">{result.water_balance.applied_label}</div>
                    </div>
                    <div className="metric-card">
                      <div className="metric-icon"><DrainIcon /></div>
                      <div className="metric-value">{result.water_balance.drainage_mm.toFixed(1)} mm</div>
                      <div className="metric-label">{result.water_balance.drainage_label}</div>
                      <div className="metric-sub">{cropName} · raiz {rootDepth} cm</div>
                    </div>
                    <div className="metric-card">
                      <div className="metric-icon"><LayersIcon /></div>
                      <div className="metric-value">{result.water_balance.storage_mm >= 0 ? "+" : ""}{result.water_balance.storage_mm.toFixed(1)} mm</div>
                      <div className="metric-label">{result.water_balance.storage_mm >= 0 ? "Ganho de Água no Perfil (θf − θi)" : "Perda de Água no Perfil (θf − θi)"}</div>
                    </div>
                    <div className="metric-card">
                      <div className="metric-icon"><RainIcon /></div>
                      <div className="metric-value">{result.water_balance.runoff_mm.toFixed(1)} mm</div>
                      <div className="metric-label">Escoamento Superficial</div>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="metric-card">
                      <div className="metric-icon"><RainIcon /></div>
                      <div className="metric-value">{appliedMm != null ? `${appliedMm.toFixed(0)} mm` : "—"}</div>
                      <div className="metric-label">Lâmina Aplicada</div>
                    </div>
                    <div className="metric-card">
                      <div className="metric-icon"><DrainIcon /></div>
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
                <div style={{ marginBottom: 16 }}>
                  <ProfileChart profiles={result.profiles as never} rootDepth={rootDepth} />
                </div>
              )}
              {extra.length > 0 && (
                <div style={{ marginBottom: 16 }}>
                  <div className="section-title">Gráficos</div>
                  <div className="btn-row" style={{ marginTop: 0, marginBottom: 12 }} role="tablist" aria-label="Gráficos por tipo">
                    {(Object.keys(GROUP_LABELS) as (PlotGroup | "todos")[]).map((g) => (
                      <button
                        key={g}
                        role="tab"
                        aria-selected={group === g}
                        className={group === g ? "btn btn-primary" : "btn"}
                        onClick={() => setGroup(g)}
                      >
                        {GROUP_LABELS[g]}
                      </button>
                    ))}
                  </div>
                  {solutes.length > 1 && (
                    <div className="btn-row" style={{ marginTop: 0, marginBottom: 12 }} role="tablist" aria-label="Gráficos por soluto">
                      <button
                        role="tab"
                        aria-selected={solute === "todos"}
                        className={solute === "todos" ? "btn btn-primary" : "btn"}
                        onClick={() => setSolute("todos")}
                      >
                        Todos os solutos
                      </button>
                      {solutes.map((sym) => (
                        <button
                          key={sym}
                          role="tab"
                          aria-selected={solute === sym}
                          className={solute === sym ? "btn btn-primary" : "btn"}
                          onClick={() => setSolute(sym)}
                        >
                          {sym}
                        </button>
                      ))}
                    </div>
                  )}
                  <div className="plots-grid">
                    {filtered.map((p) => {
                      const src = extraSrc(p);
                      if (!src) return null;
                      return (
                        <div className="plot-card" key={p.key}>
                          <p className="plot-card-title">{p.title}</p>
                          <img src={src} alt={p.title} loading="lazy" />
                          <div className="btn-row">
                            <a
                              className="btn"
                              href={src}
                              download={`${p.key}.png`}
                            >
                              Baixar PNG
                            </a>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                  {filtered.length === 0 && (
                    <p className="muted">Nenhum gráfico para este filtro.</p>
                  )}
                </div>
              )}
              {done && (
                <div className="graph-download-actions-row">
                  <button className="btn" onClick={onDownloadGraphs}>Baixar Gráficos (PNG) ⤓</button>
                  <button className="btn" onClick={onDownloadExcel}>Baixar Dados do Perfil (.XLSX) ⤓</button>
                </div>
              )}
            </>
          )}

          {tab === "laudo" && (
            <div>
              <div className="section-title">Laudo</div>
              {report ? (
                <div className="laudo-md">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{report}</ReactMarkdown>
                </div>
              ) : (
                <p className="muted">Carregando laudo…</p>
              )}
            </div>
          )}

          {tab === "passo" && (
            <div>
              <div className="section-title">Passo a passo</div>
              {steps ? (
                <div className="laudo-md">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{steps}</ReactMarkdown>
                </div>
              ) : (
                <p className="muted">Carregando passo a passo…</p>
              )}
            </div>
          )}
        </>
      )}
    </>
  );
}
