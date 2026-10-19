"use client";

import { useEffect, useRef, useState } from "react";
import ProfileChart from "../components/ProfileChart";
import { getCrops, getJob, getSoils, postJob, type Crop, type SimulateResponse, type Soil } from "../lib/api";

const card: React.CSSProperties = { background: "#fff", border: "1px solid #e2e8f0", borderRadius: 12, padding: 16 };
const input: React.CSSProperties = { padding: 6, border: "1px solid #cbd5e1", borderRadius: 6, width: 90 };

const SPECIES = [
  { symbol: "N", name: "Nitrato", kd: 0 },
  { symbol: "K", name: "Potássio", kd: 0.45 },
  { symbol: "P", name: "Fósforo", kd: 25 },
  { symbol: "S", name: "Enxofre", kd: 0.15 },
  { symbol: "Ca", name: "Cálcio", kd: 1.2 },
  { symbol: "Mg", name: "Magnésio", kd: 0.8 },
];

type Row = { symbol: string; name: string; dose: string; kd: string; rel: string; relDays: string };

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
    try {
      if (rainMode === "series") {
        rain_series = parseSeries(series);
        if (!rain_series?.length) { setError("Cole a série diária de chuva."); return; }
        total_days = rain_series.length;
      }
      var et0_series = parseSeries(et0Series);
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

  return (
    <main style={{ maxWidth: 960, margin: "0 auto", padding: 24 }}>
      <h1>Hydrus 1D <span style={{ fontWeight: 400, fontSize: 16 }}>(fase 2 — manejo + Plotly)</span></h1>
      <p>Passo {step} de 3</p>

      {step === 1 && (
        <section style={{ ...card, display: "flex", gap: 12, flexWrap: "wrap", alignItems: "end" }}>
          <label>Solo<br />
            <select value={soil} onChange={(e) => setSoil(e.target.value)}>
              {soils.map((s) => <option key={s.key} value={s.key}>{s.name}</option>)}
            </select>
          </label>
          <label>Cultura<br />
            <select value={crop} onChange={(e) => setCrop(e.target.value)}>
              {crops.map((c) => <option key={c.key} value={c.key}>{c.name} (raiz {c.root_depth_cm} cm)</option>)}
            </select>
          </label>
          <label>Dias<br /><input style={input} value={days} onChange={(e) => setDays(e.target.value)} /></label>
          <label>Chuva<br />
            <select value={rainMode} onChange={(e) => setRainMode(e.target.value as "uniform" | "series")}>
              <option value="uniform">Lâmina uniforme</option>
              <option value="series">Série diária</option>
            </select>
          </label>
          {rainMode === "uniform" ? (
            <label>Total (mm)<br /><input style={input} value={rainMm} onChange={(e) => setRainMm(e.target.value)} /></label>
          ) : (
            <label style={{ flexBasis: "100%" }}>Série diária de chuva (mm)<br />
              <textarea rows={3} style={{ width: "100%" }} value={series} onChange={(e) => setSeries(e.target.value)} placeholder="0 0 12.5 0 3 ..." />
            </label>
          )}
          <label style={{ flexBasis: "100%" }}>Série diária de ET0, opcional (mm/dia)<br />
            <textarea rows={2} style={{ width: "100%" }} value={et0Series} onChange={(e) => setEt0Series(e.target.value)} placeholder="4 4.1 3.8 ..." />
          </label>
          <button onClick={() => setStep(2)} style={{ padding: "8px 20px" }}>Avançar</button>
        </section>
      )}

      {step === 2 && (
        <section style={{ display: "grid", gap: 16 }}>
          <div style={card}>
            {rows.map((r, i) => (
              <div key={i} style={{ display: "flex", gap: 8, marginBottom: 8, alignItems: "center", flexWrap: "wrap" }}>
                <select value={r.symbol} onChange={(e) => {
                  const sp = SPECIES.find((s) => s.symbol === e.target.value)!;
                  setRow(i, { symbol: sp.symbol, name: sp.name, kd: String(sp.kd) });
                }}>
                  {SPECIES.map((s) => <option key={s.symbol} value={s.symbol}>{s.symbol} · {s.name}</option>)}
                </select>
                <label>Dose <input style={input} value={r.dose} onChange={(e) => setRow(i, { dose: e.target.value })} /></label>
                <label>Kd <input style={input} value={r.kd} onChange={(e) => setRow(i, { kd: e.target.value })} /></label>
                <label>Liberação
                  <select value={r.rel} onChange={(e) => setRow(i, { rel: e.target.value })}>
                    <option value="immediate">Imediata</option>
                    <option value="controlled">Controlada</option>
                  </select>
                </label>
                {r.rel === "controlled" && (
                  <label>Dias <input style={input} value={r.relDays} onChange={(e) => setRow(i, { relDays: e.target.value })} /></label>
                )}
                <button onClick={() => setRows((rs) => rs.filter((_, j) => j !== i))}>✕</button>
              </div>
            ))}
            <button onClick={addRow}>+ soluto</button>
          </div>
          <div style={card}>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "end" }}>
              <label>Aplicação<br />
                <select value={placement} onChange={(e) => setPlacement(e.target.value)}>
                  <option value="surface">Superfície (0–2 cm)</option>
                  <option value="furrow">Sulco (5–10 cm)</option>
                  <option value="fertigation">Fertirrigação</option>
                </select>
              </label>
              <label>Dia da aplicação<br /><input style={input} value={appDay} onChange={(e) => setAppDay(e.target.value)} /></label>
              {placement === "fertigation" && (
                <>
                  <label>C₀ (mg/L)<br /><input style={input} value={c0} onChange={(e) => setC0(e.target.value)} /></label>
                  <label>Pulso (dias, 0=contínuo)<br /><input style={input} value={pulse} onChange={(e) => setPulse(e.target.value)} /></label>
                </>
              )}
            </div>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button onClick={() => setStep(1)}>Voltar</button>
            <button onClick={run} style={{ padding: "8px 20px" }}>Calcular</button>
          </div>
        </section>
      )}

      {step === 3 && (
        <section style={{ display: "grid", gap: 16 }}>
          <div style={card}>
            <button onClick={() => { if (timer.current) clearInterval(timer.current); setStep(2); setResult(null); setReport(""); }}>← Editar</button>
            <p>Status: <strong>{jobState || "—"}</strong> {jobState === "running" && <span>({elapsed}s)</span>}</p>
            {error && <p style={{ color: "#b91c1c" }}>{error}</p>}
            {jobState === "done" && (
              <div style={{ display: "flex", gap: 8 }}>
                <a href={`/api/jobs/${jobId}/excel`}><button>Baixar Excel</button></a>
                <button onClick={loadReport}>Ver laudo</button>
              </div>
            )}
          </div>
          {result && (
            <>
              <div style={card}>
                <strong>Drenagem: {result.drainage_mm.toFixed(1)} mm</strong>
                {result.solutes.map((s) => (
                  <div key={s.symbol} style={{ marginTop: 8 }}>
                    <strong>{s.name} ({s.symbol})</strong> — retido {s.retained_root_pct.toFixed(1)}% ·
                    abaixo {s.below_profile_pct.toFixed(1)}% · fundo {s.bottom_pct.toFixed(1)}% ·
                    absorvido {s.uptaken_pct.toFixed(1)}% · pico {s.peak_depth_cm ?? "—"} cm
                  </div>
                ))}
              </div>
              {result.profiles && <div style={card}><ProfileChart profiles={result.profiles as never} rootDepth={rootDepth} /></div>}
              {result.plot_png_base64 && (
                <div style={card}>
                  <img src={`data:image/png;base64,${result.plot_png_base64}`} alt="Perfil" style={{ width: "100%" }} />
                </div>
              )}
              {report && <div style={{ ...card, whiteSpace: "pre-wrap", fontSize: 13 }}><pre style={{ margin: 0 }}>{report}</pre></div>}
            </>
          )}
        </section>
      )}
    </main>
  );
}
