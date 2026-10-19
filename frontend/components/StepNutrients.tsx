"use client";

import { useEffect, useState } from "react";
import { ApiError, getFertilizers, postFertilizerDose, type BlendPresetInfo, type FertilizerInfo } from "../lib/api";

export type NutrientRow = {
  symbol: string;
  name: string;
  dose: string;
  kd: string;
  disp: string;
  res: string;
  rel: string;
  relDays: string;
  kdEdited?: boolean;
  kdSource?: string;
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

export const DEFAULT_ROWS: NutrientRow[] = [
  { symbol: "K", name: "Potássio", dose: "30", kd: "0.45", disp: "20", res: "0", rel: "immediate", relDays: "60", kdEdited: false, kdSource: "" },
];

export function defaultDispForDepth(depthCm: string): string {
  const d = parseFloat(String(depthCm).replace(",", "."));
  if (!Number.isFinite(d) || d <= 0) return "20";
  const v = d / 10;
  return String(Math.round(v * 100) / 100);
}

type Props = {
  waterOnly: boolean;
  setWaterOnly: (v: boolean) => void;
  rows: NutrientRow[];
  setRow: (i: number, patch: Partial<NutrientRow>) => void;
  addRow: () => void;
  removeRow: (i: number) => void;
  kdInfo: Record<string, { kd: string; citation: string }>;
  onApplyFertilizer: (doses: Record<string, number>) => void;
  placement: string;
  setPlacement: (v: string) => void;
  appDay: string;
  setAppDay: (v: string) => void;
  zTop: string;
  setZTop: (v: string) => void;
  zBottom: string;
  setZBottom: (v: string) => void;
  c0: string;
  setC0: (v: string) => void;
  pulse: string;
  setPulse: (v: string) => void;
  fertContinuous: boolean;
  setFertContinuous: (v: boolean) => void;
  error: string;
  fieldErrors: string[];
  onBack: () => void;
  onNext: () => void;
};

export default function StepNutrients(props: Props) {
  const {
    waterOnly, setWaterOnly,
    rows, setRow, addRow, removeRow,
    kdInfo, onApplyFertilizer,
    placement, setPlacement,
    appDay, setAppDay,
    zTop, setZTop, zBottom, setZBottom,
    c0, setC0, pulse, setPulse,
    fertContinuous, setFertContinuous,
    error, fieldErrors, onBack, onNext,
  } = props;

  const [catalog, setCatalog] = useState<FertilizerInfo[]>([]);
  const [blends, setBlends] = useState<BlendPresetInfo[]>([]);
  const [fertKey, setFertKey] = useState("kcl");
  const [grossDose, setGrossDose] = useState("200");
  const [isCustomFert, setIsCustomFert] = useState(false);
  const [customPcts, setCustomPcts] = useState<Record<string, string>>({ N: "0", K: "0", P: "0", S: "0", Ca: "0", Mg: "0" });
  const [blendKey, setBlendKey] = useState("");
  const [fertMsg, setFertMsg] = useState("");
  const [fertError, setFertError] = useState("");
  const [fertBusy, setFertBusy] = useState(false);

  useEffect(() => {
    getFertilizers().then((c) => {
      setCatalog(c.commercial);
      setBlends(c.blend_presets);
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
      const body: { fert_key?: string; gross_dose: number; custom_pcts?: Record<string, number>; blend_preset?: string } = {
        fert_key: isCustomFert ? "custom" : fertKey,
        gross_dose: gross,
      };
      if (blendKey) {
        body.blend_preset = blendKey;
      } else if (isCustomFert) {
        const pcts: Record<string, number> = {};
        for (const s of NUTRIENT_SYMBOLS) {
          const v = parseFloat((customPcts[s] ?? "0").replace(",", "."));
          pcts[s] = Number.isFinite(v) ? v : 0;
        }
        body.custom_pcts = pcts;
      }
      const res = await postFertilizerDose(body);
      onApplyFertilizer(res.elemental_doses);
      setFertMsg(res.message);
    } catch (e) {
      setFertError(e instanceof ApiError ? e.message : String(e instanceof Error ? e.message : e));
    } finally {
      setFertBusy(false);
    }
  }

  function applyBlend(key: string) {
    setBlendKey(key);
    const b = blends.find((x) => x.key === key);
    if (b) {
      setCustomPcts(Object.fromEntries(NUTRIENT_SYMBOLS.map((s) => [s, String(b.nutrient_pcts[s] ?? 0)])));
    }
  }

  return (
    <>
      <div role="radiogroup" aria-label="Modo de simulação">
        <label className="field" style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
          <input type="radio" name="simulation-mode" value="nutrients" checked={!waterOnly} onChange={() => setWaterOnly(false)} />
          Água + nutrientes
        </label>
        <label className="field" style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
          <input type="radio" name="simulation-mode" value="water-only" checked={waterOnly} onChange={() => setWaterOnly(true)} />
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
          <h3 className="section-title" style={{ marginTop: 8 }}>Carregar Fertilizante Comercial</h3>
          <div className="form-row">
            <label className="field">Fertilizante Comercial
              <select value={fertKey} onChange={(e) => setFertKey(e.target.value)} disabled={isCustomFert || !!blendKey}>
                {catalog.map((f) => <option key={f.key} value={f.key}>{f.label}</option>)}
              </select>
            </label>
            <label className="field">Dose Bruta de Produto Comercial [kg/ha]
              <input value={grossDose} onChange={(e) => setGrossDose(e.target.value)} inputMode="decimal" />
            </label>
          </div>
          <div className="form-row" style={{ marginTop: 8 }}>
            <label className="field" style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
              <input type="checkbox" checked={isCustomFert} onChange={(e) => { setIsCustomFert(e.target.checked); setBlendKey(""); }} />
              Fertilizante Personalizado (teores próprios)
            </label>
            <label className="field">Mistura pronta (blend)
              <select value={blendKey} onChange={(e) => applyBlend(e.target.value)}>
                <option value="">—</option>
                {blends.map((b) => <option key={b.key} value={b.key}>{b.label}</option>)}
              </select>
            </label>
          </div>
          {(isCustomFert || blendKey) && (
            <div className="form-row" style={{ marginTop: 8 }}>
              {NUTRIENT_SYMBOLS.map((s) => (
                <label className="field" key={s}>Teor {s} [%]
                  <input
                    value={customPcts[s] ?? "0"}
                    onChange={(e) => { setCustomPcts((p) => ({ ...p, [s]: e.target.value })); setBlendKey(""); }}
                    inputMode="decimal"
                  />
                </label>
              ))}
            </div>
          )}
          <div className="btn-row" style={{ marginTop: 8 }}>
            <button className="btn" onClick={applyFertilizer} disabled={fertBusy}>
              {fertBusy ? "Aplicando..." : "Aplicar fertilizante"}
            </button>
          </div>
          {fertMsg && <p className="hint-text">{fertMsg}</p>}
          {fertError && <p className="error-text">{fertError}</p>}

          <h3 className="section-title" style={{ marginTop: 20 }}>Solutos e doses elementares</h3>
        </>
      )}
      {!waterOnly && rows.map((r, i) => {
        const info = kdInfo[r.symbol];
        const edited = !!r.kdEdited;
        const badge = edited ? "Editado" : `Literatura: ${r.kdSource || info?.citation || ""}`;
        return (
        <div className="nutrient-row" key={i}>
          <label className="field">Soluto
            <select value={r.symbol} onChange={(e) => {
              const sp = SPECIES.find((s) => s.symbol === e.target.value)!;
              const lit = kdInfo[sp.symbol];
              setRow(i, { symbol: sp.symbol, name: sp.name, kd: lit?.kd ?? String(sp.kd), kdEdited: false, kdSource: lit?.citation ?? "" });
            }}>
              {SPECIES.map((s) => <option key={s.symbol} value={s.symbol}>{s.symbol} · {s.name}</option>)}
            </select>
          </label>
          <label className="field">Dose elementar [kg/ha]
            <input value={r.dose} onChange={(e) => setRow(i, { dose: e.target.value })} />
          </label>
          <label className="field">Kd - Adsorção [cm³/g]
            <input value={r.kd} onChange={(e) => setRow(i, { kd: e.target.value, kdEdited: true })} />
            <span className="hint-text" title={info?.citation}>{badge}</span>
          </label>
          <label className="field">Dispersividade λ [cm]
            <input value={r.disp} onChange={(e) => setRow(i, { disp: e.target.value })} />
          </label>
          <label className="field">Resíduo inicial [mg/dm³]
            <input value={r.res} onChange={(e) => setRow(i, { res: e.target.value })} />
          </label>
          <label className="field">Liberação
            <select value={r.rel} onChange={(e) => setRow(i, { rel: e.target.value })}>
              <option value="immediate">Convencional (Solubilização Instantânea)</option>
              <option value="controlled">Liberação Controlada / Lenta</option>
            </select>
          </label>
          {r.rel === "controlled" && (
            <label className="field">Duração Nominal da Liberação [dias]
              <input value={r.relDays} onChange={(e) => setRow(i, { relDays: e.target.value })} />
            </label>
          )}
          <button className="icon-btn" onClick={() => removeRow(i)} title="Remover">✕</button>
        </div>
        );
      })}
      {!waterOnly && (
        <>
          <button className="btn" onClick={addRow}>+ soluto</button>

          <h3 className="section-title" style={{ marginTop: 20 }}>Posicionamento do adubo no solo</h3>
          <div role="radiogroup" aria-label="Posicionamento do adubo no solo">
            <label className="field" style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
              <input type="radio" name="placement-mode" value="surface" checked={placement === "surface"} onChange={() => setPlacement("surface")} />
              A lanço / Superfície (0 a 2 cm)
            </label>
            <label className="field" style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
              <input type="radio" name="placement-mode" value="furrow" checked={placement === "furrow"} onChange={() => setPlacement("furrow")} />
              No Sulco de Plantio (5 a 10 cm)
            </label>
            <label className="field" style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
              <input type="radio" name="placement-mode" value="custom" checked={placement === "custom"} onChange={() => setPlacement("custom")} />
              Profundidade personalizada
            </label>
            <label className="field" style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
              <input type="radio" name="placement-mode" value="fertigation" checked={placement === "fertigation"} onChange={() => setPlacement("fertigation")} />
              Fertirrigação
            </label>
          </div>

          <div className="form-row" style={{ marginTop: 12 }}>
            <label className="field">Dia da aplicação
              <input value={appDay} onChange={(e) => setAppDay(e.target.value)} />
            </label>
            {placement === "custom" && (
              <>
                <label className="field">De (profundidade inicial) [cm]
                  <input value={zTop} onChange={(e) => setZTop(e.target.value)} />
                </label>
                <label className="field">Até (profundidade final) [cm]
                  <input value={zBottom} onChange={(e) => setZBottom(e.target.value)} />
                </label>
              </>
            )}
            {placement === "fertigation" && (
              <>
                <label className="field">Concentração da Solução Injetada C₀ [mg/L]
                  <input value={c0} onChange={(e) => setC0(e.target.value)} />
                </label>
                <label className="field">Duração da Injeção [dias]
                  <input value={pulse} onChange={(e) => setPulse(e.target.value)} disabled={fertContinuous} />
                </label>
                <label className="field" style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
                  <input type="checkbox" checked={fertContinuous} onChange={(e) => setFertContinuous(e.target.checked)} />
                  Injeção contínua (toda a duração)
                </label>
              </>
            )}
          </div>
        </>
      )}
      {fieldErrors.length > 0 && (
        <ul className="error-text">
          {fieldErrors.map((m, i) => <li key={i}>{m}</li>)}
        </ul>
      )}
      {error && <p className="error-text">{error}</p>}
      <div className="btn-row">
        <button className="btn" onClick={onBack}>Voltar</button>
        <button className="btn btn-primary" onClick={onNext}>Avançar</button>
      </div>
    </>
  );
}
