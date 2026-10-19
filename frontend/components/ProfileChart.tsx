"use client";

import { useEffect, useRef } from "react";

const COLORS: Record<string, string> = { N: "#d95f02", K: "#7570b3", Ca: "#1b9e77", Mg: "#e7298a", S: "#e6ab02", P: "#66a61e" };

export default function ProfileChart({ profiles, rootDepth }: { profiles: { z: number[]; solutes: Record<string, { name: string; c: number[] }> } | null; rootDepth: number }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!profiles || !ref.current) return;
    let cancelled = false;
    (async () => {
      const Plotly = (await import("plotly.js-dist-min")).default;
      if (cancelled || !ref.current) return;
      const traces = Object.entries(profiles.solutes).map(([sym, s]) => ({
        x: s.c,
        y: profiles.z,
        mode: "lines" as const,
        name: `${s.name} (${sym})`,
        line: { color: COLORS[sym] ?? "#388e3c", width: 2.5 },
        fill: "tozerox" as const,
        fillcolor: (COLORS[sym] ?? "#388e3c") + "33",
      }));
      Plotly.react(ref.current, traces as never[], {
        margin: { l: 60, r: 20, t: 10, b: 50 },
        xaxis: { title: { text: "Teor no solo [mg/cm³]" } },
        yaxis: { title: { text: "Profundidade [cm]" }, autorange: "reversed" as const },
        shapes: [
          { type: "rect", xref: "paper", yref: "y", x0: 0, x1: 1, y0: 0, y1: rootDepth, fillcolor: "#2ca02c", opacity: 0.08, line: { width: 0 } },
        ],
        legend: { orientation: "h" as const, y: -0.25 },
      }, { responsive: true, displayModeBar: true });
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(profiles)]);

  return <div ref={ref} style={{ width: "100%", height: 480 }} />;
}
