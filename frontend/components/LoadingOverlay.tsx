"use client";

export default function LoadingOverlay() {
  return (
    <div id="fullscreen-loading" role="alertdialog" aria-live="assertive" aria-busy="true">
      <div className="loader-spinner" aria-hidden="true" />
      <div className="loader-message">
        Calculando resultados...
        <br />
        <small>Isso pode levar 1-3 minutos</small>
      </div>
    </div>
  );
}
