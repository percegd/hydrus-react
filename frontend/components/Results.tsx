"use client";

import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import ProfileChart from "./ProfileChart";
import { plotUrl } from "../lib/api";
import type { ExtraPlot, SimulateResponse } from "../lib/api";

/* Paleta por nutriente — porte de NUTRIENT_ACCENTS (app_gradio.py). */
const ACCENTS: Record<string, [string, string]> = {
  N: ["#fff7ed", "#c2410c"],
  K: ["#f5f3ff", "#6d28d9"],
  P: ["#f7fee7", "#4d7c0f"],
  S: ["#fefce8", "#a16207"],
  Ca: ["#ecfdf5", "#047857"],
  Mg: ["#fdf2f8", "#be185d"],
};

export type SoluteMeta = { kd: string; residual: string };

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
  hasCrop: boolean;
  soluteMeta?: Record<string, SoluteMeta>;
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

/* Cabeçalhos de seção iguais aos do Gradio (Passo 5 / Resultados). */
const GROUP_LABELS: Record<PlotGroup | "todos", string> = {
  todos: "Todos",
  perfil: "Distribuição em Profundidade C(z)",
  btc: "Curvas de Avanço no Tempo C(t) e θ(t)",
  evolucao: "Evolução Temporal do Perfil",
};

function soluteOf(key: string): string {
  const m = key.match(/^(?:perfil|avanco_tempo|evolucao_dias)_(.+)$/);
  if (!m) return "";
  const rest = m[1];
  if (rest === "umidade" || rest === "combinado" || rest === "profundidade_umidade") return "";
  return rest;
}

function fmtPeak(v: number | null | undefined): string {
  if (v === null || v === undefined || (typeof v === "number" && Number.isNaN(v))) return "indefinido";
  return `${v.toFixed(1)} cm`;
}

export default function Results(props: Props) {
  const { jobState, elapsed, jobId, result, report, steps, cropName, rootDepth, appliedMm, hasCrop, soluteMeta, onDownloadExcel, onDownloadGraphs, onLoadReport, onLoadSteps } = props;

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
      // Umidade/combinado aparecem só em "todos os solutos".
      if (solute !== "todos" && !s && p.key !== "perfil_combinado") return false;
    }
    return true;
  });

  const done = jobState === "done";
  const wb = result?.water_balance ?? null;
  const appliedLabel = wb?.applied_label ?? "Lâmina Aplicada";
  const drainageLabel = wb?.drainage_label ?? "Drenagem no Fundo";
  const appliedVal = wb ? wb.applied_mm : appliedMm;
  const drainageVal = wb ? wb.drainage_mm : result?.drainage_mm;
  const waterOnly = !result?.solutes?.length;

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
              {/* Cartões de resultado — porte de build_metrics_cards_html (app_gradio.py):
                  água (lâmina + drenagem) primeiro, depois um cartão por soluto. */}
              <div className="metrics-card-grid">
                <div className="metric-card">
                  <div className="metric-icon"><RainIcon /></div>
                  <div className="metric-value">{appliedVal != null ? `${appliedVal.toFixed(0)} mm` : "—"}</div>
                  <div className="metric-label">{appliedLabel}</div>
                </div>
                <div className="metric-card">
                  <div className="metric-icon"><DrainIcon /></div>
                  <div className="metric-value">{drainageVal != null ? `${drainageVal.toFixed(1)} mm` : "—"}</div>
                  <div className="metric-label">{drainageLabel}</div>
                  <div className="metric-sub">{cropName} · raiz {rootDepth} cm</div>
                </div>
                {result.solutes.map((s) => {
                  const [bg, fg] = ACCENTS[s.symbol] ?? ["#f1f5f9", "#334155"];
                  const dose = s.dose_kg_ha;
                  const meta = soluteMeta?.[s.symbol];
                  const kdNum = meta?.kd != null && meta.kd !== "" ? parseFloat(String(meta.kd).replace(",", ".")) : NaN;
                  const resNum = meta?.residual != null && meta.residual !== "" ? parseFloat(String(meta.residual).replace(",", ".")) : 0;
                  return (
                    <div className="metric-card metric-nutr" key={s.symbol}>
                      <div className="metric-nutr-head">
                        <span className="metric-nutr-sym" style={{ background: bg, color: fg }}>{s.symbol}</span>
                        <span className="metric-nutr-name">{s.name}</span>
                      </div>
                      <div className="metric-value">{s.retained_root_pct.toFixed(1)}%</div>
                      <div className="metric-label">Retido na camada avaliada (0–{rootDepth.toFixed(0)} cm)</div>
                      <div className="metric-sub">{(dose * s.retained_root_pct / 100).toFixed(1)} kg/ha de {dose.toFixed(0)} kg/ha aplicados</div>
                      <div className="metric-nutr-rows">
                        <div className="metric-nutr-row"><span>Abaixo da camada (no perfil)</span><b>{s.below_profile_pct.toFixed(1)}% · {(dose * s.below_profile_pct / 100).toFixed(1)} kg/ha</b></div>
                        <div className="metric-nutr-row"><span>Atravessou o fundo ({rootDepth.toFixed(0)} cm)</span><b>{s.bottom_pct.toFixed(1)}% · {(dose * s.bottom_pct / 100).toFixed(1)} kg/ha</b></div>
                        {s.uptaken_pct > 0.05 && (
                          <div className="metric-nutr-row"><span>Absorvido (passivo, sem teto nutricional)</span><b>{s.uptaken_pct.toFixed(1)}% · {(dose * s.uptaken_pct / 100).toFixed(1)} kg/ha</b></div>
                        )}
                        <div className="metric-nutr-row"><span>Pico no perfil</span><b>{fmtPeak(s.peak_depth_cm)}</b></div>
                        {Number.isFinite(kdNum) && (
                          <div className="metric-nutr-row"><span>Kd</span><b>{kdNum.toFixed(3)} cm³/g</b></div>
                        )}
                        {resNum > 0 && (
                          <div className="metric-nutr-row"><span>Residual inicial</span><b>{resNum.toFixed(2)} mg/dm³</b></div>
                        )}
                      </div>
                    </div>
                  );
                })}
                {/* Modo "somente água": balanço hídrico (sem solutos) — porte do ramo
                    water_only de build_metrics_cards_html. */}
                {waterOnly && wb && (
                  <>
                    <div className="metric-card">
                      <div className="metric-icon"><LayersIcon /></div>
                      <div className="metric-value">{wb.storage_mm >= 0 ? "+" : ""}{wb.storage_mm.toFixed(1)} mm</div>
                      <div className="metric-label">{wb.storage_mm >= 0 ? "Ganho de Água no Perfil (θf − θi)" : "Perda de Água no Perfil (θf − θi)"}</div>
                    </div>
                    {wb.runoff_mm > 0.05 && (
                      <div className="metric-card">
                        <div className="metric-icon"><RainIcon /></div>
                        <div className="metric-value">{wb.runoff_mm.toFixed(1)} mm</div>
                        <div className="metric-label">Escoamento Superficial</div>
                      </div>
                    )}
                  </>
                )}
              </div>
              {wb?.evap_mm != null && wb?.transp_mm != null && (
                <p className="muted">
                  Evapotranspiração (E+T): {(wb.evap_mm + wb.transp_mm).toFixed(1)} mm
                  {" "}(E {wb.evap_mm.toFixed(1)} + T {wb.transp_mm.toFixed(1)} mm)
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
                    <div className="btn-row" style={{ marginTop: 0, marginBottom: 12 }} role="tablist" aria-label="Por Soluto">
                      <button
                        role="tab"
                        aria-selected={solute === "todos"}
                        className={solute === "todos" ? "btn btn-primary" : "btn"}
                        onClick={() => setSolute("todos")}
                      >
                        Por Soluto — todos
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
              {!hasCrop && (
                <p className="muted">Perfil sem raízes; sem cultura — a camada avaliada é o próprio domínio.</p>
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
