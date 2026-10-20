"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import "katex/dist/katex.min.css";
import MetricsCards from "../components/MetricsCards";
import WizardProgress from "../components/WizardProgress";
import { getCrops, getJob, getReport, getSoils, postJob, type Crop, type SimulateResponse, type Soil } from "../lib/api";

const SPECIES = [
  { symbol: "N", name: "Nitrato", kd: 0 },
  { symbol: "K", name: "Potássio", kd: 0.45 },
  { symbol: "P", name: "Fósforo", kd: 25 },
  { symbol: "S", name: "Enxofre", kd: 0.15 },
  { symbol: "Ca", name: "Cálcio", kd: 1.2 },
  { symbol: "Mg", name: "Magnésio", kd: 0.8 },
];

type Row = { symbol: string; name: string; dose: string; kd: string; rel: string; relDays: string };

const STEP_TITLES = [
  { title: "Passo 1 de 3: Solo, cultura e água", sub: "Defina o cenário físico da simulação." },
  { title: "Passo 2 de 3: Nutrientes e manejo", sub: "Solutos, doses, liberação e aplicação." },
  { title: "Resultados da Modelagem Física 1D", sub: "Balanço de água e nutrientes consolidado com base na Equação de Richards e Advecção-Dispersão." },
];

export default function Home() {
  const [step, setStep] = useState(1);
  const [soils, setSoils] = useState<Soil[]>([]);
  const [crops, setCrops] = useState<Crop[]>([]);
  const [soil, setSoil] = useState("latossolo_medio");
  const [crop, setCrop] = useState("soja");
  const [days, setDays] = useState("30");
  const [rainMode, setRainMode] = useState<"uniform" | "series">("uniform");
  const [rainMm, setRainMm] = useState("50");
  const [series, setSeries] = useState("");
  const [et0Series, setEt0Series] = useState("");
  const [rows, setRows] = useState<Row[]>([{ symbol: "K", name: "Potássio", dose: "30", kd: "0.45", rel: "immediate", relDays: "60" }]);
  const [placement, setPlacement] = useState("surface");
  const [appDay, setAppDay] = useState("0");
  const [c0, setC0] = useState("20");
  const [pulse, setPulse] = useState("0");
  const [jobId, setJobId] = useState("");
  const [jobState, setJobState] = useState("");
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState("");
  const [result, setResult] = useState<SimulateResponse | null>(null);
  const [report, setReport] = useState("");
  const [showRestartModal, setShowRestartModal] = useState(false);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    getSoils().then(setSoils).catch(() => setError("API fora do ar (backend :8001)."));
    getCrops().then(setCrops).catch(() => {});
    return () => { if (timer.current) clearInterval(timer.current); };
  }, []);

  function setRow(i: number, patch: Partial<Row>) {
    setRows((rs) => rs.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  }
  function addRow() {
    const used = new Set(rows.map((r) => r.symbol));
    const next = SPECIES.find((s) => !used.has(s.symbol)) ?? SPECIES[0];
    setRows((rs) => [...rs, { symbol: next.symbol, name: next.name, dose: "30", kd: String(next.kd), rel: "immediate", relDays: "60" }]);
  }

  function parseSeries(text: string): number[] | undefined {
    if (!text.trim()) return undefined;
    const vals = text.split(/[\s,;]+/).filter(Boolean).map(Number);
    if (vals.some((v) => Number.isNaN(v) || v < 0)) throw new Error("Série inválida (só números ≥ 0).");
    return vals;
  }

  async function run() {
    setError("");
    setResult(null);
    setReport("");
    let rain_series: number[] | undefined;
    let total_days = parseFloat(days) || 30;
    let et0_series: number[] | undefined;
    try {
      if (rainMode === "series") {
        rain_series = parseSeries(series);
        if (!rain_series?.length) { setError("Cole a série diária de chuva."); return; }
        total_days = rain_series.length;
      }
      et0_series = parseSeries(et0Series);
    } catch (e) { setError(String((e as Error).message || e)); return; }
    const solutes = rows
      .filter((r) => parseFloat(r.dose) > 0)
      .map((r) => ({
        symbol: r.symbol, name: r.name, dose_kg_ha: parseFloat(r.dose), kd: parseFloat(r.kd) || 0,
        release_type: r.rel === "controlled" ? "controlled" : "immediate", release_days: parseFloat(r.relDays) || 60,
      }));
    if (!solutes.length) { setError("Informe ao menos 1 soluto com dose > 0."); return; }
    setStep(3);
    setJobState("queued");
    try {
      const body = {
        soil_key: soil, crop_key: crop, depth_cm: 200, total_days,
        rain_mm: parseFloat(rainMm) || 0, rain_series,
        et0_series, solutes,
        placement: {
          mode: placement, z_top_cm: 0, z_bottom_cm: 2,
          fertigation_c0_mg_l: parseFloat(c0) || 0, fertigation_pulse_days: parseFloat(pulse) || 0,
          application_day: parseFloat(appDay) || 0,
        },
      };
      const { job_id } = await postJob(body);
      setJobId(job_id);
      setJobState("running");
      timer.current = setInterval(async () => {
        try {
          const st = await getJob(job_id);
          setElapsed(st.elapsed_s);
          if (st.status === "done") {
            if (timer.current) clearInterval(timer.current);
            setJobState("done");
            setResult(st.result);
            try {
              const rep = await getReport(job_id);
              setReport(rep.report_markdown);
            } catch { /* laudo indisponível: mantém tela sem laudo */ }
          } else if (st.status === "failed") {
            if (timer.current) clearInterval(timer.current);
            setJobState("failed");
            setError(st.error || "Falha na simulação.");
          } else {
            setJobState(st.status);
          }
        } catch { /* mantém polling */ }
      }, 1000);
    } catch (e) {
      setJobState("failed");
      setError(String(e));
    }
  }

  function confirmRestart() {
    if (timer.current) clearInterval(timer.current);
    setShowRestartModal(false);
    setStep(1);
    setJobId("");
    setJobState("");
    setResult(null);
    setReport("");
    setError("");
  }

  const perfilSrc = result?.images.perfil ?? result?.images.agua ?? null;

  return (
    <div className="hydrus-container">
      <header className="app-header">
        <h1 className="app-title"><span className="leaf">🌱</span> Simulação e Física de Solos</h1>
        <div className="app-subtitle">Simulação de transporte de água e nutrientes no perfil do solo</div>
      </header>

      <WizardProgress current={step} />

      <div className="wizard-step-box">
        <div className="wizard-question-header">
          <h2 className="wizard-question-title">{STEP_TITLES[step - 1].title}</h2>
          <p className="wizard-question-subtitle">{STEP_TITLES[step - 1].sub}</p>
        </div>

        {step === 1 && (
          <>
            <div className="form-row">
              <label className="field">Solo
                <select value={soil} onChange={(e) => setSoil(e.target.value)}>
                  {soils.map((s) => <option key={s.key} value={s.key}>{s.name}</option>)}
                </select>
              </label>
              <label className="field">Cultura
                <select value={crop} onChange={(e) => setCrop(e.target.value)}>
                  {crops.map((c) => <option key={c.key} value={c.key}>{c.name} (raiz {c.root_depth_cm} cm)</option>)}
                </select>
              </label>
              <label className="field">Dias
                <input value={days} onChange={(e) => setDays(e.target.value)} />
              </label>
              <label className="field">Chuva
                <select value={rainMode} onChange={(e) => setRainMode(e.target.value as "uniform" | "series")}>
                  <option value="uniform">Lâmina uniforme</option>
                  <option value="series">Série diária</option>
                </select>
              </label>
              {rainMode === "uniform" && (
                <label className="field">Total (mm)
                  <input value={rainMm} onChange={(e) => setRainMm(e.target.value)} />
                </label>
              )}
            </div>
            {rainMode === "series" && (
              <div className="form-row" style={{ marginTop: 12 }}>
                <label className="field" style={{ flex: "1 1 100%" }}>Série diária de chuva (mm, separados por espaço/vírgula/linha)
                  <textarea rows={3} value={series} onChange={(e) => setSeries(e.target.value)} placeholder="0 0 12.5 0 3 ..." />
                </label>
              </div>
            )}
            <div className="form-row" style={{ marginTop: 12 }}>
              <label className="field" style={{ flex: "1 1 100%" }}>Série diária de ET0, opcional (mm/dia)
                <textarea rows={2} value={et0Series} onChange={(e) => setEt0Series(e.target.value)} placeholder="4 4.1 3.8 ..." />
              </label>
            </div>
            {error && <p className="error-text">{error}</p>}
            <div className="btn-row">
              <button className="btn btn-primary" onClick={() => setStep(2)}>Avançar</button>
            </div>
          </>
        )}

        {step === 2 && (
          <>
            {rows.map((r, i) => (
              <div className="nutrient-row" key={i}>
                <label className="field">Soluto
                  <select value={r.symbol} onChange={(e) => {
                    const sp = SPECIES.find((s) => s.symbol === e.target.value)!;
                    setRow(i, { symbol: sp.symbol, name: sp.name, kd: String(sp.kd) });
                  }}>
                    {SPECIES.map((s) => <option key={s.symbol} value={s.symbol}>{s.symbol} · {s.name}</option>)}
                  </select>
                </label>
                <label className="field">Dose (kg/ha)
                  <input value={r.dose} onChange={(e) => setRow(i, { dose: e.target.value })} />
                </label>
                <label className="field">Kd (cm³/g)
                  <input value={r.kd} onChange={(e) => setRow(i, { kd: e.target.value })} />
                </label>
                <label className="field">Liberação
                  <select value={r.rel} onChange={(e) => setRow(i, { rel: e.target.value })}>
                    <option value="immediate">Imediata</option>
                    <option value="controlled">Controlada</option>
                  </select>
                </label>
                {r.rel === "controlled" && (
                  <label className="field">Dias
                    <input value={r.relDays} onChange={(e) => setRow(i, { relDays: e.target.value })} />
                  </label>
                )}
                <button className="icon-btn" onClick={() => setRows((rs) => rs.filter((_, j) => j !== i))} title="Remover">✕</button>
              </div>
            ))}
            <button className="btn" onClick={addRow}>+ soluto</button>

            <h3 className="section-title" style={{ marginTop: 20 }}>Aplicação</h3>
            <div className="form-row">
              <label className="field">Modo
                <select value={placement} onChange={(e) => setPlacement(e.target.value)}>
                  <option value="surface">Superfície (0–2 cm)</option>
                  <option value="furrow">Sulco (5–10 cm)</option>
                  <option value="fertigation">Fertirrigação</option>
                </select>
              </label>
              <label className="field">Dia da aplicação
                <input value={appDay} onChange={(e) => setAppDay(e.target.value)} />
              </label>
              {placement === "fertigation" && (
                <>
                  <label className="field">C₀ (mg/L)
                    <input value={c0} onChange={(e) => setC0(e.target.value)} />
                  </label>
                  <label className="field">Pulso (dias, 0=contínuo)
                    <input value={pulse} onChange={(e) => setPulse(e.target.value)} />
                  </label>
                </>
              )}
            </div>
            {error && <p className="error-text">{error}</p>}
            <div className="btn-row">
              <button className="btn" onClick={() => setStep(1)}>Voltar</button>
              <button className="btn btn-primary" onClick={run}>Calcular Resultados</button>
            </div>
          </>
        )}

        {step === 3 && (
          <>
            <div className="btn-row" style={{ marginTop: 0, marginBottom: 12 }}>
              <button className="btn" onClick={() => { if (timer.current) clearInterval(timer.current); setStep(2); setResult(null); setReport(""); }}>← Editar</button>
            </div>
            <p className="muted">Status: <strong>{jobState || "—"}</strong> {(jobState === "running" || jobState === "queued") && <span>({elapsed}s)</span>}</p>
            {error && <p className="error-text">{error}</p>}
            {result && (
              <>
                <MetricsCards result={result} />

                {perfilSrc && (
                  <>
                    <h3 className="section-title">Distribuição em Profundidade C(z)</h3>
                    <div className="graph-white-card" style={{ marginBottom: 16 }}>
                      <img src={`data:image/png;base64,${perfilSrc}`} alt="Distribuição em profundidade" style={{ width: "100%" }} />
                    </div>
                  </>
                )}

                {result.images.btc && (
                  <>
                    <h3 className="section-title">Curvas de Avanço no Tempo C(t) e θ(t)</h3>
                    <div className="graph-white-card" style={{ marginBottom: 16 }}>
                      <img src={`data:image/png;base64,${result.images.btc}`} alt="Curvas de avanço no tempo" style={{ width: "100%" }} />
                    </div>
                  </>
                )}

                {result.images.evolucao && (
                  <>
                    <h3 className="section-title">Evolução Temporal do Perfil</h3>
                    <div className="graph-white-card" style={{ marginBottom: 16 }}>
                      <img src={`data:image/png;base64,${result.images.evolucao}`} alt="Evolução temporal do perfil" style={{ width: "100%" }} />
                    </div>
                  </>
                )}

                {result.images.galeria.length > 0 && (
                  <>
                    <h3 className="section-title">Por Soluto</h3>
                    <div className="solute-gallery-grid" style={{ marginBottom: 16 }}>
                      {result.images.galeria.map((g) => (
                        <div className="graph-white-card" key={g.symbol}>
                          <img src={`data:image/png;base64,${g.png}`} alt={`${g.name} (${g.symbol})`} style={{ width: "100%" }} />
                        </div>
                      ))}
                    </div>
                  </>
                )}

                {jobState === "done" && (
                  <div className="graph-download-actions-row">
                    <a className="btn-download-action" href={`/api/jobs/${jobId}/graficos.zip`}>Baixar Gráficos (PNG) ⤓</a>
                    <a className="btn-download-action" href={`/api/jobs/${jobId}/excel`}>Baixar Dados do Perfil (.XLSX) ⤓</a>
                  </div>
                )}

                {report && (
                  <div className="report-display-card">
                    <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]}>
                      {report}
                    </ReactMarkdown>
                  </div>
                )}

                <div className="btn-row" style={{ marginTop: 20 }}>
                  <button className="btn btn-primary" onClick={() => setShowRestartModal(true)}>Nova Simulação</button>
                </div>
              </>
            )}

            {showRestartModal && (
              <div className="confirm-modal-overlay" onClick={() => setShowRestartModal(false)}>
                <div className="confirm-modal-card" onClick={(e) => e.stopPropagation()}>
                  <div style={{ display: "flex", alignItems: "flex-start", gap: 16, marginBottom: 8 }}>
                    <div style={{ width: 48, height: 48, borderRadius: 12, background: "#ecfdf5", display: "flex", alignItems: "center", justifyContent: "center", color: "#059669", flexShrink: 0, boxShadow: "0 2px 6px rgba(5, 150, 105, 0.12)" }}>
                      <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"></path><path d="M21 3v5h-5"></path><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"></path><path d="M8 16H3v5"></path></svg>
                    </div>
                    <div style={{ flex: 1 }}>
                      <h3 style={{ margin: 0, fontSize: 19, fontWeight: 700, color: "#111827", letterSpacing: "-0.01em" }}>Iniciar Nova Simulação?</h3>
                      <p style={{ margin: "8px 0 0 0", fontSize: 14.5, color: "#4b5563", lineHeight: 1.55 }}>Você retornará ao primeiro passo da modelagem. Os resultados calculados atualmente nesta tela serão substituídos.</p>
                    </div>
                  </div>
                  <div className="modal-actions">
                    <button className="btn-modal-cancel" onClick={() => setShowRestartModal(false)}>Cancelar</button>
                    <button className="btn-modal-confirm" onClick={confirmRestart}>Confirmar e Reiniciar</button>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
