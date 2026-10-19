export type Soil = { key: string; name: string };
export type Crop = { key: string; name: string; root_depth_cm: number };
export type SoluteBalance = {
  symbol: string;
  name: string;
  dose_kg_ha: number;
  retained_root_pct: number;
  below_profile_pct: number;
  bottom_pct: number;
  uptaken_pct: number;
  peak_depth_cm: number | null;
};
export type SimulateResponse = { drainage_mm: number; solutes: SoluteBalance[]; plot_png_base64: string | null; profiles: { z: number[]; solutes: Record<string, { name: string; c: number[] }> } | null };

export class ApiError extends Error {
  details: string[];
  constructor(message: string, details: string[] = []) {
    super(message);
    this.name = "ApiError";
    this.details = details;
  }
}

function formatPydanticLoc(loc: unknown): string {
  if (!Array.isArray(loc)) return String(loc ?? "");
  return (loc as unknown[]).filter((v) => v !== "body").map(String).join(".");
}

function formatDetail(detail: unknown): { message: string; details: string[] } {
  if (typeof detail === "string") return { message: detail, details: [detail] };
  if (Array.isArray(detail)) {
    const parts: string[] = detail.map((item) => {
      if (item && typeof item === "object") {
        const o = item as Record<string, unknown>;
        if (typeof o.field === "string" && typeof o.message === "string") {
          return `${o.field}: ${o.message}`;
        }
        if (Array.isArray(o.loc) && (typeof o.msg === "string" || typeof o.message === "string")) {
          const msg = String(o.msg ?? o.message);
          const loc = formatPydanticLoc(o.loc);
          return loc ? `${loc}: ${msg}` : msg;
        }
        if (typeof o.msg === "string") return o.msg;
        if (typeof o.message === "string") return o.message;
      }
      try {
        return JSON.stringify(item);
      } catch {
        return String(item);
      }
    });
    return { message: parts.join("; "), details: parts };
  }
  if (detail && typeof detail === "object") {
    const o = detail as Record<string, unknown>;
    if (typeof o.message === "string") return { message: o.message, details: [o.message] };
  }
  try {
    const s = JSON.stringify(detail);
    return { message: s, details: [s] };
  } catch {
    return { message: String(detail), details: [String(detail)] };
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`/api${path}`, { headers: { "Content-Type": "application/json" }, ...init });
  if (!r.ok) {
    let message = `API ${r.status}`;
    let details: string[] = [];
    try {
      const data = (await r.json()) as { detail?: unknown; message?: unknown };
      const detail = data?.detail ?? data;
      if (detail !== undefined) {
        const f = formatDetail(detail);
        if (f.message) message = f.message;
        details = f.details;
      } else if (typeof (data as { message?: unknown })?.message === "string") {
        message = (data as { message: string }).message;
        details = [message];
      }
    } catch {
      /* mantém mensagem genérica */
    }
    throw new ApiError(message, details);
  }
  return r.json() as Promise<T>;
}

export const getSoils = () => req<Soil[]>("/soils");
export const getCrops = () => req<Crop[]>("/crops");
export const postSimulate = (body: unknown) => req<SimulateResponse>("/simulate", { method: "POST", body: JSON.stringify(body) });
export type JobCreated = { job_id: string };
export type JobStatus = { job_id: string; status: string; elapsed_s: number; result: SimulateResponse | null; error: string | null };
export const postJob = (body: unknown) => req<JobCreated>("/jobs", { method: "POST", body: JSON.stringify(body) });
export const getJob = (id: string) => req<JobStatus>(`/jobs/${id}`);
