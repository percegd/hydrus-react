"use client";

export type NutrientRow = { symbol: string; name: string; dose: string; kd: string; rel: string; relDays: string };

export const SPECIES = [
  { symbol: "N", name: "Nitrato", kd: 0 },
  { symbol: "K", name: "Potássio", kd: 0.45 },
  { symbol: "P", name: "Fósforo", kd: 25 },
  { symbol: "S", name: "Enxofre", kd: 0.15 },
  { symbol: "Ca", name: "Cálcio", kd: 1.2 },
  { symbol: "Mg", name: "Magnésio", kd: 0.8 },
];

export const DEFAULT_ROWS: NutrientRow[] = [
  { symbol: "K", name: "Potássio", dose: "30", kd: "0.45", rel: "immediate", relDays: "60" },
];

type Props = {
  rows: NutrientRow[];
  setRow: (i: number, patch: Partial<NutrientRow>) => void;
  addRow: () => void;
  removeRow: (i: number) => void;
  placement: string;
  setPlacement: (v: string) => void;
  appDay: string;
  setAppDay: (v: string) => void;
  c0: string;
  setC0: (v: string) => void;
  pulse: string;
  setPulse: (v: string) => void;
  error: string;
  fieldErrors: string[];
  onBack: () => void;
  onNext: () => void;
};

export default function StepNutrients(props: Props) {
  const { rows, setRow, addRow, removeRow, placement, setPlacement, appDay, setAppDay, c0, setC0, pulse, setPulse, error, fieldErrors, onBack, onNext } = props;
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
          <label className="field">Dose (kg/ha)
            <input value={r.dose} onChange={(e) => setRow(i, { dose: e.target.value })} />
          </label>
          <label className="field">Kd (cm³/g)
            <input value={r.kd} onChange={(e) => setRow(i, { kd: e.target.value })} />
          </label>
          <label className="field">Liberação
            <select value={r.rel} onChange={(e) => setRow(i, { rel: e.target.value })}>
              <option value="immediate">Imediata</option>
              <option value="controlled">Controlada</option>
            </select>
          </label>
          {r.rel === "controlled" && (
            <label className="field">Dias
              <input value={r.relDays} onChange={(e) => setRow(i, { relDays: e.target.value })} />
            </label>
          )}
          <button className="icon-btn" onClick={() => removeRow(i)} title="Remover">✕</button>
        </div>
      ))}
      <button className="btn" onClick={addRow}>+ soluto</button>

      <h3 className="section-title" style={{ marginTop: 20 }}>Aplicação</h3>
      <div className="form-row">
        <label className="field">Modo
          <select value={placement} onChange={(e) => setPlacement(e.target.value)}>
            <option value="surface">Superfície (0–2 cm)</option>
            <option value="furrow">Sulco (5–10 cm)</option>
            <option value="fertigation">Fertirrigação</option>
          </select>
        </label>
        <label className="field">Dia da aplicação
          <input value={appDay} onChange={(e) => setAppDay(e.target.value)} />
        </label>
        {placement === "fertigation" && (
          <>
            <label className="field">C₀ (mg/L)
              <input value={c0} onChange={(e) => setC0(e.target.value)} />
            </label>
            <label className="field">Pulso (dias, 0=contínuo)
              <input value={pulse} onChange={(e) => setPulse(e.target.value)} />
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
