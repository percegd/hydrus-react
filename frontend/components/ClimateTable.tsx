"use client";

import type { ClimateRow } from "../lib/api";

type Props = {
  rows: ClimateRow[];
  setRows: (rows: ClimateRow[]) => void;
  appDay: string;
  setAppDay: (v: string) => void;
  hideAppDay?: boolean;
};

export const APP_DAY_LABEL = "Dia da aplicação do fertilizante [1 - 365]";
export const APP_DAY_DEFAULT = "30";

function toNum(raw: string): number | null {
  const t = raw.trim().replace(",", ".");
  if (t === "") return null;
  const v = Number(t);
  if (!Number.isFinite(v) || v < 0) return NaN as unknown as null;
  return v;
}

export default function ClimateTable({ rows, setRows, appDay, setAppDay, hideAppDay }: Props) {
  function setCell(i: number, field: "rain_mm" | "et0_mm", raw: string) {
    const v = toNum(raw);
    // Mantém o texto digitado válido; inválido (< 0 ou texto) zera o erro no envio.
    setRows(rows.map((r, j) => (j === i ? { ...r, [field]: v === null || Number.isNaN(v) ? NaN : v } : r)));
  }

  const totalRain = rows.reduce((a, r) => a + (Number.isFinite(r.rain_mm) ? r.rain_mm : 0), 0);

  return (
    <>
      {!hideAppDay && (
        <div className="form-row">
          <label className="field">
            <span className="field-label">{APP_DAY_LABEL}</span>
            <input value={appDay} onChange={(e) => setAppDay(e.target.value)} placeholder={APP_DAY_DEFAULT} inputMode="decimal" />
          </label>
          <span className="hint-text" style={{ alignSelf: "end" }}>
            Chuva total na tabela: {totalRain.toFixed(1)} mm ({rows.length} dias)
          </span>
        </div>
      )}
      {hideAppDay && (
        <p className="hint-text">
          Chuva total na tabela: {totalRain.toFixed(1)} mm ({rows.length} dias)
        </p>
      )}
      <div className="climate-table-wrap">
        <table className="climate-table">
          <thead>
            <tr>
              <th>Dia</th>
              <th>Chuva (mm)</th>
              <th>ET0 (mm/dia)</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={r.day}>
                <td className="day-cell">{r.day}</td>
                <td>
                  <input
                    aria-label={`Chuva dia ${r.day}`}
                    value={Number.isNaN(r.rain_mm) ? "" : String(r.rain_mm)}
                    onChange={(e) => setCell(i, "rain_mm", e.target.value)}
                    inputMode="decimal"
                  />
                </td>
                <td>
                  <input
                    aria-label={`ET0 dia ${r.day}`}
                    value={Number.isNaN(r.et0_mm) ? "" : String(r.et0_mm)}
                    onChange={(e) => setCell(i, "et0_mm", e.target.value)}
                    inputMode="decimal"
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="hint-text">
        Tabela editável (365 dias): edite células ou cole dados do Excel. A tabela é a fonte da série enviada para a simulação.
      </p>
    </>
  );
}
