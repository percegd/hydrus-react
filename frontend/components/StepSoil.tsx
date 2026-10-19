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
};

function SoilLayersIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M3 9.5h18" />
      <path d="M3 14.5h18" />
    </svg>
  );
}

function SeedlingIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
      <path d="M7 20h10" />
      <path d="M12 20v-9" />
      <path d="M12 11c0-3.3 2.2-5.5 5.5-5.5C17.5 8.8 15.3 11 12 11z" />
      <path d="M12 11C12 7.7 9.8 5.5 6.5 5.5 6.5 8.8 8.7 11 12 11z" />
    </svg>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
    </label>
  );
}

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
}: Props) {
  const comCultura = cropMode === "com";
  return (
    <>
      <div className="form-row">
        <Field label="Tipo de Solo">
          <select value={soil} onChange={(e) => setSoil(e.target.value)} disabled={isCustomSoil}>
            {soils.map((s) => <option key={s.key} value={s.key}>{s.name}</option>)}
          </select>
        </Field>
      </div>

      <div className="custom-toggle-chk">
        <label>
          <input
            type="checkbox"
            className="switch"
            checked={isCustomSoil}
            onChange={(e) => setIsCustomSoil(e.target.checked)}
          />
          Solo Personalizado
        </label>
      </div>

      {isCustomSoil && (
        <div className="custom-param-box">
          <span className="param-subheading">Granulometria do Solo Personalizado (Cálculo Automático Rosetta)</span>
          <div className="form-row" style={{ marginTop: 12 }}>
            <Field label={`% de Areia`}>
              <input
                type="range"
                min={0}
                max={100}
                step={5}
                value={sandPct}
                onChange={(e) => setSandPct(e.target.value)}
                aria-label="% de Areia"
              />
            </Field>
            <Field label={`% de Argila`}>
              <input
                type="range"
                min={0}
                max={100}
                step={5}
                value={clayPct}
                onChange={(e) => setClayPct(e.target.value)}
                aria-label="% de Argila"
              />
            </Field>
          </div>
          {rosettaNote && <div className="soil-texture-badge" dangerouslySetInnerHTML={{ __html: rosettaNote.replace(/(\S+):/g, "<b>$1:</b>") }} />}
        </div>
      )}

      <div style={{ margin: "18px 0 10px 0" }}>
        <span className="step-section-title-inline">Propriedades Físico-Hídricas do Solo (van Genuchten - Mualem)</span>
      </div>
      <div className="form-row">
        <Field label="θr - Umidade residual [cm³/cm³]">
          <input value={thetaR} onChange={(e) => setThetaR(e.target.value)} inputMode="decimal" type="number" step="any" min={0} max={1} />
        </Field>
        <Field label="θs - Umidade de saturação [cm³/cm³]">
          <input value={thetaS} onChange={(e) => setThetaS(e.target.value)} inputMode="decimal" type="number" step="any" min={0} max={1} />
        </Field>
        <Field label="α - Parâmetro de escala (entrada de ar) [1/cm]">
          <input value={vgAlpha} onChange={(e) => setVgAlpha(e.target.value)} inputMode="decimal" type="number" step="any" min={0} />
        </Field>
      </div>
      <div className="form-row">
        <Field label="n - Índice de poros [-]">
          <input value={vgN} onChange={(e) => setVgN(e.target.value)} inputMode="decimal" type="number" step="any" min={0} />
        </Field>
        <Field label="Ks - Condutividade saturada [cm/dia]">
          <input value={ks} onChange={(e) => setKs(e.target.value)} inputMode="decimal" type="number" step="any" min={0} />
        </Field>
        <Field label="ρb - Densidade aparente [g/cm³]">
          <input value={bulk} onChange={(e) => setBulk(e.target.value)} inputMode="decimal" type="number" step="any" min={0} />
        </Field>
      </div>

      <div style={{ margin: "26px 0 10px 0" }}>
        <span className="step-section-title-inline">Domínio do Perfil de Solo Simulado</span>
      </div>
      <div className="form-row">
        <Field label="Profundidade do Perfil Simulado [cm]">
          <input
            value={depthCm}
            onChange={(e) => setDepthCm(e.target.value)}
            inputMode="decimal"
            type="number"
            min={1}
            max={300}
          />
        </Field>
      </div>

      <div className="step-section-title" style={{ marginTop: 28 }}>Cultura (Transpiração e Absorção Radicular)</div>
      <div className="choice-cards" role="radiogroup" aria-label="Modo de cultura">
        <label className={`choice-card${!comCultura ? " selected" : ""}`}>
          <input
            type="radio"
            name="crop-mode"
            value="sem"
            checked={!comCultura}
            onChange={() => setCropMode("sem")}
          />
          <span className="choice-icon"><SoilLayersIcon /></span>
          Sem cultura (perfil nu)
        </label>
        <label className={`choice-card${comCultura ? " selected" : ""}`}>
          <input
            type="radio"
            name="crop-mode"
            value="com"
            checked={comCultura}
            onChange={() => setCropMode("com")}
          />
          <span className="choice-icon"><SeedlingIcon /></span>
          Com cultura agrícola
        </label>
      </div>

      {comCultura && (
        <div style={{ marginTop: 20 }}>
          <div className="form-row">
            <Field label="Cultura agrícola">
              <select value={crop} onChange={(e) => setCrop(e.target.value)}>
                {crops.map((c) => <option key={c.key} value={c.key}>{c.name} (raiz {c.root_depth_cm} cm)</option>)}
              </select>
            </Field>
            <Field label="Profundidade radicular [cm]">
              <input
                value={rootDepthCm}
                onChange={(e) => setRootDepthCm(e.target.value)}
                inputMode="decimal"
                type="number"
                min={1}
              />
            </Field>
          </div>
        </div>
      )}
    </>
  );
}
