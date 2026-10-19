"use client";

import type { Crop, Soil } from "../lib/api";

type Props = {
  soils: Soil[];
  crops: Crop[];
  soil: string;
  setSoil: (v: string) => void;
  cropMode: string;
  setCropMode: (v: string) => void;
  crop: string;
  setCrop: (v: string) => void;
  depthCm: string;
  setDepthCm: (v: string) => void;
  rootDepthCm: string;
  setRootDepthCm: (v: string) => void;
  error: string;
  fieldErrors: string[];
  onNext: () => void;
};

export default function StepSoil({
  soils,
  crops,
  soil,
  setSoil,
  cropMode,
  setCropMode,
  crop,
  setCrop,
  depthCm,
  setDepthCm,
  rootDepthCm,
  setRootDepthCm,
  error,
  fieldErrors,
  onNext,
}: Props) {
  const comCultura = cropMode === "com";
  return (
    <>
      <div className="form-row">
        <label className="field">Tipo de Solo
          <select value={soil} onChange={(e) => setSoil(e.target.value)}>
            {soils.map((s) => <option key={s.key} value={s.key}>{s.name}</option>)}
          </select>
        </label>
      </div>

      <details style={{ marginTop: 16 }}>
        <summary>Avançado</summary>
        <div className="form-row" style={{ marginTop: 12 }}>
          <label className="field">Profundidade do perfil [cm] (máx 300)
            <input
              value={depthCm}
              onChange={(e) => setDepthCm(e.target.value)}
              inputMode="decimal"
              type="number"
              min={1}
              max={300}
            />
          </label>
        </div>
      </details>

      <h3 className="section-title" style={{ marginTop: 20 }}>Cultura (Transpiração e Absorção Radicular)</h3>
      <div className="form-row" role="radiogroup" aria-label="Modo de cultura">
        <label className="field" style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
          <input
            type="radio"
            name="crop-mode"
            value="sem"
            checked={!comCultura}
            onChange={() => setCropMode("sem")}
          />
          Sem cultura
        </label>
        <label className="field" style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
          <input
            type="radio"
            name="crop-mode"
            value="com"
            checked={comCultura}
            onChange={() => setCropMode("com")}
          />
          Com cultura
        </label>
      </div>

      {comCultura && (
        <div className="form-row" style={{ marginTop: 12 }}>
          <label className="field">Cultura agrícola
            <select value={crop} onChange={(e) => setCrop(e.target.value)}>
              {crops.map((c) => <option key={c.key} value={c.key}>{c.name} (raiz {c.root_depth_cm} cm)</option>)}
            </select>
          </label>
          <label className="field">Profundidade radicular [cm]
            <input
              value={rootDepthCm}
              onChange={(e) => setRootDepthCm(e.target.value)}
              inputMode="decimal"
              type="number"
              min={1}
            />
          </label>
        </div>
      )}

      {fieldErrors.length > 0 && (
        <ul className="error-text">
          {fieldErrors.map((m, i) => <li key={i}>{m}</li>)}
        </ul>
      )}
      {error && <p className="error-text">{error}</p>}
      <div className="btn-row">
        <button className="btn btn-primary" onClick={onNext}>Avançar</button>
      </div>
    </>
  );
}
