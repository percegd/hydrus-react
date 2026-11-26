export type HydraulicInput = {
  thetaR: string;
  thetaS: string;
  alpha: string;
  n: string;
  ks: string;
  bulk: string;
  l: string;
};

function parseNum(raw: string): number {
  return parseFloat(String(raw).replace(",", "."));
}

export function formatCatalog(base: number | undefined, digits: number): string {
  if (base == null || !Number.isFinite(base)) return "";
  const f = 10 ** digits;
  return String(Math.round(base * f) / f);
}

export function valueDiffers(raw: string, base: number | undefined, digits: number): boolean {
  const shown = formatCatalog(base, digits);
  if (!shown) return false;
  const v = parseNum(raw);
  if (!Number.isFinite(v)) return false;
  return Math.abs(v - parseNum(shown)) > 1e-9;
}

export function soilHydraulicIssues(v: HydraulicInput): string[] {
  const tr = parseNum(v.thetaR);
  const ts = parseNum(v.thetaS);
  const alpha = parseNum(v.alpha);
  const n = parseNum(v.n);
  const ks = parseNum(v.ks);
  const bulk = parseNum(v.bulk);
  const l = parseNum(v.l);
  if (![tr, ts, alpha, n, ks, bulk, l].every(Number.isFinite)) {
    return ["Preencha θr, θs, α, n, Ks, ρb e l com números."];
  }
  const issues: string[] = [];
  if (!(tr >= 0 && tr < ts && ts <= 1)) issues.push("0 ≤ θr < θs ≤ 1.");
  if (!(alpha > 0)) issues.push("α deve ser maior que 0.");
  if (!(n > 1)) issues.push("n deve ser maior que 1.");
  else if (!(n > 1.05)) issues.push("n deve ser maior que 1,05 (van Genuchten).");
  if (!(ks > 0)) issues.push("Ks deve ser maior que 0.");
  if (!(bulk > 0)) issues.push("ρb deve ser maior que 0.");
  return issues;
}
