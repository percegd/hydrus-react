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
  isCustomSoil: boolean;
  setIsCustomSoil: (v: boolean) => void;
  sandPct: string;
  setSandPct: (v: string) => void;
  clayPct: string;
  setClayPct: (v: string) => void;
  thetaR: string;
  setThetaR: (v: string) => void;
  thetaS: string;
  setThetaS: (v: string) => void;
  vgAlpha: string;
  setVgAlpha: (v: string) => void;
  vgN: string;
  setVgN: (v: string) => void;
  ks: string;
  setKs: (v: string) => void;
  bulk: string;
  setBulk: (v: string) => void;
  rosettaNote: string;
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
  isCustomSoil,
  setIsCustomSoil,
  sandPct,
  setSandPct,
  clayPct,
  setClayPct,
  thetaR,
  setThetaR,
  thetaS,
  setThetaS,
  vgAlpha,
  setVgAlpha,
  vgN,
  setVgN,
  ks,
  setKs,
  bulk,
  setBulk,
  rosettaNote,
  error,
  fieldErrors,
  onNext,
}: Props) {
  const comCultura = cropMode === "com";
  return (
    <>
      <div className="form-row">
        <label className="field">Tipo de Solo
          <select value={soil} onChange={(e) => setSoil(e.target.value)} disabled={isCustomSoil}>
            {soils.map((s) => <option key={s.key} value={s.key}>{s.name}</option>)}
          </select>
        </label>
      </div>

      <div className="form-row" style={{ marginTop: 8 }}>
        <label className="field" style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
          <input
            type="checkbox"
            checked={isCustomSoil}
            onChange={(e) => setIsCustomSoil(e.target.checked)}
          />
          Solo Personalizado
        </label>
      </div>

      {isCustomSoil && (
        <div style={{ marginTop: 12 }}>
          <div className="form-row">
            <label className="field">% de Areia ({sandPct}%)
              <input
                type="range"
                min={0}
                max={100}
                step={5}
                value={sandPct}
                onChange={(e) => setSandPct(e.target.value)}
              />
            </label>
            <label className="field">% de Argila ({clayPct}%)
              <input
                type="range"
                min={0}
                max={100}
                step={5}
                value={clayPct}
                onChange={(e) => setClayPct(e.target.value)}
              />
            </label>
          </div>
          {rosettaNote && <p className="hint-text">{rosettaNote}</p>}
        </div>
      )}

      <h3 className="section-title" style={{ marginTop: 20 }}>Propriedades Físico-Hídricas do Solo (van Genuchten - Mualem)</h3>
      <div className="form-row">
        <label className="field">θr - Umidade residual [cm³/cm³]
          <input value={thetaR} onChange={(e) => setThetaR(e.target.value)} inputMode="decimal" type="number" step="any" min={0} max={1} />
        </label>
        <label className="field">θs - Umidade de saturação [cm³/cm³]
          <input value={thetaS} onChange={(e) => setThetaS(e.target.value)} inputMode="decimal" type="number" step="any" min={0} max={1} />
        </label>
        <label className="field">α - Parâmetro de escala (entrada de ar) [1/cm]
          <input value={vgAlpha} onChange={(e) => setVgAlpha(e.target.value)} inputMode="decimal" type="number" step="any" min={0} />
        </label>
      </div>
      <div className="form-row" style={{ marginTop: 8 }}>
        <label className="field">n - Índice de poros [-]
          <input value={vgN} onChange={(e) => setVgN(e.target.value)} inputMode="decimal" type="number" step="any" min={0} />
        </label>
        <label className="field">Ks - Condutividade saturada [cm/dia]
          <input value={ks} onChange={(e) => setKs(e.target.value)} inputMode="decimal" type="number" step="any" min={0} />
        </label>
        <label className="field">ρb - Densidade aparente [g/cm³]
          <input value={bulk} onChange={(e) => setBulk(e.target.value)} inputMode="decimal" type="number" step="any" min={0} />
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
