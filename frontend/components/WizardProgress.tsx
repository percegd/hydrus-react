"use client";

const STEPS = ["Apresentação", "Solo e Perfil", "Nutrientes", "Regime Hídrico", "Resultados"];

export default function WizardProgress({ current }: { current: number }) {
  return (
    <div className="wizard-progress-bar">
      {STEPS.map((title, i) => {
        const state = i < current ? "step-done" : i === current ? "step-active" : "step-pending";
        const badge = i < current ? "badge-done" : i === current ? "badge-active" : "badge-pending";
        return (
          <span key={title} style={{ display: "contents" }}>
            {i === 0 ? (
              <div className={`wizard-step ${state}`}>
                <span className="wizard-label">{title}</span>
              </div>
            ) : (
              <div className={`wizard-step ${state}`}>
                <span className={`wizard-badge ${badge}`}>{i < current ? "✓" : i}</span>
                <span className="wizard-label">{title}</span>
              </div>
            )}
            {i < STEPS.length - 1 && <div className={`wizard-connector${i < current ? " connector-done" : ""}`} />}
          </span>
        );
      })}
    </div>
  );
}
