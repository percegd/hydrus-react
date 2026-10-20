"use client";

import { useEffect, useRef, useState } from "react";
import LoadingOverlay from "../components/LoadingOverlay";
import Results from "../components/Results";
import StepIntro from "../components/StepIntro";
import StepNutrients, { DEFAULT_ROWS, NUTRIENT_SYMBOLS, blankCustomRow, defaultDispForDepth, type NutrientRow } from "../components/StepNutrients";
import StepSoil from "../components/StepSoil";
import StepWater, { emptyRows, type RainMode } from "../components/StepWater";
import WizardProgress from "../components/WizardProgress";
import { ApiError, getCrops, getExcelBlob, getGraphsBlob, getJob, getKd, getReport, getSoils, getSteps, postJob, postRosetta, type ClimateRow, type Crop, type SimulateResponse, type Soil } from "../lib/api";

const STEP_TITLES = [
  { title: "Apresentação", sub: "Visão geral da plataforma de simulação." },
  { title: "Passo 1 de 3: Qual o solo e as propriedades do perfil?", sub: "" },
  { title: "Passo 2 de 3: Água e solutos", sub: "" },
  { title: "Passo 3 de 3: Qual o regime hídrico aplicado?", sub: "" },
  { title: "Resultados da Modelagem Física 1D", sub: "Balanço de água e nutrientes consolidado com base na Equação de Richards e Advecção-Dispersão." },
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
  cropName: "Soja",
  cropKc: "1",
  cropH1: "-15",
  cropH2: "-30",
  cropH3: "-450",
  cropH4: "-12000",
  depthCm: "200",
  rootDepthCm: "35",
  days: "7",
  rainMode: "hub" as RainMode,
  rainMm: "60",
  moisture: "80",
  et0: "4.0",
  advEt: false,
  evap: "0",
  transp: "0",
  hubKey: "piracicaba_sp",
  hubScenario: "medio",
  hubAppDay: "30",
  uploadAppDay: "30",
  waterOnly: false,
  analysisStart: "1",
  analysisEnd: "365",
  printDays: "55, 128, 237, 365",
  rows: DEFAULT_ROWS,
  placement: "surface",
  releaseType: "immediate",
  releaseDays: "60",
  appDay: "0",
  zTop: "5",
  zBottom: "10",
  c0: "20",
  pulse: "7",
  fertContinuous: false,
};

function RestartIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" />
      <path d="M21 3v5h-5" />
      <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" />
      <path d="M8 16H3v5" />
    </svg>
  );
}

function ValidationModal({ issues, onClose }: { issues: string[]; onClose: () => void }) {
  return (
    <div className="modal-overlay" role="alertdialog" aria-modal="true" aria-labelledby="validation-title">
      <div className="modal-card validation-modal-card">
        <div className="validation-modal-head">
          <div className="validation-modal-icon">⚠</div>
          <div>
            <h3 className="validation-modal-title" id="validation-title">Verifique os campos destacados</h3>
            <p className="validation-modal-sub">
              {issues.length} campo(s) com formato inválido ou valor fisicamente impossível.
            </p>
          </div>
        </div>
        <div className="validation-issue-list">
          {issues.map((m, i) => {
            const sep = m.indexOf(":");
            const head = sep > 0 ? m.slice(0, sep).trim() : "Campo";
            const body = sep > 0 ? m.slice(sep + 1).trim() : m;
            return (
              <div className="validation-issue" key={i}>
                <span className="validation-issue-num">{i + 1}</span>
                <div className="validation-issue-body">
                  <b>{head}</b>
                  <p>{body}</p>
                </div>
              </div>
            );
          })}
        </div>
        <div className="modal-actions">
          <button className="btn-modal-confirm" style={{ width: "100%" }} onClick={onClose} autoFocus>
            Entendi, vou corrigir
          </button>
        </div>
      </div>
    </div>
  );
}

function RestartModal({ onCancel, onConfirm }: { onCancel: () => void; onConfirm: () => void }) {
  return (
    <div className="modal-overlay" role="alertdialog" aria-modal="true" aria-labelledby="restart-title">
      <div className="modal-card">
        <div className="modal-head">
          <div className="modal-icon-refresh"><RestartIcon /></div>
          <div style={{ flex: 1 }}>
            <h3 className="modal-title" id="restart-title">Iniciar Nova Simulação?</h3>
            <p className="modal-sub">
              Você retornará à tela de apresentação. Os dados da última simulação continuarão preenchidos para você ajustar; os resultados atuais serão substituídos ao calcular de novo.
            </p>
          </div>
        </div>
        <div className="modal-actions">
          <button className="btn-modal-cancel" onClick={onCancel}>Cancelar</button>
          <button className="btn-modal-confirm" onClick={onConfirm} autoFocus>Confirmar e Reiniciar</button>
        </div>
      </div>
    </div>
  );
}

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
  const [cropName, setCropName] = useState(DEFAULTS.cropName);
  const [cropKc, setCropKc] = useState(DEFAULTS.cropKc);
  const [cropH1, setCropH1] = useState(DEFAULTS.cropH1);
  const [cropH2, setCropH2] = useState(DEFAULTS.cropH2);
  const [cropH3, setCropH3] = useState(DEFAULTS.cropH3);
  const [cropH4, setCropH4] = useState(DEFAULTS.cropH4);
  const [depthCm, setDepthCm] = useState(DEFAULTS.depthCm);
  const [rootDepthCm, setRootDepthCm] = useState(DEFAULTS.rootDepthCm);
  const [days, setDays] = useState(DEFAULTS.days);
  const [rainMode, setRainMode] = useState<RainMode>(DEFAULTS.rainMode);
  const [rainMm, setRainMm] = useState(DEFAULTS.rainMm);
  const [moisture, setMoisture] = useState(DEFAULTS.moisture);
  const [et0, setEt0] = useState(DEFAULTS.et0);
  const [advEt, setAdvEt] = useState(DEFAULTS.advEt);
  const [evap, setEvap] = useState(DEFAULTS.evap);
  const [transp, setTransp] = useState(DEFAULTS.transp);
  const [climateRows, setClimateRows] = useState<ClimateRow[]>(() => emptyRows(365));
  const [hubKey, setHubKey] = useState(DEFAULTS.hubKey);
  const [hubLabel, setHubLabel] = useState("");
  const [hubScenario, setHubScenario] = useState(DEFAULTS.hubScenario);
  const [hubAppDay, setHubAppDay] = useState(DEFAULTS.hubAppDay);
  const [uploadAppDay, setUploadAppDay] = useState(DEFAULTS.uploadAppDay);
  const [waterOnly, setWaterOnly] = useState(DEFAULTS.waterOnly);
  const [analysisStart, setAnalysisStart] = useState(DEFAULTS.analysisStart);
  const [analysisEnd, setAnalysisEnd] = useState(DEFAULTS.analysisEnd);
  const [printDays, setPrintDays] = useState(DEFAULTS.printDays);
  const [rows, setRows] = useState<NutrientRow[]>(DEFAULTS.rows.map((r) => ({ ...r })));
  const [releaseType, setReleaseType] = useState(DEFAULTS.releaseType);
  const [releaseDays, setReleaseDays] = useState(DEFAULTS.releaseDays);
  const [placement, setPlacement] = useState(DEFAULTS.placement);
  const [appDay, setAppDay] = useState(DEFAULTS.appDay);
  const [zTop, setZTop] = useState(DEFAULTS.zTop);
  const [zBottom, setZBottom] = useState(DEFAULTS.zBottom);
  const [c0, setC0] = useState(DEFAULTS.c0);
  const [pulse, setPulse] = useState(DEFAULTS.pulse);
  const [fertContinuous, setFertContinuous] = useState(DEFAULTS.fertContinuous);
  const [lastFert, setLastFert] = useState<{ fert_key: string; gross_dose: number; doses: Record<string, number> } | null>(null);
  const [jobId, setJobId] = useState("");
  const [jobState, setJobState] = useState("");
  const [elapsed, setElapsed] = useState(0);
  const [validationIssues, setValidationIssues] = useState<string[] | null>(null);
  const [restartOpen, setRestartOpen] = useState(false);
  const [result, setResult] = useState<SimulateResponse | null>(null);
  const [report, setReport] = useState("");
  const [steps, setSteps] = useState("");
  const [appliedMm, setAppliedMm] = useState<number | null>(null);
  const pollAbort = useRef<AbortController | null>(null);
  const pollCancelled = useRef(false);
  const elapsedTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const safetyTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [overlayTimedOut, setOverlayTimedOut] = useState(false);

  function stopPolling() {
    pollCancelled.current = true;
    if (pollAbort.current) {
      try { pollAbort.current.abort(); } catch { /* ignore */ }
      pollAbort.current = null;
    }
    if (elapsedTimer.current) {
      clearInterval(elapsedTimer.current);
      elapsedTimer.current = null;
    }
    if (safetyTimer.current) {
      clearTimeout(safetyTimer.current);
      safetyTimer.current = null;
    }
  }

  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  }, [step]);

  useEffect(() => {
    getSoils().then(setSoils).catch(() => setValidationIssues(["API fora do ar (backend :8001)."]));
    getCrops().then((cs) => {
      setCrops(cs);
      // Prefill cultura selecionada (Gradio: nome + raiz + Kc + Feddes da cultura).
      const found = cs.find((c) => c.key === crop);
      if (found) {
        fillCropParams(found);
      }
    }).catch(() => {});
    return () => { stopPolling(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function fillCropParams(c: Crop) {
    setCropName(c.name);
    setRootDepthCm(String(c.root_depth_cm));
    setCropKc(String(c.kc));
    setCropH1(String(c.h1));
    setCropH2(String(c.h2));
    setCropH3(String(c.h3));
    setCropH4(String(c.h4));
  }

  function setCropMode(mode: string) {
    setCropModeState(mode);
    if (mode === "com") {
      const found = crops.find((c) => c.key === crop);
      if (found) fillCropParams(found);
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
          setRosettaNote(`Silte: ${r.silt_pct}% • Classe: ${r.texture} • Areia (${sand}%) + Argila (${clay}%) + Silte (${r.silt_pct})% = 100%`);
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
        // Igual ao Gradio: ao trocar o solo, o Kd sempre volta ao valor de literatura.
        // Linhas "Outro soluto" não têm literatura (Kd 0.20 de traçador) — preservadas.
        if (row.custom) return row;
        const lit = info[row.symbol];
        if (!lit) return row;
        return { ...row, kd: lit.kd, kdSource: lit.citation, kdEdited: false };
      }));
    }).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [soil, isCustomSoil, sandPct, clayPct]);

  function applyFertilizer(doses: Record<string, number>, fertKey?: string, grossDose?: number) {
    // Paridade Gradio (apply_commercial_fertilizer): 6 linhas fixas recebem
    // dose = round(bruta × teor%/100, 1), ativa se > 0; Kd de literatura do
    // solo atual, dispersividade padrão (0,1 × profundidade), residual "0".
    // Linhas "Outro soluto" (custom) não mudam.
    const dispDefault = defaultDispForDepth(depthCm);
    setRows((rs) => rs.map((r) => {
      if (r.custom) return r;
      const dose = doses[r.symbol] ?? 0;
      const rounded = String(Math.round(dose * 10) / 10);
      const lit = kdInfo[r.symbol];
      return {
        ...r,
        active: dose > 0,
        dose: rounded,
        kd: lit?.kd ?? r.kd,
        kdEdited: false,
        kdSource: lit?.citation ?? "",
        disp: dispDefault,
        res: "0",
      };
    }));
    // D) guarda origem comercial p/ a Etapa 1 do passo a passo (só vale se a
    // tabela não for editada depois — verificado em run()).
    if (fertKey && grossDose !== undefined && Number.isFinite(grossDose)) {
      const rounded: Record<string, number> = {};
      for (const sym of NUTRIENT_SYMBOLS) {
        rounded[sym] = Math.round(((doses as Record<string, number>)[sym] ?? 0) * 10) / 10;
      }
      setLastFert({ fert_key: fertKey, gross_dose: grossDose, doses: rounded });
    } else {
      setLastFert(null);
    }
  }

  function handleCropSelect(key: string) {
    setCrop(key);
    const found = crops.find((c) => c.key === key);
    if (found) fillCropParams(found);
  }

  function openValidation(issues: string[]) {
    setValidationIssues(issues.length > 0 ? issues : ["Erro desconhecido."]);
  }

  function showApiError(e: unknown) {
    if (e instanceof ApiError && e.details.length > 0) {
      openValidation(e.details);
    } else {
      openValidation([String(e instanceof Error ? e.message : e)]);
    }
  }
  function setRow(i: number, patch: Partial<NutrientRow>) {
    setRows((rs) => rs.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  }
  function addRow() {
    // Só adiciona linhas "Outro soluto" (as 6 fixas sempre existem).
    setRows((rs) => [...rs, blankCustomRow(defaultDispForDepth(depthCm))]);
  }
  function removeRow(i: number) {
    setRows((rs) => {
      if (!rs[i]?.custom) return rs;
      if (rs.filter((r) => r.custom).length <= 1) return rs;
      return rs.filter((_, j) => j !== i);
    });
  }

  function num(x: string, def: number): number {
    const v = parseFloat(String(x).replace(",", "."));
    return Number.isNaN(v) ? def : v;
  }

  function numOrNull(x: string): number | null {
    const t = String(x ?? "").trim().replace(",", ".");
    if (!t) return null;
    const v = parseFloat(t);
    return Number.isNaN(v) ? null : v;
  }

  function startNewSimulation() {
    stopPolling();
    setJobId("");
    setJobState("");
    setElapsed(0);
    setOverlayTimedOut(false);
    setValidationIssues(null);
    setResult(null);
    setReport("");
    setSteps("");
    setAppliedMm(null);
    setRestartOpen(false);
    setStep(0);
  }

  async function run() {
    stopPolling();
    setValidationIssues(null);
    setResult(null);
    setReport("");
    setSteps("");
    setAppliedMm(null);
    let rain_series: number[] | undefined;
    let total_days = num(days, 7);
    let et0_series: number[] | undefined;
    let appDayEff = appDay;
    try {
      if (rainMode === "hub" || rainMode === "upload") {
        if (!climateRows.length) { openValidation(["Tabela de série diária: a tabela de série diária está vazia. Preencha a coluna de chuva (mm)."]); return; }
        rain_series = climateRows.map((r) => {
          if (!Number.isFinite(r.rain_mm) || r.rain_mm < 0) throw new Error("Série inválida (só números ≥ 0).");
          return r.rain_mm;
        });
        et0_series = climateRows.map((r) => {
          if (!Number.isFinite(r.et0_mm) || r.et0_mm < 0) throw new Error("Série inválida (só números ≥ 0).");
          return r.et0_mm;
        });
        if (!rain_series.some((v) => v > 0)) { openValidation(["Tabela de série diária: a tabela de série diária está vazia. Preencha a coluna de chuva (mm)."]); return; }
        total_days = rain_series.length;
        appDayEff = rainMode === "hub" ? hubAppDay : uploadAppDay;
      }
    } catch (e) { openValidation([String((e as Error).message || e)]); return; }
    const depthVal = num(depthCm, 200);
    const dispDefault = depthVal / 10;
    const relType = releaseType === "controlled" ? "controlled" : "immediate";
    const relDays = num(releaseDays, 60);
    const unnamedCustom = !waterOnly && rows.some((r) => r.custom && r.active && !String(r.name).trim());
    if (unnamedCustom) { openValidation(["Outro soluto: informe o nome/símbolo da espécie (ex: Br⁻, Cl⁻, Atrazina) ou desmarque a linha."]); return; }
    const solutes = waterOnly ? [] : rows
      .filter((r) => r.active)
      .map((r) => {
        const sym = r.custom ? String(r.name).trim() : r.symbol;
        const nm = r.custom ? String(r.name).trim() : r.name;
        const dispNum = num(r.disp, dispDefault);
        return {
          symbol: sym, name: nm, dose_kg_ha: parseFloat(String(r.dose).replace(",", ".")), kd: num(r.kd, 0),
          dispersivity_cm: dispNum > 0 ? dispNum : dispDefault,
          initial_residual_mg_dm3: r.res === "" ? 0 : num(r.res, 0),
          release_type: relType, release_days: relDays,
        };
      })
      .filter((s) => s.symbol && s.dose_kg_ha > 0);
    if (!waterOnly && !solutes.length) { openValidation(["Modo de simulação: modo 'Água + nutrientes' exige ao menos um soluto com dose > 0. Marque um nutriente ou troque para 'Somente água'."]); return; }
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
      } catch (e) { openValidation([String((e as Error).message || e)]); return; }
    }
    const appliedTotal = rain_series ? rain_series.reduce((a, b) => a + b, 0) : num(rainMm, 0);
    setAppliedMm(appliedTotal);
    // Permanece no Passo 3 com overlay de tela cheia até o job concluir.
    setOverlayTimedOut(false);
    setJobState("queued");
    // Timeout de segurança (paridade Gradio): após 300 s remove o overlay;
    // o polling continua e o resultado aparece normalmente se concluir depois.
    if (safetyTimer.current) clearTimeout(safetyTimer.current);
    safetyTimer.current = setTimeout(() => {
      setOverlayTimedOut(true);
      safetyTimer.current = null;
    }, 300000);
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
    // D) só envia a origem comercial se a tabela fixa não foi editada depois
    // do modal: p/ cada linha fixa, (ativa e dose == doses[sym]) ou
    // (inativa e doses[sym] == 0).
    let fertilizer: { fert_key: string; gross_dose: number } | undefined;
    if (lastFert) {
      const ok = NUTRIENT_SYMBOLS.every((sym) => {
        const row = rows.find((r) => !r.custom && r.symbol === sym);
        const expected = lastFert.doses[sym] ?? 0;
        if (!row) return expected === 0;
        const cur = parseFloat(String(row.dose).replace(",", "."));
        const curNum = Number.isFinite(cur) ? cur : NaN;
        if (row.active) {
          return Number.isFinite(curNum) && Math.abs(curNum - expected) < 1e-9;
        }
        return Math.abs(expected) < 1e-9;
      });
      if (ok) fertilizer = { fert_key: lastFert.fert_key, gross_dose: lastFert.gross_dose };
    }
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
        crop_name: isCom ? (cropName.trim() || null) : null,
        kc: isCom ? numOrNull(cropKc) : null,
        h1: isCom ? numOrNull(cropH1) : null,
        h2: isCom ? numOrNull(cropH2) : null,
        h3: isCom ? numOrNull(cropH3) : null,
        h4: isCom ? numOrNull(cropH4) : null,
        depth_cm: depthVal,
        root_depth_cm: isCom ? num(rootDepthCm, rootFallback) : null,
        total_days,
        rain_mm: num(rainMm, 0), rain_series,
        initial_moisture_pct: num(moisture, 80),
        et0_mm_day: num(et0, 0), et0_series,
        evap_mm_day: rainMode === "uniform" && advEt ? num(evap, 0) : 0,
        transp_mm_day: rainMode === "uniform" && advEt && isCom ? num(transp, 0) : 0,
        solutes,
        water_only: waterOnly,
        analysis_start_day,
        analysis_end_day,
        print_days,
        // Paridade Gradio (laudo sazonal): fonte da série p/ o laudo.
        // hub -> rótulo exato do seletor + " (NASA POWER)"; upload -> planilha
        // do usuário; lâmina -> não envia (backend usa o default do polo).
        ...(rainMode === "hub"
          ? { series_source_label: `Série climática do polo — ${hubLabel || hubKey} (NASA POWER)` }
          : rainMode === "upload"
            ? { series_source_label: "Planilha climática importada pelo usuário (série diária)" }
            : {}),
        placement: {
          mode: placement, z_top_cm: z_top, z_bottom_cm: z_bottom,
          fertigation_c0_mg_l: num(c0, 20),
          fertigation_pulse_days: fertContinuous ? 0 : num(pulse, 7),
          application_day: num(appDayEff, 0),
        },
        ...(fertilizer ? { fertilizer } : {}),
      };
      const { job_id } = await postJob(body);
      setJobId(job_id);
      setJobState("running");
      // Long-poll sequencial: próxima chamada (wait=25) logo após a anterior
      // retornar — sem sobreposição (sem setInterval). Mantém 1 requisição
      // aberta para o Cloud Run alocar CPU enquanto o job roda.
      pollCancelled.current = false;
      const ctrl = new AbortController();
      pollAbort.current = ctrl;
      const t0 = Date.now();
      setElapsed(0);
      if (elapsedTimer.current) clearInterval(elapsedTimer.current);
      elapsedTimer.current = setInterval(() => {
        if (pollCancelled.current) return;
        setElapsed(Math.round(((Date.now() - t0) / 1000) * 10) / 10);
      }, 500);
      let pollErrors = 0;
      try {
        for (;;) {
          if (pollCancelled.current) return;
          let st;
          try {
            st = await getJob(job_id, 25, ctrl.signal);
          } catch (e) {
            if (pollCancelled.current) return;
            if (e instanceof DOMException && e.name === "AbortError") return;
            if (e instanceof ApiError && (e.status === 404 || e.status === 410)) {
              stopPolling();
              setJobState("expired");
              openValidation(["A simulação expirou; rode novamente."]);
              return;
            }
            pollErrors += 1;
            if (pollErrors >= 5) {
              stopPolling();
              setJobState("failed");
              openValidation([e instanceof Error ? e.message : String(e)]);
              return;
            }
            continue;
          }
          if (pollCancelled.current) return;
          pollErrors = 0;
          setElapsed(st.elapsed_s);
          if (st.status === "done") {
            stopPolling();
            setElapsed(st.elapsed_s);
            setJobState("done");
            setResult(st.result);
            setStep(4);
            return;
          } else if (st.status === "failed") {
            stopPolling();
            setJobState("failed");
            openValidation([st.error || "Falha na simulação."]);
            return;
          } else {
            setJobState(st.status);
          }
        }
      } catch (e) {
        if (!pollCancelled.current) {
          stopPolling();
          setJobState("failed");
          showApiError(e);
        }
      }
    } catch (e) {
      stopPolling();
      setJobState("failed");
      showApiError(e);
    }
  }

  async function loadReport() {
    try {
      const markdown = await getReport(jobId);
      setReport(markdown);
    } catch (e) {
      if (e instanceof ApiError && (e.status === 404 || e.status === 410)) {
        openValidation(["Job expirado; rode a simulação novamente."]);
        return;
      }
      showApiError(e);
    }
  }

  async function loadSteps() {
    try {
      const markdown = await getSteps(jobId);
      setSteps(markdown);
    } catch (e) {
      if (e instanceof ApiError && (e.status === 404 || e.status === 410)) {
        openValidation(["Job expirado; rode a simulação novamente."]);
        return;
      }
      showApiError(e);
    }
  }

  async function downloadExcel() {
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
        openValidation(["Job expirado; rode a simulação novamente."]);
        return;
      }
      showApiError(e);
    }
  }

  async function downloadGraphs() {
    try {
      const blob = await getGraphsBlob(jobId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `graficos_${jobId}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      if (e instanceof ApiError && (e.status === 404 || e.status === 410)) {
        openValidation(["Job expirado; rode a simulação novamente."]);
        return;
      }
      showApiError(e);
    }
  }

  const isCom = cropMode === "com";
  const cropEntry = crops.find((c) => c.key === crop);
  const rootDepth = isCom ? num(rootDepthCm, cropEntry?.root_depth_cm ?? 35) : num(depthCm, 200);
  const cropLabel = isCom ? (cropName.trim() || cropEntry?.name || crop) : "Sem cultura";
  const resultsWaterOnly = result ? (result.water_only || !result.solutes?.length) : waterOnly;
  const headerTitle = step === 4 && resultsWaterOnly
    ? "Resultados da Modelagem Física 1D — Fluxo de Água"
    : STEP_TITLES[step].title;
  const headerSub = step === 4 && resultsWaterOnly
    ? "Balanço hídrico do perfil resolvido pela Equação de Richards acoplada à evaporação do solo e à absorção radicular (Feddes, quando há cultura)."
    : STEP_TITLES[step].sub;
  const running = jobState === "queued" || jobState === "running";
  const showOverlay = running && !overlayTimedOut;

  // Bloqueia o scroll do body enquanto o overlay de tela cheia está aberto.
  useEffect(() => {
    if (!showOverlay) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [showOverlay]);
  const soluteMeta = Object.fromEntries(rows.map((r) => {
    const sym = r.custom ? String(r.name).trim() : r.symbol;
    return [sym, { kd: r.kd, residual: r.res }];
  }));

  return (
    <div className="hydrus-container">
      <header className="app-header">
        <div className="header-logos">
          <img src="/ppg_header.png" alt="PPG Engenharia de Sistemas Agrícolas" className="header-logo-img" />
          <img src="/gpeas_header.png" alt="GPEAS" className="header-logo-img" />
        </div>
        <p className="app-subtitle">Simulação de transporte de água e nutrientes no perfil do solo</p>
      </header>

      <WizardProgress current={step} />

      <div className="wizard-step-box">
        {step === 0 ? (
          <StepIntro />
        ) : (
          <>
            <div className="wizard-question-header">
              <h2 className="wizard-question-title">{headerTitle}</h2>
              {headerSub && (
                <p className="wizard-question-subtitle">{headerSub}</p>
              )}
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
                cropName={cropName}
                setCropName={setCropName}
                cropKc={cropKc}
                setCropKc={setCropKc}
                cropH1={cropH1}
                setCropH1={setCropH1}
                cropH2={cropH2}
                setCropH2={setCropH2}
                cropH3={cropH3}
                setCropH3={setCropH3}
                cropH4={cropH4}
                setCropH4={setCropH4}
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
                releaseType={releaseType}
                setReleaseType={setReleaseType}
                releaseDays={releaseDays}
                setReleaseDays={setReleaseDays}
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
                hasCrop={isCom}
                cropKc={cropKc}
                advEt={advEt}
                setAdvEt={setAdvEt}
                evap={evap}
                setEvap={setEvap}
                transp={transp}
                setTransp={setTransp}
                climateRows={climateRows}
                setClimateRows={setClimateRows}
                hubKey={hubKey}
                setHubKey={setHubKey}
                hubLabel={hubLabel}
                setHubLabel={setHubLabel}
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
              />
            )}

            {step === 4 && (
              <Results
                jobState={jobState}
                elapsed={elapsed}
                jobId={jobId}
                result={result}
                report={report}
                steps={steps}
                cropName={cropLabel}
                rootDepth={rootDepth}
                appliedMm={appliedMm}
                hasCrop={isCom}
                soluteMeta={soluteMeta}
                onDownloadExcel={downloadExcel}
                onDownloadGraphs={downloadGraphs}
                onLoadReport={loadReport}
                onLoadSteps={loadSteps}
              />
            )}
          </>
        )}
      </div>

      <div className="wizard-nav-row">
        {step === 0 && (
          <button className="btn-wizard-next" onClick={() => setStep(1)}>
            Iniciar simulação
          </button>
        )}
        {(step === 1 || step === 2) && (
          <>
            <button className="btn-wizard-back" onClick={() => setStep(step - 1)}>
              Voltar
            </button>
            <button className="btn-wizard-next" onClick={() => setStep(step + 1)}>
              Avançar
            </button>
          </>
        )}
        {step === 3 && (
          <>
            <button className="btn-wizard-back" onClick={() => setStep(2)}>
              Voltar
            </button>
            <button className={`btn-wizard-next${running ? " is-loading" : ""}`} onClick={run} disabled={running}>
              Calcular Resultados
            </button>
          </>
        )}
        {step === 4 && (
          <button className="btn-wizard-next" onClick={() => setRestartOpen(true)}>
            Nova Simulação
          </button>
        )}
      </div>

      {validationIssues && (
        <ValidationModal issues={validationIssues} onClose={() => setValidationIssues(null)} />
      )}
      {restartOpen && (
        <RestartModal onCancel={() => setRestartOpen(false)} onConfirm={startNewSimulation} />
      )}
      {showOverlay && <LoadingOverlay />}
    </div>
  );
}
