"use client";

import { useEffect, useState } from "react";
import { ApiError, getFertilizers, postFertilizerDose, type FertilizerInfo } from "../lib/api";
import HelpIcon from "./HelpIcon";

export type NutrientRow = {
  symbol: string;
  name: string;
  dose: string;
  kd: string;
  disp: string;
  res: string;
  custom?: boolean;
  active: boolean;
  kdEdited?: boolean;
  kdSource?: string;
};

/** Ordem fixa das linhas, igual à tabela do Gradio (Passo 2). */
export const NUTRIENT_ORDER = ["N", "K", "P", "S", "Ca", "Mg"];

export const FIXED_NAMES: Record<string, string> = {
  N: "Nitrato",
  K: "Potássio",
  P: "Fósforo",
  S: "Enxofre",
  Ca: "Cálcio",
  Mg: "Magnésio",
};

/** Kd inicial por nutriente (antes do Kd de literatura por textura carregar). */
const INITIAL_KD: Record<string, string> = {
  N: "0",
  K: "0.45",
  P: "25",
  S: "0.15",
  Ca: "1.2",
  Mg: "0.8",
};

export const SPECIES = [
  { symbol: "N", name: "Nitrato", kd: 0 },
  { symbol: "K", name: "Potássio", kd: 0.45 },
  { symbol: "P", name: "Fósforo", kd: 25 },
  { symbol: "S", name: "Enxofre", kd: 0.15 },
  { symbol: "Ca", name: "Cálcio", kd: 1.2 },
  { symbol: "Mg", name: "Magnésio", kd: 0.8 },
];

export const NUTRIENT_SYMBOLS = ["N", "K", "P", "S", "Ca", "Mg"];

/** Rótulos de exibição iguais aos do Gradio (o `name` do payload é preservado). */
export function nutrientLabel(symbol: string, fallback: string): string {
  switch (symbol) {
    case "N": return "N · Nitrato (NO₃⁻)";
    case "K": return "K · Potássio (K⁺)";
    case "P": return "P · Fósforo (fosfato)";
    case "S": return "S · Enxofre (sulfato)";
    case "Ca": return "Ca · Cálcio (Ca²⁺)";
    case "Mg": return "Mg · Magnésio (Mg²⁺)";
    default: return fallback || symbol;
  }
}

/** 6 linhas fixas (só K ativo, dose 30) + 1 linha "Outro soluto" — igual ao Gradio. */
export const DEFAULT_ROWS: NutrientRow[] = [
  ...NUTRIENT_ORDER.map((sym) => ({
    symbol: sym,
    name: FIXED_NAMES[sym] ?? sym,
    dose: sym === "K" ? "30" : "0",
    kd: INITIAL_KD[sym] ?? "0",
    disp: "20",
    res: "0",
    active: sym === "K",
    kdEdited: false,
    kdSource: "",
  })),
  { symbol: "", name: "", dose: "0", kd: "0.2", disp: "20", res: "0", custom: true, active: false, kdEdited: false, kdSource: "" },
];

export const CUSTOM_PLACEHOLDER = "Outro soluto (ex: Br⁻, Cl⁻, Atrazina)";

export function defaultDispForDepth(depthCm: string): string {
  const d = parseFloat(String(depthCm).replace(",", "."));
  if (!Number.isFinite(d) || d <= 0) return "20";
  const v = d / 10;
  return String(Math.round(v * 100) / 100);
}

export function blankCustomRow(disp: string): NutrientRow {
  return { symbol: "", name: "", dose: "0", kd: "0.2", disp, res: "0", custom: true, active: false, kdEdited: false, kdSource: "" };
}

type Props = {
  waterOnly: boolean;
  setWaterOnly: (v: boolean) => void;
  rows: NutrientRow[];
  setRow: (i: number, patch: Partial<NutrientRow>) => void;
  addRow: () => void;
  removeRow: (i: number) => void;
  kdInfo: Record<string, { kd: string; citation: string }>;
  onApplyFertilizer: (doses: Record<string, number>, fertKey?: string, grossDose?: number) => void;
  placement: string;
  setPlacement: (v: string) => void;
  appDay: string;
  setAppDay: (v: string) => void;
  zTop: string;
  setZTop: (v: string) => void;
  zBottom: string;
  setZBottom: (v: string) => void;
  pulse: string;
  setPulse: (v: string) => void;
  fertContinuous: boolean;
  setFertContinuous: (v: boolean) => void;
  releaseType: string;
  setReleaseType: (v: string) => void;
  releaseDays: string;
  setReleaseDays: (v: string) => void;
};

function FlaskIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 3h6" />
      <path d="M10 3v6.5L5.6 17.1A2 2 0 0 0 7.4 20h9.2a2 2 0 0 0 1.8-2.9L14 9.5V3" />
      <path d="M7.2 15h9.6" />
      <circle cx="10.2" cy="17.6" r="0.9" />
      <circle cx="13.6" cy="17.6" r="0.9" />
    </svg>
  );
}

function DropIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z" />
    </svg>
  );
}

function CubeIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
      <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
      <line x1="12" y1="22.08" x2="12" y2="12" />
    </svg>
  );
}

function Field({ label, children, fixed, helpKey }: { label: string; children: React.ReactNode; fixed?: boolean; helpKey?: string }) {
  return (
    <label className={`field${fixed ? " fixed" : ""}`}>
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

export default function StepNutrients(props: Props) {
  const {
    waterOnly, setWaterOnly,
    rows, setRow, addRow, removeRow,
    kdInfo, onApplyFertilizer,
    placement, setPlacement,
    appDay, setAppDay,
    zTop, setZTop, zBottom, setZBottom,
    pulse, setPulse,
    fertContinuous, setFertContinuous,
    releaseType, setReleaseType,
    releaseDays, setReleaseDays,
  } = props;

  const [catalog, setCatalog] = useState<FertilizerInfo[]>([]);
  const [fertKey, setFertKey] = useState("polialita");
  const [grossDose, setGrossDose] = useState("200");
  const [fertMsg, setFertMsg] = useState("");
  const [fertError, setFertError] = useState("");
  const [fertBusy, setFertBusy] = useState(false);
  const [fertOpen, setFertOpen] = useState(false);

  useEffect(() => {
    getFertilizers().then((c) => {
      setCatalog(c.commercial);
      if (c.commercial.length > 0) setFertKey(c.commercial[0].key);
    }).catch(() => {});
  }, []);

  async function applyFertilizer() {
    setFertMsg("");
    setFertError("");
    const gross = parseFloat(grossDose.replace(",", "."));
    if (!Number.isFinite(gross) || gross < 0) {
      setFertError("Dose bruta deve ser um número ≥ 0.");
      return;
    }
    setFertBusy(true);
    try {
      const res = await postFertilizerDose({ fert_key: fertKey, gross_dose: gross });
      onApplyFertilizer(res.elemental_doses, fertKey, gross);
      setFertMsg(res.message);
      setFertOpen(false);
    } catch (e) {
      setFertError(e instanceof ApiError ? e.message : String(e instanceof Error ? e.message : e));
    } finally {
      setFertBusy(false);
    }
  }

  function toggleRow(i: number, on: boolean) {
    const cur = rows[i];
    if (on) {
      if (cur.custom) {
        setRow(i, { active: true });
      } else {
        const v = parseFloat(String(cur.dose).replace(",", "."));
        setRow(i, { active: true, dose: Number.isFinite(v) && v > 0 ? cur.dose : "30" });
      }
    } else {
      setRow(i, { active: false });
    }
  }

  const customCount = rows.filter((r) => r.custom).length;

  const PLACEMENTS = [
    { value: "surface", label: "A lanço / Superfície (0 a 2 cm)" },
    { value: "furrow", label: "No Sulco de Plantio (5 a 10 cm)" },
    { value: "custom", label: "Profundidade Personalizada" },
    { value: "fertigation", label: "Fertirrigação" },
  ];

  const isControlled = releaseType === "controlled";

  return (
    <>
      <div className="choice-cards" role="radiogroup" aria-label="Modo de simulação">
        <label className={`choice-card${!waterOnly ? " selected" : ""}`}>
          <input type="radio" name="simulation-mode" value="nutrients" checked={!waterOnly} onChange={() => setWaterOnly(false)} />
          <span className="choice-icon"><FlaskIcon /></span>
          Água + nutrientes
        </label>
        <label className={`choice-card${waterOnly ? " selected" : ""}`}>
          <input type="radio" name="simulation-mode" value="water-only" checked={waterOnly} onChange={() => setWaterOnly(true)} />
          <span className="choice-icon"><DropIcon /></span>
          Somente água
        </label>
      </div>

      {waterOnly && (
        <div className="water-only-note">
          <b>Simulação somente de água.</b> Nenhum soluto será transportado — a tabela de
          nutrientes, a liberação do fertilizante e o posicionamento do adubo ficam desativados.
          <ul>
            <li><b>Perfil de umidade θ(z)</b> — umidade ao longo da profundidade (inicial vs final);</li>
            <li><b>θ(t) nos nós de observação</b> — avanço da frente de molhamento no tempo;</li>
            <li><b>Balanço hídrico</b> — chuva/irrigação, drenagem no fundo, escoamento superficial e Δ armazenamento.</li>
          </ul>
        </div>
      )}

      {!waterOnly && (
        <>
          <div className="section-header-row">
            <button type="button" className="btn-modal-open" onClick={() => { setFertMsg(""); setFertError(""); setFertOpen(true); }}>
              <span className="cube-icon"><CubeIcon /></span>
              Carregar Fertilizante Comercial
            </button>
          </div>
          {fertMsg && <p className="hint-text">{fertMsg}</p>}

          <div className="nutrient-table-header">
            <span className="col-nutr">Nutriente</span>
            <div className="col-dose"><span className="header-title">Dose elementar <HelpIcon helpKey="dose_tab" /></span><span className="header-unit">[kg/ha]</span></div>
            <div className="col-kd"><span className="header-title">Kd - Adsorção <HelpIcon helpKey="kd_tab" /></span><span className="header-unit">[cm³/g]</span></div>
            <div className="col-disp"><span className="header-title">Disp. (λ) <HelpIcon helpKey="disp_tab" /></span><span className="header-unit">[cm]</span></div>
            <div className="col-res"><span className="header-title">Teor Residual <HelpIcon helpKey="res_tab" /></span><span className="header-unit">[mg/dm³]</span></div>
          </div>
          <div className="estimate-note">
            <b>Como estes valores são estimados:</b> o <b>Kd</b> vem de tabelas de literatura
            para a textura do solo escolhido (Embrapa, van Raij, Sparks, SSSA); o <b>λ</b> usa o
            padrão <b>0,1 × profundidade do domínio</b>, regra prática da comunidade HYDRUS-1D.
            Para valores calibrados — ex.: ajuste por STANMOD/CXTFIT — digite diretamente na célula.
          </div>

          <div style={{ marginTop: 10 }}>
            {rows.map((r, i) => {
              const active = !!r.active;
              const info = r.custom ? undefined : kdInfo[r.symbol];
              const badge = r.custom
                ? "Soluto personalizado (traçador / poluente / íon diverso)"
                : (r.kdEdited ? "Valor editado manualmente" : `Literatura: ${r.kdSource || info?.citation || ""}`);
              return (
                <div key={i}>
                  <div className={`nutrient-row${active ? " active" : ""}`}>
                    {r.custom ? (
                      <div className="nutrient-col-name">
                        <input
                          type="checkbox"
                          className="switch"
                          checked={active}
                          onChange={(e) => toggleRow(i, e.target.checked)}
                          aria-label="Ativar outro soluto"
                        />
                        <input
                          type="text"
                          value={r.name}
                          disabled={!active}
                          onChange={(e) => setRow(i, { name: e.target.value, symbol: e.target.value })}
                          placeholder={CUSTOM_PLACEHOLDER}
                          aria-label="Nome do outro soluto"
                          title="Nome/símbolo do soluto (ex: Br⁻, Cl⁻, Atrazina)"
                        />
                      </div>
                    ) : (
                      <div className="nutrient-col-check">
                        <input
                          type="checkbox"
                          className="switch"
                          checked={active}
                          onChange={(e) => toggleRow(i, e.target.checked)}
                          aria-label={`Ativar ${nutrientLabel(r.symbol, r.name)}`}
                        />
                        <span className="nutr-name">{nutrientLabel(r.symbol, r.name)}</span>
                      </div>
                    )}
                    <div className={`nutrient-col-dose${active ? "" : " input-disabled-dim"}`}>
                      <input value={r.dose} disabled={!active} onChange={(e) => setRow(i, { dose: e.target.value })} inputMode="decimal" aria-label="Dose elementar [kg/ha]" />
                    </div>
                    <div className={`nutrient-col-kd${active ? "" : " input-disabled-dim"}`} title={badge}>
                      <input value={r.kd} disabled={!active} onChange={(e) => setRow(i, { kd: e.target.value, kdEdited: true })} inputMode="decimal" aria-label="Kd - Adsorção [cm³/g]" />
                    </div>
                    <div className={`nutrient-col-disp${active ? "" : " input-disabled-dim"}`}>
                      <input value={r.disp} disabled={!active} onChange={(e) => setRow(i, { disp: e.target.value })} inputMode="decimal" aria-label="Dispersividade λ [cm]" />
                    </div>
                    <div className={`nutrient-col-res${active ? "" : " input-disabled-dim"}`}>
                      <input value={r.res} disabled={!active} onChange={(e) => setRow(i, { res: e.target.value })} inputMode="decimal" aria-label="Teor residual [mg/dm³]" />
                    </div>
                    {r.custom && customCount > 1 && (
                      <button type="button" className="icon-btn" onClick={() => removeRow(i)} title="Remover soluto" aria-label="Remover soluto">✕</button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          <div style={{ marginTop: 8 }}>
            <button type="button" className="btn-add-solute" onClick={addRow}>+ Adicionar outro soluto</button>
          </div>

          <div className="step-section-title"><span className="help-section-title">Liberação do fertilizante <HelpIcon helpKey="release_type" /></span></div>
          <div className="seg-grid" role="radiogroup" aria-label="Liberação do fertilizante" style={{ marginTop: 10 }}>
            <label className={`seg-option${!isControlled ? " selected" : ""}`}>
              <input
                type="radio"
                name="release-type"
                value="immediate"
                checked={!isControlled}
                onChange={() => setReleaseType("immediate")}
              />
              Convencional (Solubilização Instantânea)
            </label>
            <label className={`seg-option${isControlled ? " selected" : ""}`}>
              <input
                type="radio"
                name="release-type"
                value="controlled"
                checked={isControlled}
                onChange={() => setReleaseType("controlled")}
              />
              Liberação Controlada / Lenta
            </label>
          </div>
          {isControlled && (
            <div className="form-row" style={{ marginTop: 8 }}>
              <Field label="Duração da liberação [dias]" helpKey="release_days">
                <input value={releaseDays} onChange={(e) => setReleaseDays(e.target.value)} inputMode="decimal" />
              </Field>
            </div>
          )}

          <div className="step-section-title"><span className="help-section-title">Posicionamento do adubo no solo <HelpIcon helpKey="placement_mode" /></span></div>
          <div className="seg-grid" role="radiogroup" aria-label="Posicionamento do adubo no solo" style={{ marginTop: 10 }}>
            {PLACEMENTS.map((p) => (
              <label key={p.value} className={`seg-option${placement === p.value ? " selected" : ""}`}>
                <input
                  type="radio"
                  name="placement-mode"
                  value={p.value}
                  checked={placement === p.value}
                  onChange={() => setPlacement(p.value)}
                />
                {p.label}
              </label>
            ))}
          </div>

          <div className="form-row" style={{ marginTop: 12 }}>
            <Field label="Dia da aplicação" helpKey="app_day">
              <input value={appDay} onChange={(e) => setAppDay(e.target.value)} inputMode="decimal" />
            </Field>
            {placement === "custom" && (
              <>
                <Field label="De (profundidade inicial) [cm]" helpKey="z_top">
                  <input value={zTop} onChange={(e) => setZTop(e.target.value)} inputMode="decimal" />
                </Field>
                <Field label="Até (profundidade final) [cm]" helpKey="z_bottom">
                  <input value={zBottom} onChange={(e) => setZBottom(e.target.value)} inputMode="decimal" />
                </Field>
              </>
            )}
            {placement === "fertigation" && (
              <>
                <div className="field fixed">
                  <span className="field-label">
                    <span className="field-label-row">
                      C₀ calculado por nutriente
                    </span>
                  </span>
                  <p className="hint-text" style={{ margin: "4px 0 0 0" }}>
                    C₀ calculada por nutriente = dose ÷ lâmina no período de injeção.
                  </p>
                </div>
                <Field label="Duração da Injeção [dias]" helpKey="fert_pulse">
                  <input value={pulse} onChange={(e) => setPulse(e.target.value)} inputMode="decimal" disabled={fertContinuous} />
                </Field>
                <div className="field fixed">
                  <span className="field-label">{"\u00A0"}</span>
                  <label className="switch-row">
                    <input type="checkbox" className="switch" checked={fertContinuous} onChange={(e) => setFertContinuous(e.target.checked)} />
                    Injeção contínua (toda a duração)
                  </label>
                </div>
              </>
            )}
          </div>
        </>
      )}

      {fertOpen && (
        <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="fert-title">
          <div className="modal-card fert-modal-card">
            <h3 className="fert-modal-title" id="fert-title">Carregar Fertilizante Comercial</h3>
            <p className="fert-modal-sub">
              Selecione o fertilizante e a dose bruta comercial. O sistema calculará e preencherá
              automaticamente as doses elementares de cada nutriente.
            </p>
            <div className="form-row">
              <Field label="Fertilizante Comercial">
                <select value={fertKey} onChange={(e) => setFertKey(e.target.value)}>
                  {catalog.map((f) => <option key={f.key} value={f.key}>{f.label}</option>)}
                </select>
              </Field>
            </div>
            <div className="form-row">
              <Field label="Dose Bruta de Produto Comercial [kg/ha]">
                <input value={grossDose} onChange={(e) => setGrossDose(e.target.value)} inputMode="decimal" />
              </Field>
            </div>
            {fertError && <p className="error-text">{fertError}</p>}
            <div className="modal-actions">
              <button type="button" className="btn-modal-cancel" onClick={() => setFertOpen(false)}>Cancelar</button>
              <button type="button" className="btn-modal-confirm" onClick={applyFertilizer} disabled={fertBusy}>
                {fertBusy ? "Aplicando..." : "Confirmar"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
