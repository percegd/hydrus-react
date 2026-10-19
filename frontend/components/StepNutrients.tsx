"use client";

export type NutrientRow = {
  symbol: string;
  name: string;
  dose: string;
  kd: string;
  disp: string;
  res: string;
  rel: string;
  relDays: string;
};

export const SPECIES = [
  { symbol: "N", name: "Nitrato", kd: 0 },
  { symbol: "K", name: "Potássio", kd: 0.45 },
  { symbol: "P", name: "Fósforo", kd: 25 },
  { symbol: "S", name: "Enxofre", kd: 0.15 },
  { symbol: "Ca", name: "Cálcio", kd: 1.2 },
  { symbol: "Mg", name: "Magnésio", kd: 0.8 },
];

export const DEFAULT_ROWS: NutrientRow[] = [
  { symbol: "K", name: "Potássio", dose: "30", kd: "0.45", disp: "20", res: "0", rel: "immediate", relDays: "60" },
];

export function defaultDispForDepth(depthCm: string): string {
  const d = parseFloat(String(depthCm).replace(",", "."));
  if (!Number.isFinite(d) || d <= 0) return "20";
  const v = d / 10;
  return String(Math.round(v * 100) / 100);
}

type Props = {
  rows: NutrientRow[];
  setRow: (i: number, patch: Partial<NutrientRow>) => void;
  addRow: () => void;
  removeRow: (i: number) => void;
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
    rows, setRow, addRow, removeRow,
    placement, setPlacement,
    appDay, setAppDay,
    zTop, setZTop, zBottom, setZBottom,
    c0, setC0, pulse, setPulse,
    fertContinuous, setFertContinuous,
    error, fieldErrors, onBack, onNext,
  } = props;
  return (
    <>
      {rows.map((r, i) => (
        <div className="nutrient-row" key={i}>
          <label className="field">Soluto
            <select value={r.symbol} onChange={(e) => {
              const sp = SPECIES.find((s) => s.symbol === e.target.value)!;
              setRow(i, { symbol: sp.symbol, name: sp.name, kd: String(sp.kd) });
            }}>
              {SPECIES.map((s) => <option key={s.symbol} value={s.symbol}>{s.symbol} · {s.name}</option>)}
            </select>
          </label>
          <label className="field">Dose elementar [kg/ha]
            <input value={r.dose} onChange={(e) => setRow(i, { dose: e.target.value })} />
          </label>
          <label className="field">Kd - Adsorção [cm³/g]
            <input value={r.kd} onChange={(e) => setRow(i, { kd: e.target.value })} />
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
      ))}
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
