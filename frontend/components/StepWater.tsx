"use client";

type Props = {
  days: string;
  setDays: (v: string) => void;
  rainMode: "uniform" | "series";
  setRainMode: (v: "uniform" | "series") => void;
  rainMm: string;
  setRainMm: (v: string) => void;
  moisture: string;
  setMoisture: (v: string) => void;
  et0: string;
  setEt0: (v: string) => void;
  series: string;
  setSeries: (v: string) => void;
  et0Series: string;
  setEt0Series: (v: string) => void;
  error: string;
  fieldErrors: string[];
  onBack: () => void;
  onRun: () => void;
};

export default function StepWater(props: Props) {
  const { days, setDays, rainMode, setRainMode, rainMm, setRainMm, moisture, setMoisture, et0, setEt0, series, setSeries, et0Series, setEt0Series, error, fieldErrors, onBack, onRun } = props;
  return (
    <>
      <div className="form-row">
        <label className="field">Dias
          <input value={days} onChange={(e) => setDays(e.target.value)} />
        </label>
        <label className="field">Chuva
          <select value={rainMode} onChange={(e) => setRainMode(e.target.value as "uniform" | "series")}>
            <option value="uniform">Lâmina uniforme</option>
            <option value="series">Série diária</option>
          </select>
        </label>
        {rainMode === "uniform" && (
          <label className="field">Total (mm)
            <input value={rainMm} onChange={(e) => setRainMm(e.target.value)} />
          </label>
        )}
        <label className="field">Umidade prévia (%)
          <input value={moisture} onChange={(e) => setMoisture(e.target.value)} />
        </label>
        <label className="field">ET0 (mm/dia)
          <input value={et0} onChange={(e) => setEt0(e.target.value)} />
        </label>
      </div>
      {rainMode === "series" && (
        <div className="form-row" style={{ marginTop: 12 }}>
          <label className="field" style={{ flex: "1 1 100%" }}>Série diária de chuva (mm, separados por espaço/vírgula/linha)
            <textarea rows={3} value={series} onChange={(e) => setSeries(e.target.value)} placeholder="0 0 12.5 0 3 ..." />
          </label>
        </div>
      )}
      <div className="form-row" style={{ marginTop: 12 }}>
        <label className="field" style={{ flex: "1 1 100%" }}>Série diária de ET0, opcional (mm/dia)
          <textarea rows={2} value={et0Series} onChange={(e) => setEt0Series(e.target.value)} placeholder="4 4.1 3.8 ..." />
        </label>
      </div>
      {fieldErrors.length > 0 && (
        <ul className="error-text">
          {fieldErrors.map((m, i) => <li key={i}>{m}</li>)}
        </ul>
      )}
      {error && <p className="error-text">{error}</p>}
      <div className="btn-row">
        <button className="btn" onClick={onBack}>Voltar</button>
        <button className="btn btn-primary" onClick={onRun}>Calcular Resultados</button>
      </div>
    </>
  );
}
