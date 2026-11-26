"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { FIELD_HELP } from "../lib/fieldHelp";

export default function HelpIcon({ helpKey }: { helpKey: string }) {
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const entry = FIELD_HELP[helpKey];

  useEffect(() => {
    setMounted(true);
  }, []);

  return (
    <>
      <button
        type="button"
        className="help-badge"
        aria-label={entry ? `Ajuda: ${entry.title}` : "Ajuda"}
        title="O que é isto?"
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          if (entry) setOpen(true);
        }}
      >
        ?
      </button>
      {open && mounted && entry
        ? createPortal(
            <div
              className="modal-overlay"
              role="alertdialog"
              aria-modal="true"
              aria-label={entry.title}
              onClick={() => setOpen(false)}
            >
              <div
                className="modal-card help-modal-card"
                role="document"
                onClick={(e) => e.stopPropagation()}
              >
                <div className="help-modal-head">
                  <div className="help-modal-icon">?</div>
                  <div>
                    <h3 className="help-modal-title">
                      {entry.title} {entry.unit ? <span className="help-modal-unit">{entry.unit}</span> : null}
                    </h3>
                  </div>
                </div>
                <div className="help-modal-body">
                  <p>
                    <b>O que é:</b> {entry.what}
                  </p>
                  <p>
                    <b>Na simulação:</b> {entry.simulation}
                  </p>
                </div>
                <div className="modal-actions">
                  <button
                    type="button"
                    className="btn-modal-confirm"
                    style={{ width: "100%" }}
                    onClick={() => setOpen(false)}
                    autoFocus
                  >
                    Entendi
                  </button>
                </div>
              </div>
            </div>,
            document.body
          )
        : null}
    </>
  );
}
