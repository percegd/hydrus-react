"use client";

import type { SimulateResponse } from "../lib/api";

const NUTRIENT_ACCENTS: Record<string, [string, string]> = {
  N: ["#fff7ed", "#c2410c"],
  K: ["#f5f3ff", "#6d28d9"],
  P: ["#f7fee7", "#4d7c0f"],
  S: ["#fefce8", "#a16207"],
  Ca: ["#ecfdf5", "#047857"],
  Mg: ["#fdf2f8", "#be185d"],
};

const ICON_RAIN = (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z" />
  </svg>
);

const ICON_DRAIN = (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="12" y1="4" x2="12" y2="20" />
    <polyline points="18 14 12 20 6 14" />
  </svg>
);

const ICON_STORE = (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 12h18" />
    <path d="M3 6h18" />
    <path d="M3 18h18" />
  </svg>
);

export default function MetricsCards({ result }: { result: SimulateResponse }) {
  const appliedMm = result.applied_mm ?? 0;
  const drainageMm = result.drainage_mm ?? 0;
  const evalDepth = result.eval_depth_cm ?? 0;
  const targetD = result.target_depth_cm ?? 0;
  const hasCrop = result.has_crop ?? false;
  const zMax = result.z_max_cm ?? 0;
  const evalLabel = hasCrop && targetD > 0 ? targetD : evalDepth;

  return (
    <div className="metrics-card-grid">
      <div className="metric-card">
        <div className="metric-icon">{ICON_RAIN}</div>
        <div className="metric-value">{appliedMm.toFixed(0)} mm</div>
        <div className="metric-label">Lâmina Aplicada</div>
      </div>
      <div className="metric-card">
        <div className="metric-icon">{ICON_DRAIN}</div>
        <div className="metric-value">{drainageMm.toFixed(1)} mm</div>
        <div className="metric-label">Drenagem no Fundo</div>
      </div>

      {result.solutes.map((s) => {
        const dose = s.dose_kg_ha ?? 0;
        const ret = s.retained_root_pct ?? 0;
        const below = s.below_profile_pct ?? 0;
        const bot = s.bottom_pct ?? 0;
        const upt = s.uptaken_pct ?? 0;
        const peak = s.peak_depth_cm;
        const kd = s.kd ?? 0;
        const kdEff = s.kd_eff ?? kd;
        const res0 = s.initial_residual_mg_dm3 ?? 0;
        const [bg, fg] = NUTRIENT_ACCENTS[s.symbol] ?? ["#f1f5f9", "#334155"];
        const showRootRow = hasCrop && targetD > 0 && targetD < evalDepth && ret > 0;
        const kdEffective = Math.abs(kdEff - kd) > 0.0005;
        const peakText =
          peak === null || peak === undefined || (typeof peak === "number" && Number.isNaN(peak))
            ? "indefinido"
            : `${Number(peak).toFixed(1)} cm`;

        return (
          <div className="metric-card metric-nutr" key={s.symbol}>
            <div className="metric-nutr-head">
              <span className="metric-nutr-sym" style={{ background: bg, color: fg }}>{s.symbol}</span>
              <span className="metric-nutr-name">{s.name}</span>
            </div>
            <div className="metric-value">{ret.toFixed(1)}%</div>
            <div className="metric-label">Retido na camada avaliada (0–{evalLabel.toFixed(0)} cm)</div>
            <div className="metric-sub">{((dose * ret) / 100).toFixed(1)} kg/ha de {dose.toFixed(0)} kg/ha aplicados</div>
            <div className="metric-nutr-rows">
              {showRootRow && (
                <div className="metric-nutr-row">
                  <span>Na camada avaliada (0–{targetD.toFixed(0)} cm)</span>
                  <b>{ret.toFixed(1)}% · {((dose * ret) / 100).toFixed(1)} kg/ha</b>
                </div>
              )}
              <div className="metric-nutr-row">
                <span>Abaixo da camada (no perfil)</span>
                <b>{below.toFixed(1)}% · {((dose * below) / 100).toFixed(1)} kg/ha</b>
              </div>
              <div className="metric-nutr-row">
                <span>Atravessou o fundo ({zMax.toFixed(0)} cm)</span>
                <b>{bot.toFixed(1)}% · {((dose * bot) / 100).toFixed(1)} kg/ha</b>
              </div>
              {upt > 0.05 && (
                <div className="metric-nutr-row">
                  <span>Absorvido (passivo, sem teto nutricional)</span>
                  <b>{upt.toFixed(1)}% · {((dose * upt) / 100).toFixed(1)} kg/ha</b>
                </div>
              )}
              <div className="metric-nutr-row">
                <span>Pico no perfil</span>
                <b>{peakText}</b>
              </div>
              <div className="metric-nutr-row">
                <span>{kdEffective ? "Kd (efetivo)" : "Kd"}</span>
                <b>{(kdEffective ? kdEff : kd).toFixed(3)} cm³/g</b>
              </div>
              {res0 > 0 && (
                <div className="metric-nutr-row">
                  <span>Residual inicial</span>
                  <b>{res0.toFixed(2)} mg/dm³</b>
                </div>
              )}
            </div>
          </div>
        );
      })}

      {result.solutes.length === 0 && (
        <>
          <div className="metric-card">
            <div className="metric-icon">{ICON_STORE}</div>
            <div className="metric-value">
              {(result.storage_mm >= 0 ? "+" : "") + result.storage_mm.toFixed(1)} mm
            </div>
            <div className="metric-label">
              {result.storage_mm >= 0 ? "Ganho de Água no Perfil" : "Perda de Água no Perfil"} (θf − θi)
            </div>
          </div>
          {result.runoff_mm > 0.05 && (
            <div className="metric-card">
              <div className="metric-icon">{ICON_RAIN}</div>
              <div className="metric-value">{result.runoff_mm.toFixed(1)} mm</div>
              <div className="metric-label">Escoamento Superficial</div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
