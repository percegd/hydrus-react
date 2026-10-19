"use client";

import { useEffect, useRef, useState } from "react";
import ProfileChart from "../components/ProfileChart";
import WizardProgress from "../components/WizardProgress";
import { getCrops, getJob, getSoils, postJob, type Crop, type SimulateResponse, type Soil } from "../lib/api";

const ACCENTS: Record<string, [string, string]> = {
  N: ["#fff7ed", "#c2410c"],
  K: ["#f5f3ff", "#6d28d9"],
  P: ["#f7fee7", "#4d7c0f"],
  S: ["#fefce8", "#a16207"],
  Ca: ["#ecfdf5", "#047857"],
  Mg: ["#fdf2f8", "#be185d"],
};

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
  { title: "Passo 3 de 3: Resultados", sub: "Balanço de massa, perfil e laudo." },
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

  async function loadReport() {
    try {
      const r = await fetch(`/api/jobs/${jobId}/report`);
      const j = await r.json();
      setReport(j.report_markdown as string);
    } catch (e) { setError(String(e)); }
  }

  const rootDepth = crops.find((c) => c.key === crop)?.root_depth_cm ?? 35;
  const cropName = crops.find((c) => c.key === crop)?.name ?? crop;

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
              {jobState === "done" && (
                <>
                  <a href={`/api/jobs/${jobId}/excel`}><button className="btn">Baixar Excel</button></a>
                  <button className="btn" onClick={loadReport}>Ver laudo</button>
                </>
              )}
            </div>
            <p className="muted">Status: <strong>{jobState || "—"}</strong> {jobState === "running" && <span>({elapsed}s)</span>}</p>
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
                {result.plot_png_base64 && (
                  <div className="wizard-step-box" style={{ padding: 16, marginBottom: 16 }}>
                    <img src={`data:image/png;base64,${result.plot_png_base64}`} alt="Perfil" style={{ width: "100%" }} />
                  </div>
                )}
                {report && <div className="wizard-step-box" style={{ padding: 16 }}><pre className="laudo-pre">{report}</pre></div>}
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
