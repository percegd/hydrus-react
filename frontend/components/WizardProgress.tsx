"use client";

const STEPS = ["Solo & Perfil", "Nutrientes & Manejo", "Resultados"];

export default function WizardProgress({ current }: { current: number }) {
  return (
    <div className="wizard-progress-bar">
      {STEPS.map((title, i) => {
        const n = i + 1;
        const state = n < current ? "step-done" : n === current ? "step-active" : "step-pending";
        const badge = n < current ? "badge-done" : n === current ? "badge-active" : "badge-pending";
        return (
          <span key={title} style={{ display: "contents" }}>
            <div className={`wizard-step ${state}`}>
              <span className={`wizard-badge ${badge}`}>{n < current ? "✓" : n}</span>
              <span className="wizard-label">{title}</span>
            </div>
            {i < STEPS.length - 1 && <div className={`wizard-connector${n < current ? " connector-done" : ""}`} />}
          </span>
        );
      })}
    </div>
  );
}
