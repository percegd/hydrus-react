"use client";

import { useEffect, useState } from "react";
import { getCrops, getSoils, postSimulate, type Crop, type SimulateResponse, type Soil } from "../lib/api";

const card: React.CSSProperties = { background: "#fff", border: "1px solid #e2e8f0", borderRadius: 12, padding: 16 };

export default function Home() {
  const [soils, setSoils] = useState<Soil[]>([]);
  const [crops, setCrops] = useState<Crop[]>([]);
  const [soil, setSoil] = useState("latossolo_medio");
  const [crop, setCrop] = useState("soja");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<SimulateResponse | null>(null);

  useEffect(() => {
    getSoils().then(setSoils).catch(() => setError("API fora do ar (backend :8001)."));
    getCrops().then(setCrops).catch(() => {});
  }, []);

  async function run() {
    setLoading(true);
    setError("");
    try {
      const res = await postSimulate({
        soil_key: soil,
        crop_key: crop,
        depth_cm: 200,
        total_days: 30,
        rain_mm: 50,
        solutes: [{ symbol: "K", name: "Potássio", dose_kg_ha: 30, kd: 0.45 }],
      });
      setResult(res);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main style={{ maxWidth: 960, margin: "0 auto", padding: 24 }}>
      <h1>Hydrus 1D <span style={{ fontWeight: 400, fontSize: 16 }}>(nova stack — fase 1)</span></h1>
      <section style={{ ...card, display: "flex", gap: 12, alignItems: "end", flexWrap: "wrap" }}>
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
        <button onClick={run} disabled={loading} style={{ padding: "8px 20px" }}>
          {loading ? "Calculando…" : "Calcular"}
        </button>
      </section>
      {error && <p style={{ color: "#b91c1c" }}>{error}</p>}
      {result && (
        <section style={{ display: "grid", gap: 16, marginTop: 16 }}>
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
        </section>
      )}
    </main>
  );
}
