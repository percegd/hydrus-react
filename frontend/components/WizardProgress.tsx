"use client";

const STEPS = ["Apresentação", "Solo & Perfil", "Nutrientes", "Regime Hídrico", "Resultados"];

function CheckIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={3} strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

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
                <span className={`wizard-badge ${badge}`}>{i < current ? <CheckIcon /> : i}</span>
                <span className="wizard-label">{title}</span>
              </div>
            )}
            {i < STEPS.length - 1 && (
              <div className={`wizard-connector${i + 1 < current ? " connector-done" : ""}`} />
            )}
          </span>
        );
      })}
    </div>
  );
}
