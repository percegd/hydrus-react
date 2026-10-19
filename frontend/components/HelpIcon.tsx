"use client";

import { useEffect, useState } from "react";
import { getHelp, type HelpEntry } from "../lib/api";

let cache: HelpEntry[] | null = null;
let inflight: Promise<HelpEntry[]> | null = null;

function loadHelp(): Promise<HelpEntry[]> {
  if (cache) return Promise.resolve(cache);
  if (!inflight) {
    inflight = getHelp()
      .then((entries) => {
        cache = entries;
        return entries;
      })
      .catch(() => [] as HelpEntry[])
      .finally(() => {
        inflight = null;
      }) as Promise<HelpEntry[]>;
  }
  return inflight;
}

export default function HelpIcon({ helpKey }: { helpKey: string }) {
  const [open, setOpen] = useState(false);
  const [entry, setEntry] = useState<HelpEntry | null>(null);

  useEffect(() => {
    if (!open || entry) return;
    loadHelp().then((entries) => {
      setEntry(entries.find((e) => e.key === helpKey) ?? null);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  return (
    <>
      <button
        type="button"
        className="help-badge"
        aria-label={`Ajuda sobre ${helpKey}`}
        title="O que é isto?"
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setOpen(true);
        }}
      >
        ?
      </button>
      {open && (
        <div
          className="modal-overlay"
          role="alertdialog"
          aria-modal="true"
          aria-label={entry?.title ?? "Ajuda"}
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
                  {entry ? (
                    <>
                      {entry.title} <span className="help-modal-unit">{entry.unit}</span>
                    </>
                  ) : (
                    "Carregando ajuda…"
                  )}
                </h3>
              </div>
            </div>
            {entry && (
              <div className="help-modal-body">
                <p>
                  <b>O que é:</b> {entry.what}
                </p>
                <p>
                  <b>Na simulação:</b> {entry.simulation}
                </p>
              </div>
            )}
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
        </div>
      )}
    </>
  );
}
