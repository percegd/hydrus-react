"use client";

import type { ClimateRow } from "../lib/api";

type Props = {
  rows: ClimateRow[];
  setRows: (rows: ClimateRow[]) => void;
  appDay: string;
  setAppDay: (v: string) => void;
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

export default function ClimateTable({ rows, setRows, appDay, setAppDay }: Props) {
  function setCell(i: number, field: "rain_mm" | "et0_mm", raw: string) {
    const v = toNum(raw);
    // Mantém o texto digitado válido; inválido (< 0 ou texto) zera o erro no envio.
    setRows(rows.map((r, j) => (j === i ? { ...r, [field]: v === null || Number.isNaN(v) ? NaN : v } : r)));
  }

  const totalRain = rows.reduce((a, r) => a + (Number.isFinite(r.rain_mm) ? r.rain_mm : 0), 0);

  return (
    <>
      <div className="form-row">
        <label className="field">
          {APP_DAY_LABEL}
          <input value={appDay} onChange={(e) => setAppDay(e.target.value)} placeholder={APP_DAY_DEFAULT} />
        </label>
        <span style={{ fontSize: 12, opacity: 0.8, alignSelf: "end" }}>
          Chuva total na tabela: {totalRain.toFixed(1)} mm ({rows.length} dias)
        </span>
      </div>
      <div style={{ marginTop: 8, maxHeight: 360, overflowY: "auto", border: "1px solid #e5e7eb", borderRadius: 8 }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead style={{ position: "sticky", top: 0, background: "#f8fafc" }}>
            <tr>
              <th style={{ padding: "6px 8px", textAlign: "right" }}>Dia</th>
              <th style={{ padding: "6px 8px", textAlign: "right" }}>Chuva (mm)</th>
              <th style={{ padding: "6px 8px", textAlign: "right" }}>ET0 (mm/dia)</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={r.day} style={{ borderTop: "1px solid #f1f5f9" }}>
                <td style={{ padding: "2px 8px", textAlign: "right", color: "#64748b" }}>{r.day}</td>
                <td style={{ padding: 2, textAlign: "right" }}>
                  <input
                    aria-label={`Chuva dia ${r.day}`}
                    value={Number.isNaN(r.rain_mm) ? "" : String(r.rain_mm)}
                    onChange={(e) => setCell(i, "rain_mm", e.target.value)}
                    style={{ width: 90, textAlign: "right" }}
                    inputMode="decimal"
                  />
                </td>
                <td style={{ padding: 2, textAlign: "right" }}>
                  <input
                    aria-label={`ET0 dia ${r.day}`}
                    value={Number.isNaN(r.et0_mm) ? "" : String(r.et0_mm)}
                    onChange={(e) => setCell(i, "et0_mm", e.target.value)}
                    style={{ width: 90, textAlign: "right" }}
                    inputMode="decimal"
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p style={{ fontSize: 12, opacity: 0.8 }}>
        Tabela editável (365 dias): edite células ou cole dados do Excel. A tabela é a fonte da série enviada para a simulação.
      </p>
    </>
  );
}
