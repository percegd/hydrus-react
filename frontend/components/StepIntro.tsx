"use client";

const FEATURES = [
  "Richards + Advecção-Dispersão",
  "Cultura e evapotranspiração",
  "Lâmina de chuva ou série diária (upload)",
  "Balanço de massa e perfis por camada",
];

function CheckIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round" width={15} height={15}>
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

export default function StepIntro() {
  return (
    <div className="intro-wrap">
      <div className="intro-icon">
        <svg viewBox="0 0 24 24" fill="none" stroke="#ffffff" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round">
          <path d="M14 9.536V7a4 4 0 0 1 4-4h1.5a.5.5 0 0 1 .5.5V5a4 4 0 0 1-4 4 4 4 0 0 0-4 4c0 2 1 3 1 5a5 5 0 0 1-1 3" />
          <path d="M4 9a5 5 0 0 1 8 4 5 5 0 0 1-8-4" />
          <path d="M5 21h14" />
        </svg>
      </div>
      <h1 className="intro-title">Simulação de Água e Nutrientes no Solo</h1>
      <p className="intro-lead">
        Plataforma que modela, com rigor físico, a dinâmica da água e o transporte de
        nutrientes (N, K, Ca, Mg, S, P) no perfil do solo — de forma simples e
        transparente, sem a complexidade da interface do HYDRUS-1D.
      </p>
      <ul className="intro-features">
        {FEATURES.map((f) => (
          <li key={f}>
            <CheckIcon />
            {f}
          </li>
        ))}
      </ul>
    </div>
  );
}
