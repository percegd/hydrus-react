"use client";

import { useEffect, useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import type { SimulateResponse } from "../lib/api";

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

function fmtPeak(v: number | null | undefined): string {
  if (v === null || v === undefined || (typeof v === "number" && Number.isNaN(v))) return "indefinido";
  return `${v.toFixed(1)} cm`;
}

/* URLs de tela são relativas ("/jobs/{id}/tela/<nome>.png"); o rewrite /api -> backend serve. */
function screenSrc(u: string | null | undefined): string | null {
  if (!u) return null;
  if (u.startsWith("/api")) return u;
  return `/api${u.startsWith("/") ? u : `/${u}`}`;
}

export default function Results(props: Props) {
  const { jobState, elapsed, result, report, steps, rootDepth, appliedMm, soluteMeta, onDownloadExcel, onDownloadGraphs, onLoadReport, onLoadSteps } = props;

  /* Laudo + passo a passo carregados automaticamente quando o resultado chega
     (o Gradio concatena os dois no mesmo card: report = f"{laudo}\n\n---\n\n{passo}"). */
  useEffect(() => {
    if (!result) return;
    if (!report) onLoadReport();
    if (!steps) onLoadSteps();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [result]);

  /* z máx = profundidade do domínio (do vetor z dos perfis); D = raiz se há
     cultura, senão o próprio domínio (page.tsx já passa rootDepth assim). */
  const zmax = useMemo(() => {
    const z = result?.profiles?.z;
    if (z && z.length > 0) return Math.max(...z);
    return rootDepth;
  }, [result, rootDepth]);

  const done = jobState === "done";
  const wb = result?.water_balance ?? null;
  const appliedLabel = wb?.applied_label ?? "Lâmina Aplicada";
  const drainageLabel = wb?.drainage_label ?? "Drenagem no Fundo";
  const appliedVal = wb ? wb.applied_mm : appliedMm;
  const drainageVal = wb ? wb.drainage_mm : result?.drainage_mm;
  const waterOnly = !result?.solutes?.length;

  const perfilSrc = screenSrc(result?.screen?.perfil);
  const btcSrc = screenSrc(result?.screen?.btc);
  const evolucaoSrc = screenSrc(result?.screen?.evolucao);
  const galeria = useMemo(
    () =>
      (result?.screen?.galeria ?? [])
        .map((g) => ({ ...g, src: screenSrc(g.url) }))
        .filter((g) => g.src),
    [result]
  );

  const combined = [report, steps].filter((t) => t && t.trim()).join("\n\n---\n\n");

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
            </div>
            {result.solutes.map((s) => {
              const [bg, fg] = ACCENTS[s.symbol] ?? ["#f1f5f9", "#334155"];
              const dose = s.dose_kg_ha;
              const meta = soluteMeta?.[s.symbol];
              const kdNum = meta?.kd != null && meta.kd !== "" ? parseFloat(String(meta.kd).replace(",", ".")) : NaN;
              const resNum = meta?.residual != null && meta.residual !== "" ? parseFloat(String(meta.residual).replace(",", ".")) : 0;
              // kg/ha vindos do backend (sobre dose+residual); fallback pct×dose.
              const kgOf = (v: number | null | undefined, pct: number) =>
                v !== null && v !== undefined && Number.isFinite(v) ? v : (dose * pct) / 100;
              const retainedKg = kgOf(s.retained_kg_ha, s.retained_root_pct);
              const belowKg = kgOf(s.below_kg_ha, s.below_profile_pct);
              const bottomKg = kgOf(s.bottom_kg_ha, s.bottom_pct);
              const uptKg = kgOf(s.uptaken_kg_ha, s.uptaken_pct);
              const capKg = kgOf(s.capsule_kg_ha, s.capsule_pct ?? 0);
              const resKg = s.residual_kg_ha ?? 0;
              const tableDose = s.dose_input_kg_ha ?? dose;
              const inputKg = s.input_kg_ha ?? dose;
              const inputTxt = resKg > 0.005
                ? `de ${inputKg.toFixed(1)} kg/ha (dose ${tableDose.toFixed(1)} + residual ${resKg.toFixed(1)})`
                : s.is_fertigation
                  ? `de ${dose.toFixed(1)} kg/ha injetados (fertirrigação)`
                  : `de ${dose.toFixed(0)} kg/ha aplicados`;
              return (
                <div className="metric-card metric-nutr" key={s.symbol}>
                  <div className="metric-nutr-head">
                    <span className="metric-nutr-sym" style={{ background: bg, color: fg }}>{s.symbol}</span>
                    <span className="metric-nutr-name">{s.name}</span>
                  </div>
                  <div className="metric-value">{s.retained_root_pct.toFixed(1)}%</div>
                  <div className="metric-label">Retido na camada avaliada (0–{rootDepth.toFixed(0)} cm)</div>
                  <div className="metric-sub">{`${retainedKg.toFixed(1)} kg/ha ${inputTxt}`}</div>
                  <div className="metric-nutr-rows">
                    <div className="metric-nutr-row"><span>Abaixo da camada (no perfil)</span><b>{s.below_profile_pct.toFixed(1)}% · {belowKg.toFixed(1)} kg/ha</b></div>
                    <div className="metric-nutr-row"><span>Atravessou o fundo ({zmax.toFixed(0)} cm)</span><b>{s.bottom_pct.toFixed(1)}% · {bottomKg.toFixed(1)} kg/ha</b></div>
                    {s.uptaken_pct > 0.05 && (
                      <div className="metric-nutr-row"><span>Absorvido pela cultura (limitado pela demanda){s.uptake_capped ? " — limitado pela demanda em parte do período" : ""}{s.uptake_capped && s.uptake_cap_kg_ha != null ? ` (teto no período: ${Number(s.uptake_cap_kg_ha).toFixed(1)} kg/ha)` : ""}</span><b>{s.uptaken_pct.toFixed(1)}% · {uptKg.toFixed(1)} kg/ha</b></div>
                    )}
                    {(s.capsule_pct ?? 0) > 0.05 && (
                      <div className="metric-nutr-row"><span>Ainda no grânulo (não liberado)</span><b>{(s.capsule_pct ?? 0).toFixed(1)}% · {capKg.toFixed(1)} kg/ha</b></div>
                    )}
                    {s.is_fertigation && s.fertigation_c0_mg_l != null && (
                      <div className="metric-nutr-row"><span>C₀ calculado (= dose ÷ lâmina na injeção)</span><b>{s.fertigation_c0_mg_l.toFixed(1)} mg/L</b></div>
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
                  <div className="metric-label">Ganho/Perda de Água no Perfil (θf − θi)</div>
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

          {perfilSrc && (
            <>
              <p className="graph-scroll-hint">Arraste os gráficos para o lado para ver tudo; use o gesto de pinça para ampliar.</p>
              <h3 className="results-section-title">{waterOnly ? "Perfil de Umidade θ(z)" : "Distribuição em Profundidade C(z)"}</h3>
              <div className="graph-white-card">
                <img src={perfilSrc} alt={waterOnly ? "Perfil de Umidade θ(z)" : "Distribuição em Profundidade C(z)"} loading="lazy" />
              </div>
            </>
          )}

          {btcSrc && (
            <>
              <h3 className="results-section-title">{waterOnly ? "Umidade no Tempo θ(t) nos Nós de Observação" : "Séries Temporais nos Nós de Observação"}</h3>
              <div className="graph-white-card">
                <img src={btcSrc} alt="Séries Temporais nos Nós de Observação" loading="lazy" />
              </div>
            </>
          )}

          {evolucaoSrc && (
            <>
              <h3 className="results-section-title">Evolução Temporal do Perfil</h3>
              <div className="graph-white-card">
                <img src={evolucaoSrc} alt="Evolução Temporal do Perfil" loading="lazy" />
              </div>
            </>
          )}

          {galeria.length > 0 && (
            <>
              <h3 className="results-section-title">Por Soluto</h3>
              <div className="graph-white-card">
                <div className="solute-gallery-grid">
                  {galeria.map((g) => (
                    <div className="solute-gallery-frame" key={g.symbol}>
                      <img src={g.src as string} alt={`${g.name} (${g.symbol})`} loading="lazy" />
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}

          {done && (
            <div className="graph-download-actions-row">
              <button className="btn-download-action" onClick={onDownloadGraphs}>Baixar Gráficos (PNG) ⤓</button>
              <button className="btn-download-action" onClick={onDownloadExcel}>Baixar Dados do Perfil (.XLSX) ⤓</button>
            </div>
          )}

          <div className="report-display-card">
            {combined ? (
              <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]}>
                {combined}
              </ReactMarkdown>
            ) : (
              <p className="muted">Carregando laudo…</p>
            )}
          </div>
        </>
      )}
    </>
  );
}
