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
export type WaterBalance = {
  applied_mm: number;
  drainage_mm: number;
  storage_mm: number;
  runoff_mm: number;
  evap_mm: number | null;
  transp_mm: number | null;
  applied_label: string;
  drainage_label: string;
};
export type SimulateResponse = { drainage_mm: number; solutes: SoluteBalance[]; plot_png_base64: string | null; plots_png_base64?: Record<string, string> | null; profiles: { z: number[]; solutes: Record<string, { name: string; c: number[] }> } | null; water_only?: boolean; water_balance?: WaterBalance | null };

export class ApiError extends Error {
  details: string[];
  status: number;
  constructor(message: string, details: string[] = [], status = 0) {
    super(message);
    this.name = "ApiError";
    this.details = details;
    this.status = status;
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
    throw await toApiError(r);
  }
  return r.json() as Promise<T>;
}

async function toApiError(r: Response): Promise<ApiError> {
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
  return new ApiError(message, details, r.status);
}

export type HubInfo = { key: string; label: string; name: string; lat: number | null; lon: number | null; mean_annual_mm: number | null };
export type ClimateRow = { day: number; rain_mm: number; et0_mm: number };
export type HubSeries = { hub_key: string; hub_label: string; scenario: string; scenario_label: string; year: number | null; days: number; rain_series: number[]; et0_series: number[]; rows: ClimateRow[]; total_rain_mm: number };
export type ClimateExample = { headers: string[]; rows: ClimateRow[]; filename: string; csv: string };
export type ClimateParseResult = { rows: ClimateRow[]; records_read: number; total_rain_mm: number; message: string };

export type FertilizerInfo = { key: string; label: string; name: string; nutrient_pcts: Record<string, number>; descr: string };
export type BlendPresetInfo = { key: string; label: string; nutrient_pcts: Record<string, number> };
export type FertilizerCatalog = { commercial: FertilizerInfo[]; blend_presets: BlendPresetInfo[] };
export type FertilizerDoseBody = { fert_key?: string; gross_dose: number; nutrient_symbol?: string; custom_pcts?: Record<string, number>; blend_preset?: string };
export type FertilizerDoseResult = { fert_key: string; fert_name: string; gross_dose: number; nutrient_pcts: Record<string, number>; elemental_doses: Record<string, number>; message: string };
export type RosettaResult = { theta_r: number; theta_s: number; alpha: number; n: number; ks: number; bulk_density: number; silt_pct: number; texture: string };
export type KdEntry = { symbol: string; kd: number; citation: string; description: string; texture?: string | null; langmuir?: Record<string, unknown> | null };
export type KdResult = { soil_key: string | null; sand_pct: number | null; clay_pct: number | null; texture: string; entries: KdEntry[] };

export const getFertilizers = () => req<FertilizerCatalog>("/fertilizers");
export const postFertilizerDose = (body: FertilizerDoseBody) =>
  req<FertilizerDoseResult>("/fertilizers/dose", { method: "POST", body: JSON.stringify(body) });
export const postRosetta = (body: { sand_pct: number; clay_pct: number; bulk_density?: number }) =>
  req<RosettaResult>("/soils/rosetta", { method: "POST", body: JSON.stringify(body) });
export const getKd = (params: { soil_key?: string; sand?: number; clay?: number; symbol?: string }) => {
  const q = new URLSearchParams();
  if (params.soil_key) q.set("soil_key", params.soil_key);
  if (params.sand !== undefined) q.set("sand", String(params.sand));
  if (params.clay !== undefined) q.set("clay", String(params.clay));
  if (params.symbol) q.set("symbol", params.symbol);
  const qs = q.toString();
  return req<KdResult>(`/kd${qs ? `?${qs}` : ""}`);
};

export const getSoils = () => req<Soil[]>("/soils");
export const getHubs = () => req<HubInfo[]>("/hubs");
export const getHubSeries = (key: string, scenario: string) =>
  req<HubSeries>(`/hubs/${encodeURIComponent(key)}/series?scenario=${encodeURIComponent(scenario)}`);
export const getClimateExample = () => req<ClimateExample>("/climate/example");
export const parseClimateFile = async (file: File): Promise<ClimateParseResult> => {
  const form = new FormData();
  form.append("file", file);
  const r = await fetch("/api/climate/parse", { method: "POST", body: form });
  if (!r.ok) {
    throw await toApiError(r);
  }
  return r.json() as Promise<ClimateParseResult>;
};
export const getCrops = () => req<Crop[]>("/crops");
export const postSimulate = (body: unknown) => req<SimulateResponse>("/simulate", { method: "POST", body: JSON.stringify(body) });
export type JobCreated = { job_id: string };
export type JobStatus = { job_id: string; status: string; elapsed_s: number; result: SimulateResponse | null; error: string | null };
export const postJob = (body: unknown) => req<JobCreated>("/jobs", { method: "POST", body: JSON.stringify(body) });
export const getJob = (id: string) => req<JobStatus>(`/jobs/${id}`);
export const getReport = async (id: string): Promise<string> => {
  const j = await req<{ report_markdown: string }>(`/jobs/${id}/report`);
  return j.report_markdown;
};
export const getExcelBlob = async (id: string): Promise<Blob> => {
  const r = await fetch(`/api/jobs/${id}/excel`);
  if (!r.ok) {
    throw await toApiError(r);
  }
  return r.blob();
};
