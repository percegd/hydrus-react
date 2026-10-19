"use client";

import type { Crop, Soil } from "../lib/api";

type Props = {
  soils: Soil[];
  crops: Crop[];
  soil: string;
  setSoil: (v: string) => void;
  crop: string;
  setCrop: (v: string) => void;
  error: string;
  fieldErrors: string[];
  onNext: () => void;
};

export default function StepSoil({ soils, crops, soil, setSoil, crop, setCrop, error, fieldErrors, onNext }: Props) {
  return (
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
      </div>
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
