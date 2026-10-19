"use client";

import { useEffect, useRef, useState } from "react";
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

type Row = { symbol: string; name: string; dose: string; kd: string };

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
  const [rows, setRows] = useState<Row[]>([{ symbol: "K", name: "Potássio", dose: "30", kd: "0.45" }]);
  const [jobState, setJobState] = useState("");
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState("");
  const [result, setResult] = useState<SimulateResponse | null>(null);
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
    setRows((rs) => [...rs, { symbol: next.symbol, name: next.name, dose: "30", kd: String(next.kd) }]);
  }

  async function run() {
    setError("");
    setResult(null);
    let rain_series: number[] | undefined;
    let total_days = parseFloat(days) || 30;
    if (rainMode === "series") {
      rain_series = series.split(/[\s,;]+/).filter(Boolean).map(Number);
      if (rain_series.some((v) => Number.isNaN(v) || v < 0)) { setError("Série diária inválida (só números ≥ 0)."); return; }
      if (!rain_series.length) { setError("Cole a série diária (um valor por dia)."); return; }
      total_days = rain_series.length;
    }
    const solutes = rows
      .filter((r) => parseFloat(r.dose) > 0)
      .map((r) => ({ symbol: r.symbol, name: r.name, dose_kg_ha: parseFloat(r.dose), kd: parseFloat(r.kd) || 0 }));
    if (!solutes.length) { setError("Informe ao menos 1 soluto com dose > 0."); return; }
    setStep(3);
    setJobState("queued");
    try {
      const body = { soil_key: soil, crop_key: crop, depth_cm: 200, total_days, rain_mm: parseFloat(rainMm) || 0, rain_series: rain_series, solutes };
      const { job_id } = await postJob(body);
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
        } catch (e) { /* mantém polling */ }
      }, 1000);
    } catch (e) {
      setJobState("failed");
      setError(String(e));
    }
  }

  return (
    <main style={{ maxWidth: 960, margin: "0 auto", padding: 24 }}>
      <h1>Hydrus 1D <span style={{ fontWeight: 400, fontSize: 16 }}>(fase 1 — jobs + wizard)</span></h1>
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
            <label style={{ flexBasis: "100%" }}>Série diária (mm, separados por espaço/vírgula/linha)<br />
              <textarea rows={3} style={{ width: "100%" }} value={series} onChange={(e) => setSeries(e.target.value)} placeholder="0 0 12.5 0 3 ..." />
            </label>
          )}
          <button onClick={() => setStep(2)} style={{ padding: "8px 20px" }}>Avançar</button>
        </section>
      )}

      {step === 2 && (
        <section style={card}>
          {rows.map((r, i) => (
            <div key={i} style={{ display: "flex", gap: 8, marginBottom: 8, alignItems: "center" }}>
              <select value={r.symbol} onChange={(e) => {
                const sp = SPECIES.find((s) => s.symbol === e.target.value)!;
                setRow(i, { symbol: sp.symbol, name: sp.name, kd: String(sp.kd) });
              }}>
                {SPECIES.map((s) => <option key={s.symbol} value={s.symbol}>{s.symbol} · {s.name}</option>)}
              </select>
              <label>Dose <input style={input} value={r.dose} onChange={(e) => setRow(i, { dose: e.target.value })} /></label>
              <label>Kd <input style={input} value={r.kd} onChange={(e) => setRow(i, { kd: e.target.value })} /></label>
              <button onClick={() => setRows((rs) => rs.filter((_, j) => j !== i))}>✕</button>
            </div>
          ))}
          <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
            <button onClick={addRow}>+ soluto</button>
            <button onClick={() => setStep(1)}>Voltar</button>
            <button onClick={run} style={{ padding: "8px 20px" }}>Calcular</button>
          </div>
        </section>
      )}

      {step === 3 && (
        <section style={{ display: "grid", gap: 16 }}>
          <div style={card}>
            <button onClick={() => { if (timer.current) clearInterval(timer.current); setStep(2); setResult(null); }}>← Editar solutos</button>
            <p>Status: <strong>{jobState || "—"}</strong> {jobState === "running" && <span>({elapsed}s)</span>}</p>
            {error && <p style={{ color: "#b91c1c" }}>{error}</p>}
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
              {result.plot_png_base64 && (
                <div style={card}>
                  <img src={`data:image/png;base64,${result.plot_png_base64}`} alt="Perfil" style={{ width: "100%" }} />
                </div>
              )}
            </>
          )}
        </section>
      )}
    </main>
  );
}
