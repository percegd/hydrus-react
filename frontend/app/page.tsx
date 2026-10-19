"use client";

import { useEffect, useRef, useState } from "react";
import Results from "../components/Results";
import StepIntro from "../components/StepIntro";
import StepNutrients, { DEFAULT_ROWS, SPECIES, defaultDispForDepth, type NutrientRow } from "../components/StepNutrients";
import StepSoil from "../components/StepSoil";
import StepWater from "../components/StepWater";
import WizardProgress from "../components/WizardProgress";
import { ApiError, getCrops, getExcelBlob, getJob, getReport, getSoils, postJob, type Crop, type SimulateResponse, type Soil } from "../lib/api";

const STEP_TITLES = [
  { title: "Apresentação", sub: "Visão geral da plataforma de simulação." },
  { title: "Passo 1 de 4: Solo e cultura", sub: "Defina o solo e a cultura do cenário." },
  { title: "Passo 2 de 4: Nutrientes e manejo", sub: "Solutos, doses, liberação e aplicação." },
  { title: "Passo 3 de 4: Regime hídrico", sub: "Defina o cenário hídrico da simulação." },
  { title: "Passo 4 de 4: Resultados", sub: "Balanço de massa, perfil e laudo." },
];

const DEFAULTS = {
  soil: "latossolo_medio",
  cropMode: "sem",
  crop: "soja",
  depthCm: "200",
  rootDepthCm: "35",
  days: "7",
  rainMode: "uniform" as const,
  rainMm: "60",
  moisture: "80",
  et0: "4.0",
  series: "",
  et0Series: "",
  rows: DEFAULT_ROWS,
  placement: "surface",
  appDay: "0",
  zTop: "5",
  zBottom: "10",
  c0: "20",
  pulse: "7",
  fertContinuous: false,
};

export default function Home() {
  const [step, setStep] = useState(0);
  const [soils, setSoils] = useState<Soil[]>([]);
  const [crops, setCrops] = useState<Crop[]>([]);
  const [soil, setSoil] = useState(DEFAULTS.soil);
  const [cropMode, setCropModeState] = useState(DEFAULTS.cropMode);
  const [crop, setCrop] = useState(DEFAULTS.crop);
  const [depthCm, setDepthCm] = useState(DEFAULTS.depthCm);
  const [rootDepthCm, setRootDepthCm] = useState(DEFAULTS.rootDepthCm);
  const [days, setDays] = useState(DEFAULTS.days);
  const [rainMode, setRainMode] = useState<"uniform" | "series">(DEFAULTS.rainMode);
  const [rainMm, setRainMm] = useState(DEFAULTS.rainMm);
  const [moisture, setMoisture] = useState(DEFAULTS.moisture);
  const [et0, setEt0] = useState(DEFAULTS.et0);
  const [series, setSeries] = useState(DEFAULTS.series);
  const [et0Series, setEt0Series] = useState(DEFAULTS.et0Series);
  const [rows, setRows] = useState<NutrientRow[]>(DEFAULTS.rows.map((r) => ({ ...r })));
  const [placement, setPlacement] = useState(DEFAULTS.placement);
  const [appDay, setAppDay] = useState(DEFAULTS.appDay);
  const [zTop, setZTop] = useState(DEFAULTS.zTop);
  const [zBottom, setZBottom] = useState(DEFAULTS.zBottom);
  const [c0, setC0] = useState(DEFAULTS.c0);
  const [pulse, setPulse] = useState(DEFAULTS.pulse);
  const [fertContinuous, setFertContinuous] = useState(DEFAULTS.fertContinuous);
  const [jobId, setJobId] = useState("");
  const [jobState, setJobState] = useState("");
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<string[]>([]);
  const [result, setResult] = useState<SimulateResponse | null>(null);
  const [report, setReport] = useState("");
  const [appliedMm, setAppliedMm] = useState<number | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    getSoils().then(setSoils).catch(() => setError("API fora do ar (backend :8001)."));
    getCrops().then((cs) => {
      setCrops(cs);
      // Prefill raiz da cultura selecionada (Gradio: root_depth da cultura).
      const found = cs.find((c) => c.key === crop);
      if (found) {
        setRootDepthCm((prev) => (prev === "" ? String(found.root_depth_cm) : prev));
      }
    }).catch(() => {});
    return () => { if (timer.current) clearInterval(timer.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function setCropMode(mode: string) {
    setCropModeState(mode);
    if (mode === "com") {
      const found = crops.find((c) => c.key === crop);
      if (found) setRootDepthCm(String(found.root_depth_cm));
    }
  }

  function handleCropSelect(key: string) {
    setCrop(key);
    const found = crops.find((c) => c.key === key);
    if (found) setRootDepthCm(String(found.root_depth_cm));
  }

  function showApiError(e: unknown) {
    if (e instanceof ApiError && e.details.length > 0) {
      setFieldErrors(e.details);
      setError("");
    } else {
      setFieldErrors([]);
      setError(String(e instanceof Error ? e.message : e));
    }
  }
  function setRow(i: number, patch: Partial<NutrientRow>) {
    setRows((rs) => rs.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  }
  function addRow() {
    const used = new Set(rows.map((r) => r.symbol));
    const next = SPECIES.find((s) => !used.has(s.symbol)) ?? SPECIES[0];
    setRows((rs) => [...rs, { symbol: next.symbol, name: next.name, dose: "30", kd: String(next.kd), disp: defaultDispForDepth(depthCm), res: "0", rel: "immediate", relDays: "60" }]);
  }
  function removeRow(i: number) {
    setRows((rs) => rs.filter((_, j) => j !== i));
  }

  function parseSeries(text: string): number[] | undefined {
    if (!text.trim()) return undefined;
    const vals = text.split(/[\s,;]+/).filter(Boolean).map((t) => Number(t.replace(",", ".")));
    if (vals.some((v) => Number.isNaN(v) || v < 0)) throw new Error("Série inválida (só números ≥ 0).");
    return vals;
  }

  function num(x: string, def: number): number {
    const v = parseFloat(String(x).replace(",", "."));
    return Number.isNaN(v) ? def : v;
  }

  function resetToDefaults() {
    if (timer.current) clearInterval(timer.current);
    setSoil(DEFAULTS.soil);
    setCropModeState(DEFAULTS.cropMode);
    setCrop(DEFAULTS.crop);
    setDepthCm(DEFAULTS.depthCm);
    setRootDepthCm(DEFAULTS.rootDepthCm);
    setDays(DEFAULTS.days);
    setRainMode(DEFAULTS.rainMode);
    setRainMm(DEFAULTS.rainMm);
    setMoisture(DEFAULTS.moisture);
    setEt0(DEFAULTS.et0);
    setSeries(DEFAULTS.series);
    setEt0Series(DEFAULTS.et0Series);
    setRows(DEFAULTS.rows.map((r) => ({ ...r })));
    setPlacement(DEFAULTS.placement);
    setAppDay(DEFAULTS.appDay);
    setZTop(DEFAULTS.zTop);
    setZBottom(DEFAULTS.zBottom);
    setC0(DEFAULTS.c0);
    setPulse(DEFAULTS.pulse);
    setFertContinuous(DEFAULTS.fertContinuous);
    setJobId("");
    setJobState("");
    setElapsed(0);
    setError("");
    setFieldErrors([]);
    setResult(null);
    setReport("");
    setAppliedMm(null);
    setStep(1);
  }

  function handleNewSimulation() {
    if (window.confirm("Deseja iniciar uma nova simulação? Os dados atuais serão perdidos.")) {
      resetToDefaults();
    }
  }

  async function run() {
    setError("");
    setFieldErrors([]);
    setResult(null);
    setReport("");
    setAppliedMm(null);
    let rain_series: number[] | undefined;
    let total_days = num(days, 7);
    let et0_series: number[] | undefined;
    try {
      if (rainMode === "series") {
        rain_series = parseSeries(series);
        if (!rain_series?.length) { setFieldErrors([]); setError("Cole a série diária de chuva."); return; }
        total_days = rain_series.length;
      }
      et0_series = parseSeries(et0Series);
    } catch (e) { setFieldErrors([]); setError(String((e as Error).message || e)); return; }
    const depthVal = num(depthCm, 200);
    const dispDefault = depthVal / 10;
    const solutes = rows
      .filter((r) => parseFloat(String(r.dose).replace(",", ".")) > 0)
      .map((r) => ({
        symbol: r.symbol, name: r.name, dose_kg_ha: parseFloat(String(r.dose).replace(",", ".")), kd: num(r.kd, 0),
        dispersivity_cm: r.disp === "" ? dispDefault : num(r.disp, dispDefault),
        initial_residual_mg_dm3: r.res === "" ? 0 : num(r.res, 0),
        release_type: r.rel === "controlled" ? "controlled" : "immediate", release_days: num(r.relDays, 60),
      }));
    if (!solutes.length) { setFieldErrors([]); setError("Informe ao menos 1 soluto com dose > 0."); return; }
    const appliedTotal = rain_series ? rain_series.reduce((a, b) => a + b, 0) : num(rainMm, 0);
    setAppliedMm(appliedTotal);
    setStep(4);
    setJobState("queued");
    // Posicionamento: faixas do Gradio (superfície 0–2, sulco 5–10, personalizada, fertirrigação).
    let z_top = 0;
    let z_bottom = 2;
    if (placement === "furrow") {
      z_top = 5;
      z_bottom = 10;
    } else if (placement === "custom") {
      z_top = num(zTop, 5);
      z_bottom = num(zBottom, 10);
    } else if (placement === "fertigation") {
      z_top = 0;
      z_bottom = 0;
    }
    const isCom = cropMode === "com";
    const cropEntry = crops.find((c) => c.key === crop);
    const rootFallback = cropEntry ? cropEntry.root_depth_cm : 35;
    try {
      const body = {
        soil_key: soil,
        crop_key: isCom ? crop : null,
        depth_cm: depthVal,
        root_depth_cm: isCom ? num(rootDepthCm, rootFallback) : null,
        total_days,
        rain_mm: num(rainMm, 0), rain_series,
        initial_moisture_pct: num(moisture, 80),
        et0_mm_day: num(et0, 0), et0_series, solutes,
        placement: {
          mode: placement, z_top_cm: z_top, z_bottom_cm: z_bottom,
          fertigation_c0_mg_l: num(c0, 20),
          fertigation_pulse_days: fertContinuous ? 0 : num(pulse, 7),
          application_day: num(appDay, 0),
        },
      };
      const { job_id } = await postJob(body);
      setJobId(job_id);
      setJobState("running");
      let pollErrors = 0;
      timer.current = setInterval(async () => {
        try {
          const st = await getJob(job_id);
          pollErrors = 0;
          setElapsed(st.elapsed_s);
          if (st.status === "done") {
            if (timer.current) clearInterval(timer.current);
            setJobState("done");
            setResult(st.result);
          } else if (st.status === "failed") {
            if (timer.current) clearInterval(timer.current);
            setJobState("failed");
            setError(st.error || "Falha na simulação.");
          } else {
            setJobState(st.status);
          }
        } catch (e) {
          if (e instanceof ApiError && (e.status === 404 || e.status === 410)) {
            if (timer.current) clearInterval(timer.current);
            setJobState("expired");
            setFieldErrors([]);
            setError("A simulação expirou; rode novamente.");
            return;
          }
          pollErrors += 1;
          if (pollErrors >= 5) {
            if (timer.current) clearInterval(timer.current);
            setJobState("failed");
            setFieldErrors([]);
            setError(e instanceof Error ? e.message : String(e));
          }
          /* senão mantém polling */
        }
      }, 1000);
    } catch (e) {
      setJobState("failed");
      showApiError(e);
    }
  }

  async function loadReport() {
    setError("");
    try {
      const markdown = await getReport(jobId);
      setReport(markdown);
    } catch (e) {
      if (e instanceof ApiError && (e.status === 404 || e.status === 410)) {
        setFieldErrors([]);
        setError("Job expirado; rode a simulação novamente.");
        return;
      }
      showApiError(e);
    }
  }

  async function downloadExcel() {
    setError("");
    try {
      const blob = await getExcelBlob(jobId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `perfil_${jobId}.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      if (e instanceof ApiError && (e.status === 404 || e.status === 410)) {
        setFieldErrors([]);
        setError("Job expirado; rode a simulação novamente.");
        return;
      }
      showApiError(e);
    }
  }

  const isCom = cropMode === "com";
  const cropEntry = crops.find((c) => c.key === crop);
  const rootDepth = isCom ? num(rootDepthCm, cropEntry?.root_depth_cm ?? 35) : num(depthCm, 200);
  const cropName = isCom ? (cropEntry?.name ?? crop) : "Sem cultura";

  return (
    <div className="hydrus-container">
      <header className="app-header">
        <h1 className="app-title"><span className="leaf">🌱</span> Simulação e Física de Solos</h1>
        <div className="app-subtitle">Simulação de transporte de água e nutrientes no perfil do solo</div>
      </header>

      <WizardProgress current={step} />

      <div className="wizard-step-box">
        {step === 0 ? (
          <StepIntro onStart={() => setStep(1)} />
        ) : (
          <>
            <div className="wizard-question-header">
              <h2 className="wizard-question-title">{STEP_TITLES[step].title}</h2>
              <p className="wizard-question-subtitle">{STEP_TITLES[step].sub}</p>
            </div>

            {step === 1 && (
              <StepSoil
                soils={soils}
                crops={crops}
                soil={soil}
                setSoil={setSoil}
                cropMode={cropMode}
                setCropMode={setCropMode}
                crop={crop}
                setCrop={handleCropSelect}
                depthCm={depthCm}
                setDepthCm={setDepthCm}
                rootDepthCm={rootDepthCm}
                setRootDepthCm={setRootDepthCm}
                error={error}
                fieldErrors={fieldErrors}
                onNext={() => setStep(2)}
              />
            )}

            {step === 2 && (
              <StepNutrients
                rows={rows}
                setRow={setRow}
                addRow={addRow}
                removeRow={removeRow}
                placement={placement}
                setPlacement={setPlacement}
                appDay={appDay}
                setAppDay={setAppDay}
                zTop={zTop}
                setZTop={setZTop}
                zBottom={zBottom}
                setZBottom={setZBottom}
                c0={c0}
                setC0={setC0}
                pulse={pulse}
                setPulse={setPulse}
                fertContinuous={fertContinuous}
                setFertContinuous={setFertContinuous}
                error={error}
                fieldErrors={fieldErrors}
                onBack={() => setStep(1)}
                onNext={() => setStep(3)}
              />
            )}

            {step === 3 && (
              <StepWater
                days={days}
                setDays={setDays}
                rainMode={rainMode}
                setRainMode={setRainMode}
                rainMm={rainMm}
                setRainMm={setRainMm}
                moisture={moisture}
                setMoisture={setMoisture}
                et0={et0}
                setEt0={setEt0}
                series={series}
                setSeries={setSeries}
                et0Series={et0Series}
                setEt0Series={setEt0Series}
                error={error}
                fieldErrors={fieldErrors}
                onBack={() => setStep(2)}
                onRun={run}
              />
            )}

            {step === 4 && (
              <Results
                jobState={jobState}
                elapsed={elapsed}
                result={result}
                report={report}
                error={error}
                fieldErrors={fieldErrors}
                cropName={cropName}
                rootDepth={rootDepth}
                appliedMm={appliedMm}
                onEdit={() => { if (timer.current) clearInterval(timer.current); setStep(3); setResult(null); setReport(""); }}
                onDownloadExcel={downloadExcel}
                onLoadReport={loadReport}
                onNewSimulation={handleNewSimulation}
              />
            )}
          </>
        )}
      </div>
    </div>
  );
}
