"use client";

import { useEffect, useRef, useState } from "react";
import HelpIcon from "./HelpIcon";
import { postCropPreview } from "../lib/api";
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
  dzCm: string;
  setDzCm: (v: string) => void;
  rootDepthCm: string;
  setRootDepthCm: (v: string) => void;
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
  vgL: string;
  setVgL: (v: string) => void;
  soilEdited: boolean;
  onRestoreSoil: () => void;
  soilIssues: string[];
  cropStartMode: string;
  setCropStartMode: (v: string) => void;
  cropAgeDap: string;
  setCropAgeDap: (v: string) => void;
  plantingDay: string;
  setPlantingDay: (v: string) => void;
  afterHarvest: string;
  setAfterHarvest: (v: string) => void;
  rootGrowth: string;
  setRootGrowth: (v: string) => void;
  measuredRoot: string;
  setMeasuredRoot: (v: string) => void;
  stageLengths: string[];
  setStageLengths: (v: string[]) => void;
  kcbIni: string;
  setKcbIni: (v: string) => void;
  kcbMid: string;
  setKcbMid: (v: string) => void;
  kcbEnd: string;
  setKcbEnd: (v: string) => void;
  uptakeCap: boolean;
  setUptakeCap: (v: boolean) => void;
  useDualKc: boolean;
  setUseDualKc: (v: boolean) => void;
  growingRoot: boolean;
  setGrowingRoot: (v: boolean) => void;
  bareAfterHarvest: boolean;
  setBareAfterHarvest: (v: boolean) => void;
  rainIsSeries: boolean;
  previewBody: Record<string, unknown>;
  onPreview?: (r: { active_day1?: boolean; kcb_day1?: number | null; ke_day1?: number | null; et_varies?: boolean }) => void;
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
  dzCm,
  setDzCm,
  rootDepthCm,
  setRootDepthCm,
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
  vgL,
  setVgL,
  soilEdited,
  onRestoreSoil,
  soilIssues,
  cropStartMode,
  setCropStartMode,
  cropAgeDap,
  setCropAgeDap,
  plantingDay,
  setPlantingDay,
  afterHarvest,
  setAfterHarvest,
  rootGrowth,
  setRootGrowth,
  measuredRoot,
  setMeasuredRoot,
  stageLengths,
  setStageLengths,
  kcbIni,
  setKcbIni,
  kcbMid,
  setKcbMid,
  kcbEnd,
  setKcbEnd,
  uptakeCap,
  setUptakeCap,
  useDualKc,
  setUseDualKc,
  growingRoot,
  setGrowingRoot,
  bareAfterHarvest,
  setBareAfterHarvest,
  rainIsSeries,
  previewBody,
  onPreview,
}: Props) {
  const comCultura = cropMode === "com";
  const canAdultPerennial = crops.some((c) => c.key === crop && c.adult_perennial === true);
  const [cropModalOpen, setCropModalOpen] = useState(false);
  useEffect(() => {
    if (!cropModalOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setCropModalOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [cropModalOpen]);
  const [preview, setPreview] = useState<string>("");
  const previewTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (!comCultura) { setPreview(""); return; }
    if (previewTimer.current) clearTimeout(previewTimer.current);
    previewTimer.current = setTimeout(() => {
      postCropPreview(previewBody).then((r) => {
        const w = r.harvest_day_cal != null ? ` · colheita no dia ${Math.round(Number(r.harvest_day_cal))}` : "";
        setPreview(`Dia 1: estádio ${r.stage_day1} · Kcb ${r.kcb_day1 != null ? Number(r.kcb_day1).toFixed(2) : "—"} · raiz ${r.root_day1_cm != null ? Number(r.root_day1_cm).toFixed(0) : "—"} cm${w}`);
        onPreview?.(r);
      }).catch(() => setPreview(""));
    }, 300);
    return () => { if (previewTimer.current) clearTimeout(previewTimer.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [comCultura, JSON.stringify(previewBody)]);


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
          <select value={soil} onChange={(e) => setSoil(e.target.value)}>
            {soils.map((s) => (
              <option key={s.key} value={s.key}>
                {s.name}{soilEdited && s.key === soil ? " (personalizado)" : ""}
              </option>
            ))}
          </select>
          {soilEdited && (
            <button type="button" className="btn-restore-soil" onClick={onRestoreSoil}>
              Restaurar valores do solo
            </button>
          )}
        </Field>
      </div>

      <div style={{ margin: "18px 0 10px 0" }}>
        <span className="step-section-title-inline">Propriedades Físico-Hídricas do Solo (van Genuchten - Mualem)</span>
      </div>
      <div className="form-row">
        <Field label="θr - Umidade residual [cm³/cm³]" helpKey="theta_r">
          <input value={thetaR} onChange={(e) => setThetaR(e.target.value)} inputMode="decimal" type="number" step="any" />
        </Field>
        <Field label="θs - Umidade de saturação [cm³/cm³]" helpKey="theta_s">
          <input value={thetaS} onChange={(e) => setThetaS(e.target.value)} inputMode="decimal" type="number" step="any" />
        </Field>
        <Field label="α - Parâmetro de escala (entrada de ar) [1/cm]" helpKey="alpha">
          <input value={vgAlpha} onChange={(e) => setVgAlpha(e.target.value)} inputMode="decimal" type="number" step="any" />
        </Field>
      </div>
      <div className="form-row">
        <Field label="n - Índice de poros [-]" helpKey="n">
          <input value={vgN} onChange={(e) => setVgN(e.target.value)} inputMode="decimal" type="number" step="any" />
        </Field>
        <Field label="Ks - Condutividade saturada [cm/dia]" helpKey="ks">
          <input value={ks} onChange={(e) => setKs(e.target.value)} inputMode="decimal" type="number" step="any" />
        </Field>
        <Field label="ρb - Densidade aparente [g/cm³]" helpKey="bulk_density">
          <input value={bulk} onChange={(e) => setBulk(e.target.value)} inputMode="decimal" type="number" step="any" />
        </Field>
      </div>
      <div className="form-row">
        <Field label="l - Tortuosidade [-]" helpKey="vg_l">
          <input value={vgL} onChange={(e) => setVgL(e.target.value)} inputMode="decimal" type="number" step="any" />
        </Field>
      </div>
      {soilIssues.length > 0 && (
        <ul className="error-text soil-issue-list">
          {soilIssues.map((msg) => <li key={msg}>{msg}</li>)}
        </ul>
      )}

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

      <div style={{ margin: "18px 0 10px 0" }}>
        <span className="step-section-title-inline">Malha numérica</span>
      </div>
      <div className="form-row">
        <Field label="Espaçamento da malha, Δz (cm)" helpKey="dz_cm">
          <input value={dzCm} onChange={(e) => setDzCm(e.target.value)} inputMode="decimal" type="number" min={0.05} step="any" />
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

          <div style={{ marginTop: 18 }}>
            <span className="step-section-title-inline">Situação da cultura no início da simulação</span>
            <div className="choice-cards" role="radiogroup" aria-label="Situação inicial">
              {(["planting", "established", "perennial"] as const).filter((m) => m !== "perennial" || canAdultPerennial).map((m) => {
                const label = m === "planting" ? "Plantio durante a simulação" : m === "established" ? "Cultura já estabelecida" : "Perene adulta";
                return (
                  <label key={m} className={`choice-card${cropStartMode === m ? " selected" : ""}`}>
                    <input type="radio" name="crop-start-mode" value={m} checked={cropStartMode === m} onChange={() => setCropStartMode(m)} />
                    {label}
                  </label>
                );
              })}
            </div>
            {!canAdultPerennial && <p className="field-hint" style={{ margin: "8px 0 0" }}>Cultura anual: perene adulta não se aplica.</p>}
            {cropStartMode === "planting" && (
              <>
                <div className="form-row" style={{ marginTop: 10 }}>
                  <Field label="Dia do plantio" helpKey="crop_start_mode">
                    <input value={plantingDay} onChange={(e) => setPlantingDay(e.target.value)} inputMode="numeric" type="number" min={1} placeholder={rainIsSeries ? "dia da série (vazio = dia da aplicação)" : "dia do ensaio (vazio = 1)"} />
                  </Field>
                </div>
                <p className="field-hint">Solo nu antes do plantio.</p>
              </>
            )}
            {cropStartMode === "established" && (
              <div className="form-row" style={{ marginTop: 10 }}>
                <Field label="Idade no início [dias após plantio/brotação]" helpKey="crop_age_dap">
                  <input value={cropAgeDap} onChange={(e) => setCropAgeDap(e.target.value)} inputMode="decimal" type="number" min={0} placeholder="ex.: 50" />
                </Field>
              </div>
            )}
            {cropStartMode === "perennial" && (
              <p className="field-hint">Perene adulta: Kcb constante e raiz fixa (HYDRUS-1D lRoot=.false.).</p>
            )}
            <div className="form-row" style={{ marginTop: 10 }}>
              <Field label="Após a colheita" helpKey="after_harvest">
                <select value={afterHarvest} onChange={(e) => setAfterHarvest(e.target.value)}>
                  <option value="bare">Solo nu</option>
                  <option value="repeat">Repetir o ciclo</option>
                </select>
              </Field>
            </div>
            {preview && <p className="field-hint" aria-live="polite">{preview}</p>}
            <details style={{ marginTop: 10 }}>
              <summary>Avançado</summary>
              <div className="form-row" style={{ marginTop: 8 }}>
                <Field label="Profundidade atual medida da raiz [cm]" helpKey="measured_root">
                  <input value={measuredRoot} onChange={(e) => setMeasuredRoot(e.target.value)} inputMode="decimal" type="number" min={0} disabled={cropStartMode !== "established"} placeholder={cropStartMode !== "established" ? "só estabelecida" : "ex.: 30"} />
                </Field>
                <Field label="Crescimento da raiz" helpKey="root_growth_model">
                  <select value={rootGrowth} onChange={(e) => setRootGrowth(e.target.value)}>
                    <option value="linear">Linear (FAO-56)</option>
                    <option value="logistic">Logístico Verhulst-Pearl (HYDRUS-1D)</option>
                  </select>
                </Field>
              </div>
              <div className="form-row">
                {["Lini", "Ldev", "Lmid", "Lfim"].map((lbl, i) => (
                  <Field key={lbl} label={`${lbl} [dias]`} helpKey="stage_lengths">
                    <input value={stageLengths[i] || ""} onChange={(e) => { const v = [...stageLengths]; v[i] = e.target.value; setStageLengths(v); }} inputMode="decimal" type="number" min={0} placeholder="banco" />
                  </Field>
                ))}
              </div>
              <div className="form-row">
                <Field label="Kcb ini" helpKey="kcb_values">
                  <input value={kcbIni} onChange={(e) => setKcbIni(e.target.value)} inputMode="decimal" type="number" step="any" placeholder="banco" />
                </Field>
                <Field label="Kcb méd" helpKey="kcb_values">
                  <input value={kcbMid} onChange={(e) => setKcbMid(e.target.value)} inputMode="decimal" type="number" step="any" placeholder="banco" />
                </Field>
                <Field label="Kcb fim" helpKey="kcb_values">
                  <input value={kcbEnd} onChange={(e) => setKcbEnd(e.target.value)} inputMode="decimal" type="number" step="any" placeholder="banco" />
                </Field>
              </div>
              <p className="ext-warn">O HYDRUS-1D original não possui essa configuração; ativá-la altera os resultados.</p>
              <label className="custom-toggle-chk">
                <input type="checkbox" className="switch" checked={useDualKc} onChange={(e) => setUseDualKc(e.target.checked)} />
                Kc dual FAO-56 (separa evaporação e transpiração)
              </label>
              <label className="custom-toggle-chk">
                <input type="checkbox" className="switch" checked={growingRoot} onChange={(e) => setGrowingRoot(e.target.checked)} />
                Raiz crescente ao longo do ciclo
              </label>
              <label className="custom-toggle-chk">
                <input type="checkbox" className="switch" checked={bareAfterHarvest} onChange={(e) => setBareAfterHarvest(e.target.checked)} />
                Solo nu após a colheita
              </label>
              <label className="custom-toggle-chk">
                <input type="checkbox" className="switch" checked={uptakeCap} onChange={(e) => setUptakeCap(e.target.checked)} />
                Limitar absorção à demanda da cultura
              </label>
            </details>
          </div>
        </div>
      )}

      {cropModalOpen && (
        <div className="modal-overlay" role="dialog" aria-modal="true" aria-label="Selecionar Cultura Agrícola">
          <div className="modal-card fert-modal-card">
            <div className="modal-sticky-head">
              <h3 className="fert-modal-title" style={{ margin: 0 }}>Selecionar Cultura Agrícola</h3>
              <button type="button" className="modal-close-x" aria-label="Fechar" title="Fechar" onClick={() => setCropModalOpen(false)}>
                ×
              </button>
            </div>
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
            <div className="modal-actions modal-sticky-foot">
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
