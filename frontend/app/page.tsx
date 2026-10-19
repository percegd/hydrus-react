"use client";

import { useEffect, useRef, useState } from "react";
import Results from "../components/Results";
import StepIntro from "../components/StepIntro";
import StepNutrients, { DEFAULT_ROWS, NUTRIENT_SYMBOLS, SPECIES, defaultDispForDepth, type NutrientRow } from "../components/StepNutrients";
import StepSoil from "../components/StepSoil";
import StepWater, { emptyRows, type RainMode } from "../components/StepWater";
import WizardProgress from "../components/WizardProgress";
import { ApiError, getCrops, getExcelBlob, getJob, getKd, getReport, getSoils, postJob, postRosetta, type ClimateRow, type Crop, type SimulateResponse, type Soil } from "../lib/api";

const STEP_TITLES = [
  { title: "Apresentação", sub: "Visão geral da plataforma de simulação." },
  { title: "Passo 1 de 4: Solo e cultura", sub: "Defina o solo e a cultura do cenário." },
  { title: "Passo 2 de 4: Nutrientes e manejo", sub: "Solutos, doses, liberação e aplicação." },
  { title: "Passo 3 de 4: Regime hídrico", sub: "Defina o cenário hídrico da simulação." },
  { title: "Passo 4 de 4: Resultados", sub: "Balanço de massa, perfil e laudo." },
];

const DEFAULTS = {
  soil: "latossolo_medio",
  isCustomSoil: false,
  sandPct: "60",
  clayPct: "25",
  thetaR: "0.1",
  thetaS: "0.43",
  vgAlpha: "0.03",
  vgN: "1.65",
  ks: "80",
  bulk: "1.3",
  cropMode: "sem",
  crop: "soja",
  depthCm: "200",
  rootDepthCm: "35",
  days: "7",
  rainMode: "uniform" as RainMode,
  rainMm: "60",
  moisture: "80",
  et0: "4.0",
  hubKey: "",
  hubScenario: "medio",
  hubAppDay: "30",
  uploadAppDay: "30",
  waterOnly: false,
  analysisStart: "1",
  analysisEnd: "365",
  printDays: "55, 128, 237, 365",
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
  const [isCustomSoil, setIsCustomSoil] = useState(DEFAULTS.isCustomSoil);
  const [sandPct, setSandPct] = useState(DEFAULTS.sandPct);
  const [clayPct, setClayPct] = useState(DEFAULTS.clayPct);
  const [thetaR, setThetaR] = useState(DEFAULTS.thetaR);
  const [thetaS, setThetaS] = useState(DEFAULTS.thetaS);
  const [vgAlpha, setVgAlpha] = useState(DEFAULTS.vgAlpha);
  const [vgN, setVgN] = useState(DEFAULTS.vgN);
  const [ks, setKs] = useState(DEFAULTS.ks);
  const [bulk, setBulk] = useState(DEFAULTS.bulk);
  const [rosettaNote, setRosettaNote] = useState("");
  const [kdInfo, setKdInfo] = useState<Record<string, { kd: string; citation: string }>>({});
  const [cropMode, setCropModeState] = useState(DEFAULTS.cropMode);
  const [crop, setCrop] = useState(DEFAULTS.crop);
  const [depthCm, setDepthCm] = useState(DEFAULTS.depthCm);
  const [rootDepthCm, setRootDepthCm] = useState(DEFAULTS.rootDepthCm);
  const [days, setDays] = useState(DEFAULTS.days);
  const [rainMode, setRainMode] = useState<RainMode>(DEFAULTS.rainMode);
  const [rainMm, setRainMm] = useState(DEFAULTS.rainMm);
  const [moisture, setMoisture] = useState(DEFAULTS.moisture);
  const [et0, setEt0] = useState(DEFAULTS.et0);
  const [climateRows, setClimateRows] = useState<ClimateRow[]>(() => emptyRows(365));
  const [hubKey, setHubKey] = useState(DEFAULTS.hubKey);
  const [hubScenario, setHubScenario] = useState(DEFAULTS.hubScenario);
  const [hubAppDay, setHubAppDay] = useState(DEFAULTS.hubAppDay);
  const [uploadAppDay, setUploadAppDay] = useState(DEFAULTS.uploadAppDay);
  const [waterOnly, setWaterOnly] = useState(DEFAULTS.waterOnly);
  const [analysisStart, setAnalysisStart] = useState(DEFAULTS.analysisStart);
  const [analysisEnd, setAnalysisEnd] = useState(DEFAULTS.analysisEnd);
  const [printDays, setPrintDays] = useState(DEFAULTS.printDays);
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

  // Solo personalizado: areia/argila -> Rosetta preenche θr θs α n Ks ρb (Gradio).
  useEffect(() => {
    if (!isCustomSoil) {
      setRosettaNote("");
      return;
    }
    const sand = parseFloat(sandPct.replace(",", "."));
    const clay = parseFloat(clayPct.replace(",", "."));
    if (!Number.isFinite(sand) || !Number.isFinite(clay) || sand + clay > 100) return;
    const t = setTimeout(() => {
      const bulkNum = parseFloat(bulk.replace(",", "."));
      postRosetta({ sand_pct: sand, clay_pct: clay, bulk_density: Number.isFinite(bulkNum) ? bulkNum : undefined })
        .then((r) => {
          setThetaR(String(r.theta_r));
          setThetaS(String(r.theta_s));
          setVgAlpha(String(r.alpha));
          setVgN(String(r.n));
          setKs(String(r.ks));
          setBulk(String(r.bulk_density));
          setRosettaNote(`Silte: ${r.silt_pct}% • Classe: ${r.texture} • Areia (${sand}%) + Argila (${clay}%) + Silte (${r.silt_pct}%) = 100%`);
        })
        .catch(() => setRosettaNote("Rosetta indisponível para esta granulometria."));
    }, 400);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isCustomSoil, sandPct, clayPct]);

  // Kd de literatura por textura: preenche as linhas ao trocar o solo (Gradio),
  // preservando valores editados manualmente (badge "Editado").
  useEffect(() => {
    const params = isCustomSoil
      ? { sand: parseFloat(sandPct.replace(",", ".")), clay: parseFloat(clayPct.replace(",", ".")), }
      : { soil_key: soil };
    if (params.sand !== undefined && (!Number.isFinite(params.sand) || !Number.isFinite(params.clay as number))) return;
    getKd(params).then((r) => {
      const info: Record<string, { kd: string; citation: string }> = {};
      for (const e of r.entries) info[e.symbol] = { kd: String(e.kd), citation: e.citation };
      setKdInfo(info);
      setRows((rs) => rs.map((row) => {
        if (row.kdEdited) return row;
        const lit = info[row.symbol];
        if (!lit) return row;
        return { ...row, kd: lit.kd, kdSource: lit.citation };
      }));
    }).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [soil, isCustomSoil, sandPct, clayPct]);

  function applyFertilizer(doses: Record<string, number>) {
    setRows((rs) => {
      const next = rs.map((r) => ({ ...r }));
      for (const sym of NUTRIENT_SYMBOLS) {
        const dose = doses[sym] ?? 0;
        if (dose <= 0) continue;
        const lit = kdInfo[sym];
        const sp = SPECIES.find((s) => s.symbol === sym);
        const idx = next.findIndex((r) => r.symbol === sym);
        if (idx >= 0) {
          next[idx] = { ...next[idx], dose: String(Math.round(dose * 10) / 10), kd: lit?.kd ?? next[idx].kd, kdEdited: false, kdSource: lit?.citation ?? "" };
        } else {
          next.push({
            symbol: sym, name: sp?.name ?? sym, dose: String(Math.round(dose * 10) / 10),
            kd: lit?.kd ?? String(sp?.kd ?? 0), disp: defaultDispForDepth(depthCm), res: "0",
            rel: "immediate", relDays: "60", kdEdited: false, kdSource: lit?.citation ?? "",
          });
        }
      }
      return next;
    });
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
    const lit = kdInfo[next.symbol];
    setRows((rs) => [...rs, { symbol: next.symbol, name: next.name, dose: "30", kd: lit?.kd ?? String(next.kd), disp: defaultDispForDepth(depthCm), res: "0", rel: "immediate", relDays: "60", kdEdited: false, kdSource: lit?.citation ?? "" }]);
  }
  function removeRow(i: number) {
    setRows((rs) => rs.filter((_, j) => j !== i));
  }

  function num(x: string, def: number): number {
    const v = parseFloat(String(x).replace(",", "."));
    return Number.isNaN(v) ? def : v;
  }

  function resetToDefaults() {
    if (timer.current) clearInterval(timer.current);
    setSoil(DEFAULTS.soil);
    setIsCustomSoil(DEFAULTS.isCustomSoil);
    setSandPct(DEFAULTS.sandPct);
    setClayPct(DEFAULTS.clayPct);
    setThetaR(DEFAULTS.thetaR);
    setThetaS(DEFAULTS.thetaS);
    setVgAlpha(DEFAULTS.vgAlpha);
    setVgN(DEFAULTS.vgN);
    setKs(DEFAULTS.ks);
    setBulk(DEFAULTS.bulk);
    setRosettaNote("");
    setKdInfo({});
    setCropModeState(DEFAULTS.cropMode);
    setCrop(DEFAULTS.crop);
    setDepthCm(DEFAULTS.depthCm);
    setRootDepthCm(DEFAULTS.rootDepthCm);
    setDays(DEFAULTS.days);
    setRainMode(DEFAULTS.rainMode);
    setRainMm(DEFAULTS.rainMm);
    setMoisture(DEFAULTS.moisture);
    setEt0(DEFAULTS.et0);
    setClimateRows(emptyRows(365));
    setHubKey(DEFAULTS.hubKey);
    setHubScenario(DEFAULTS.hubScenario);
    setHubAppDay(DEFAULTS.hubAppDay);
    setUploadAppDay(DEFAULTS.uploadAppDay);
    setWaterOnly(DEFAULTS.waterOnly);
    setAnalysisStart(DEFAULTS.analysisStart);
    setAnalysisEnd(DEFAULTS.analysisEnd);
    setPrintDays(DEFAULTS.printDays);
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
    if (timer.current) clearInterval(timer.current);
    setError("");
    setFieldErrors([]);
    setResult(null);
    setReport("");
    setAppliedMm(null);
    let rain_series: number[] | undefined;
    let total_days = num(days, 7);
    let et0_series: number[] | undefined;
    let appDayEff = appDay;
    try {
      if (rainMode === "hub" || rainMode === "upload") {
        if (!climateRows.length) { setFieldErrors([]); setError("A tabela de série diária está vazia. Preencha a coluna de chuva (mm)."); return; }
        rain_series = climateRows.map((r) => {
          if (!Number.isFinite(r.rain_mm) || r.rain_mm < 0) throw new Error("Série inválida (só números ≥ 0).");
          return r.rain_mm;
        });
        et0_series = climateRows.map((r) => {
          if (!Number.isFinite(r.et0_mm) || r.et0_mm < 0) throw new Error("Série inválida (só números ≥ 0).");
          return r.et0_mm;
        });
        if (!rain_series.some((v) => v > 0)) { setFieldErrors([]); setError("A tabela de série diária está vazia. Preencha a coluna de chuva (mm)."); return; }
        total_days = rain_series.length;
        appDayEff = rainMode === "hub" ? hubAppDay : uploadAppDay;
      }
    } catch (e) { setFieldErrors([]); setError(String((e as Error).message || e)); return; }
    const depthVal = num(depthCm, 200);
    const dispDefault = depthVal / 10;
    const solutes = waterOnly ? [] : rows
      .filter((r) => parseFloat(String(r.dose).replace(",", ".")) > 0)
      .map((r) => {
        const dispNum = num(r.disp, dispDefault);
        return {
          symbol: r.symbol, name: r.name, dose_kg_ha: parseFloat(String(r.dose).replace(",", ".")), kd: num(r.kd, 0),
          dispersivity_cm: dispNum > 0 ? dispNum : dispDefault,
          initial_residual_mg_dm3: r.res === "" ? 0 : num(r.res, 0),
          release_type: r.rel === "controlled" ? "controlled" : "immediate", release_days: num(r.relDays, 60),
        };
      });
    if (!waterOnly && !solutes.length) { setFieldErrors([]); setError("Informe ao menos 1 soluto com dose > 0."); return; }
    let print_days: number[] | undefined;
    let analysis_start_day = 1;
    let analysis_end_day = 365;
    if (rainMode === "hub" || rainMode === "upload") {
      try {
        analysis_start_day = Math.round(num(analysisStart, 1));
        analysis_end_day = Math.round(num(analysisEnd, 365));
        const raw = String(printDays).trim();
        if (!raw) {
          print_days = [];
        } else {
          print_days = raw.split(/[\s;,]+/).filter(Boolean).map((t) => Number(t.replace(",", ".")));
          if (print_days.some((v) => !Number.isFinite(v) || v < 0)) throw new Error("Dias de leitura inválidos (só números ≥ 0).");
        }
      } catch (e) { setFieldErrors([]); setError(String((e as Error).message || e)); return; }
    }
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
        custom_soil: isCustomSoil ? {
          sand_pct: num(sandPct, 60),
          clay_pct: num(clayPct, 25),
          bulk_density: num(bulk, 1.3),
          theta_r: num(thetaR, 0.1),
          theta_s: num(thetaS, 0.43),
          alpha: num(vgAlpha, 0.03),
          n: num(vgN, 1.65),
          ks: num(ks, 80),
        } : null,
        crop_key: isCom ? crop : null,
        depth_cm: depthVal,
        root_depth_cm: isCom ? num(rootDepthCm, rootFallback) : null,
        total_days,
        rain_mm: num(rainMm, 0), rain_series,
        initial_moisture_pct: num(moisture, 80),
        et0_mm_day: num(et0, 0), et0_series, solutes,
        water_only: waterOnly,
        analysis_start_day,
        analysis_end_day,
        print_days,
        placement: {
          mode: placement, z_top_cm: z_top, z_bottom_cm: z_bottom,
          fertigation_c0_mg_l: num(c0, 20),
          fertigation_pulse_days: fertContinuous ? 0 : num(pulse, 7),
          application_day: num(appDayEff, 0),
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
                isCustomSoil={isCustomSoil}
                setIsCustomSoil={setIsCustomSoil}
                sandPct={sandPct}
                setSandPct={setSandPct}
                clayPct={clayPct}
                setClayPct={setClayPct}
                thetaR={thetaR}
                setThetaR={setThetaR}
                thetaS={thetaS}
                setThetaS={setThetaS}
                vgAlpha={vgAlpha}
                setVgAlpha={setVgAlpha}
                vgN={vgN}
                setVgN={setVgN}
                ks={ks}
                setKs={setKs}
                bulk={bulk}
                setBulk={setBulk}
                rosettaNote={rosettaNote}
                error={error}
                fieldErrors={fieldErrors}
                onNext={() => setStep(2)}
              />
            )}

            {step === 2 && (
              <StepNutrients
                waterOnly={waterOnly}
                setWaterOnly={setWaterOnly}
                rows={rows}
                setRow={setRow}
                addRow={addRow}
                removeRow={removeRow}
                kdInfo={kdInfo}
                onApplyFertilizer={applyFertilizer}
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
                climateRows={climateRows}
                setClimateRows={setClimateRows}
                hubKey={hubKey}
                setHubKey={setHubKey}
                hubScenario={hubScenario}
                setHubScenario={setHubScenario}
                hubAppDay={hubAppDay}
                setHubAppDay={setHubAppDay}
                uploadAppDay={uploadAppDay}
                setUploadAppDay={setUploadAppDay}
                analysisStart={analysisStart}
                setAnalysisStart={setAnalysisStart}
                analysisEnd={analysisEnd}
                setAnalysisEnd={setAnalysisEnd}
                printDays={printDays}
                setPrintDays={setPrintDays}
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
