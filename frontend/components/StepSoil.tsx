"use client";

import { useState } from "react";
import HelpIcon from "./HelpIcon";
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
  cropName: string;
  setCropName: (v: string) => void;
  cropKc: string;
  setCropKc: (v: string) => void;
  cropH1: string;
  setCropH1: (v: string) => void;
  cropH2: string;
  setCropH2: (v: string) => void;
  cropH3: string;
  setCropH3: (v: string) => void;
  cropH4: string;
  setCropH4: (v: string) => void;
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

function Field({ label, children, helpKey }: { label: string; children: React.ReactNode; helpKey?: string }) {
  return (
    <label className="field">
      <span className="field-label">
        <span className="field-label-row">
          {label}
          {helpKey && <HelpIcon helpKey={helpKey} />}
        </span>
      </span>
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
  cropName,
  setCropName,
  cropKc,
  setCropKc,
  cropH1,
  setCropH1,
  cropH2,
  setCropH2,
  cropH3,
  setCropH3,
  cropH4,
  setCropH4,
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
  const [cropModalOpen, setCropModalOpen] = useState(false);

  function pickCrop(key: string) {
    setCrop(key);
    const found = crops.find((c) => c.key === key);
    if (found) {
      setCropName(found.name);
      setRootDepthCm(String(found.root_depth_cm));
      setCropKc(String(found.kc));
      setCropH1(String(found.h1));
      setCropH2(String(found.h2));
      setCropH3(String(found.h3));
      setCropH4(String(found.h4));
    }
    setCropModalOpen(false);
  }
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
        <Field label="θr - Umidade residual [cm³/cm³]" helpKey="theta_r">
          <input value={thetaR} onChange={(e) => setThetaR(e.target.value)} inputMode="decimal" type="number" step="any" min={0} max={1} />
        </Field>
        <Field label="θs - Umidade de saturação [cm³/cm³]" helpKey="theta_s">
          <input value={thetaS} onChange={(e) => setThetaS(e.target.value)} inputMode="decimal" type="number" step="any" min={0} max={1} />
        </Field>
        <Field label="α - Parâmetro de escala (entrada de ar) [1/cm]" helpKey="alpha">
          <input value={vgAlpha} onChange={(e) => setVgAlpha(e.target.value)} inputMode="decimal" type="number" step="any" min={0} />
        </Field>
      </div>
      <div className="form-row">
        <Field label="n - Índice de poros [-]" helpKey="n">
          <input value={vgN} onChange={(e) => setVgN(e.target.value)} inputMode="decimal" type="number" step="any" min={0} />
        </Field>
        <Field label="Ks - Condutividade saturada [cm/dia]" helpKey="ks">
          <input value={ks} onChange={(e) => setKs(e.target.value)} inputMode="decimal" type="number" step="any" min={0} />
        </Field>
        <Field label="ρb - Densidade aparente [g/cm³]" helpKey="bulk_density">
          <input value={bulk} onChange={(e) => setBulk(e.target.value)} inputMode="decimal" type="number" step="any" min={0} />
        </Field>
      </div>

      <div style={{ margin: "26px 0 10px 0" }}>
        <span className="step-section-title-inline">Domínio do Perfil de Solo Simulado</span>
      </div>
      <div className="form-row">
        <Field label="Profundidade do Perfil Simulado [cm]" helpKey="domain_depth">
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
            <Field label="Cultura agrícola" helpKey="crop_name">
              <input
                value={cropName}
                onChange={(e) => setCropName(e.target.value)}
                placeholder="Ex: Milho safrinha, Soja RR, Cana soca..."
              />
            </Field>
            <div style={{ alignSelf: "end" }}>
              <button type="button" className="btn-modal-open" onClick={() => setCropModalOpen(true)}>
                Selecionar Cultura Agrícola
              </button>
            </div>
          </div>
          <div className="form-row">
            <Field label="Profundidade radicular [cm]" helpKey="root_depth">
              <input
                value={rootDepthCm}
                onChange={(e) => setRootDepthCm(e.target.value)}
                inputMode="decimal"
                type="number"
                min={1}
              />
            </Field>
            <Field label="Coeficiente de cultura (Kc)" helpKey="kc">
              <input
                value={cropKc}
                onChange={(e) => setCropKc(e.target.value)}
                inputMode="decimal"
                type="number"
                step="any"
                min={0}
              />
            </Field>
          </div>
          <div className="form-row">
            <Field label="Anaerobiose (encharcado) [cm c.a.]" helpKey="fed_h1">
              <input
                value={cropH1}
                onChange={(e) => setCropH1(e.target.value)}
                inputMode="decimal"
                type="number"
                step="any"
              />
            </Field>
            <Field label="Aeração ótima [cm c.a.]" helpKey="fed_h2">
              <input
                value={cropH2}
                onChange={(e) => setCropH2(e.target.value)}
                inputMode="decimal"
                type="number"
                step="any"
              />
            </Field>
          </div>
          <div className="form-row">
            <Field label="Início do estresse hídrico [cm c.a.]" helpKey="fed_h3">
              <input
                value={cropH3}
                onChange={(e) => setCropH3(e.target.value)}
                inputMode="decimal"
                type="number"
                step="any"
              />
            </Field>
            <Field label="Murcha permanente [cm c.a.]" helpKey="fed_h4">
              <input
                value={cropH4}
                onChange={(e) => setCropH4(e.target.value)}
                inputMode="decimal"
                type="number"
                step="any"
              />
            </Field>
          </div>
        </div>
      )}

      {cropModalOpen && (
        <div className="modal-overlay" role="dialog" aria-modal="true" aria-label="Selecionar Cultura Agrícola">
          <div className="modal-card fert-modal-card">
            <h3 className="fert-modal-title" style={{ marginBottom: 14 }}>Selecionar Cultura Agrícola</h3>
            <div className="choice-cards" role="radiogroup" aria-label="Culturas" style={{ flexDirection: "column", gap: 8 }}>
              {crops.map((c) => (
                <label key={c.key} className={`choice-card${crop === c.key ? " selected" : ""}`}>
                  <input
                    type="radio"
                    name="crop-picker"
                    value={c.key}
                    checked={crop === c.key}
                    onChange={() => pickCrop(c.key)}
                  />
                  <span>{c.name} (raiz {c.root_depth_cm} cm)</span>
                </label>
              ))}
            </div>
            <div className="modal-actions">
              <button type="button" className="btn-modal-cancel" onClick={() => setCropModalOpen(false)}>
                Fechar
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
