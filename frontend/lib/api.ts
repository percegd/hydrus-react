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
  kd: number;
  kd_eff: number;
  initial_residual_mg_dm3: number;
  leaching_ratio_pct: number;
};
export type GalleryImage = { symbol: string; name: string; png: string };
export type ResultImages = {
  perfil: string | null;
  btc: string | null;
  evolucao: string | null;
  agua: string | null;
  galeria: GalleryImage[];
};
export type SimulateResponse = {
  drainage_mm: number;
  solutes: SoluteBalance[];
  images: ResultImages;
  applied_mm: number;
  eval_depth_cm: number;
  target_depth_cm: number;
  has_crop: boolean;
  z_max_cm: number;
  runoff_mm: number;
  storage_mm: number;
};

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`/api${path}`, { headers: { "Content-Type": "application/json" }, ...init });
  if (!r.ok) throw new Error(`API ${r.status}`);
  return r.json() as Promise<T>;
}

export const getSoils = () => req<Soil[]>("/soils");
export const getCrops = () => req<Crop[]>("/crops");
export const postSimulate = (body: unknown) => req<SimulateResponse>("/simulate", { method: "POST", body: JSON.stringify(body) });
export type JobCreated = { job_id: string };
export type JobStatus = {
  job_id: string;
  status: string;
  elapsed_s: number;
  result: SimulateResponse | null;
  error: string | null;
  has_excel?: boolean;
  has_report?: boolean;
  has_zip?: boolean;
};
export const postJob = (body: unknown) => req<JobCreated>("/jobs", { method: "POST", body: JSON.stringify(body) });
export const getJob = (id: string) => req<JobStatus>(`/jobs/${id}`);
export const getReport = (id: string) => req<{ report_markdown: string }>(`/jobs/${id}/report`);
