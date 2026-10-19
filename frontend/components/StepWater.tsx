"use client";

import { useState } from "react";

type Props = {
  days: string;
  setDays: (v: string) => void;
  rainMode: "uniform" | "series";
  setRainMode: (v: "uniform" | "series") => void;
  rainMm: string;
  setRainMm: (v: string) => void;
  moisture: string;
  setMoisture: (v: string) => void;
  et0: string;
  setEt0: (v: string) => void;
  series: string;
  setSeries: (v: string) => void;
  et0Series: string;
  setEt0Series: (v: string) => void;
  error: string;
  fieldErrors: string[];
  onBack: () => void;
  onRun: () => void;
};

function normHeaderToken(t: string): string {
  return t
    .trim()
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

function parseNumberToken(raw: string, linha: number): number {
  const t = raw.trim().replace(",", ".");
  if (t === "") {
    throw new Error(`Linha ${linha}: valor vazio. Preencha todos os valores ou remova a linha.`);
  }
  const v = Number(t);
  if (!Number.isFinite(v) || v < 0) {
    throw new Error(`Linha ${linha}: valor inválido "${raw.trim()}". Use apenas números ≥ 0.`);
  }
  return v;
}

function splitLine(line: string, sep: ";" | "," | "ws"): string[] {
  if (sep === ";") return line.split(";");
  if (sep === ",") {
    const trimmed = line.trim();
    // Número único com vírgula decimal (ex: "12,5") — não dividir.
    if (/^-?\d+,\d+$/.test(trimmed)) return [trimmed];
    return line.split(",");
  }
  return line.split(/[\s\t]+/).filter((x) => x.length > 0);
}

export function parseDailyCsv(text: string): { rain: number[]; et0?: number[] } {
  const rawLines = text.split(/\r?\n/);
  const lines: string[] = [];
  const lineNos: number[] = [];
  rawLines.forEach((l, idx) => {
    const t = l.trim();
    if (t.length === 0 || t.startsWith("#")) return;
    lines.push(t);
    lineNos.push(idx + 1);
  });
  if (lines.length === 0) {
    throw new Error("Arquivo vazio ou sem dados válidos.");
  }
  // Detecta separador: ';' prevalece (permite vírgula decimal); senão ','; senão espaço.
  const hasSemi = lines.some((l) => l.includes(";"));
  const hasComma = lines.some((l) => l.includes(","));
  const sep: ";" | "," | "ws" = hasSemi ? ";" : hasComma ? "," : "ws";

  let startIdx = 0;
  let colKinds: ("day" | "rain" | "et0")[] | null = null;

  const firstTokens = splitLine(lines[0], sep).map((s) => s.trim());
  const isNumericToken = (t: string) => {
    const n = Number(t.trim().replace(",", "."));
    return t.trim() !== "" && Number.isFinite(n);
  };
  const firstHasLetter = firstTokens.some((t) => /[a-zA-Z]/.test(t) && !isNumericToken(t));
  if (firstHasLetter) {
    // Cabeçalho opcional: day/dia, chuva/rain, et0.
    const kinds = firstTokens.map((t) => {
      const n = normHeaderToken(t);
      if (n.includes("dia") || n === "day" || n === "d" || n.includes("data")) return "day" as const;
      if (n.includes("et0") || n.includes("eto") || n.includes("evapo")) return "et0" as const;
      if (n.includes("chuva") || n.includes("rain") || n.includes("prec") || n.includes("lamina") || n === "mm") return "rain" as const;
      return "unknown" as const;
    });
    // Mapeia desconhecidos por posição quando há cabeçalho parcial.
    const mapped: ("day" | "rain" | "et0")[] = [];
    let rainAssigned = false;
    for (const k of kinds) {
      if (k === "unknown") {
        if (!rainAssigned) {
          mapped.push("rain");
          rainAssigned = true;
        } else {
          mapped.push("et0");
        }
      } else {
        mapped.push(k);
        if (k === "rain") rainAssigned = true;
      }
    }
    colKinds = mapped;
    if (mapped.filter((k) => k === "rain").length > 1 || mapped.filter((k) => k === "et0").length > 1) {
      throw new Error("Cabeçalho ambíguo: mais de uma coluna chuva/rain ou ET0. Renomeie as colunas (dia, chuva, ET0).");
    }
    startIdx = 1;
    if (lines.length <= 1) {
      throw new Error("Arquivo contém apenas cabeçalho, sem dados diários.");
    }
  }

  const rain: number[] = [];
  const et0vals: number[] = [];
  let hasEt0Col = colKinds !== null && colKinds.includes("et0");
  let twoColAsDayRain: boolean | null = null;

  // Sem cabeçalho: infere pelo nº de colunas da 1ª linha de dados.
  let dataColCount = 0;
  if (colKinds === null) {
    dataColCount = splitLine(lines[0], sep).length;
    if (dataColCount < 1 || dataColCount > 3) {
      // Permite 1..3 colunas; mais que isso é erro.
      if (dataColCount > 3) {
        throw new Error(
          `Linha ${lineNos[0]}: esperadas 1 a 3 colunas (dia opcional, chuva, ET0 opcional), encontradas ${dataColCount}. Use separador "," ou ";" e vírgula decimal se necessário.`
        );
      }
    }
    if (dataColCount === 3) colKinds = ["day", "rain", "et0"];
    else if (dataColCount === 1) colKinds = ["rain"];
    else if (dataColCount === 2) {
      // Heurística: se a 1ª coluna for sequência 1..N (ou 0..N-1), é dia; senão é chuva+ET0.
      const firstCol: number[] = [];
      let seqOk = true;
      for (let li = 0; li < lines.length; li++) {
        const toks = splitLine(lines[li], sep);
        if (toks.length !== 2) {
          seqOk = false;
          break;
        }
        const a = Number(toks[0].trim().replace(",", "."));
        if (!Number.isFinite(a)) {
          seqOk = false;
          break;
        }
        firstCol.push(a);
      }
      if (seqOk) {
        const isSeq1 = firstCol.every((v, idx) => v === idx + 1);
        const isSeq0 = firstCol.every((v, idx) => v === idx);
        twoColAsDayRain = isSeq1 || isSeq0;
      } else {
        twoColAsDayRain = false;
      }
      colKinds = twoColAsDayRain ? ["day", "rain"] : ["rain", "et0"];
      if (!twoColAsDayRain) hasEt0Col = true;
    }
  } else {
    hasEt0Col = colKinds.includes("et0");
  }

  for (let li = startIdx; li < lines.length; li++) {
    const lineNo = lineNos[li];
    const toks = splitLine(lines[li], sep).map((s) => s.trim());
    if (colKinds && toks.length !== colKinds.length) {
      throw new Error(
        `Linha ${lineNo}: número de colunas inconsistente (esperadas ${colKinds.length}, encontradas ${toks.length}).`
      );
    }
    const kinds = colKinds!;
    let rainTok: string | null = null;
    let et0Tok: string | null = null;
    for (let c = 0; c < kinds.length; c++) {
      if (kinds[c] === "rain") rainTok = toks[c];
      if (kinds[c] === "et0") et0Tok = toks[c];
    }
    if (rainTok === null) {
      throw new Error(`Linha ${lineNo}: coluna de chuva não encontrada. Inclua uma coluna chuva/rain em mm.`);
    }
    rain.push(parseNumberToken(rainTok, lineNo));
    if (hasEt0Col && et0Tok !== null) {
      et0vals.push(parseNumberToken(et0Tok, lineNo));
    }
  }

  if (rain.length === 0) {
    throw new Error("Nenhum valor válido de chuva encontrado no arquivo.");
  }
  if (hasEt0Col) {
    return { rain, et0: et0vals };
  }
  return { rain };
}

export default function StepWater(props: Props) {
  const { days, setDays, rainMode, setRainMode, rainMm, setRainMm, moisture, setMoisture, et0, setEt0, series, setSeries, et0Series, setEt0Series, error, fieldErrors, onBack, onRun } = props;
  const [fileError, setFileError] = useState("");
  const [fileInfo, setFileInfo] = useState("");

  async function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    setFileError("");
    setFileInfo("");
    const f = e.target.files?.[0];
    if (!f) return;
    try {
      const text = await f.text();
      const parsed = parseDailyCsv(text);
      setSeries(parsed.rain.map((v) => String(v)).join("\n"));
      if (parsed.et0) {
        setEt0Series(parsed.et0.map((v) => String(v)).join("\n"));
        setFileInfo(`Arquivo "${f.name}" importado: ${parsed.rain.length} dias de chuva e ET0.`);
      } else {
        setEt0Series("");
        setFileInfo(`Arquivo "${f.name}" importado: ${parsed.rain.length} dias de chuva (sem ET0).`);
      }
      setRainMode("series");
    } catch (err) {
      setFileError(err instanceof Error ? err.message : String(err));
    } finally {
      e.target.value = "";
    }
  }

  return (
    <>
      <div className="form-row">
        <label className="field">Duração do Ensaio [dias]
          <input value={days} onChange={(e) => setDays(e.target.value)} />
        </label>
        <label className="field">Chuva
          <select value={rainMode} onChange={(e) => setRainMode(e.target.value as "uniform" | "series")}>
            <option value="uniform">Lâmina uniforme</option>
            <option value="series">Série diária</option>
          </select>
        </label>
        {rainMode === "uniform" && (
          <label className="field">Lâmina de Chuva / Irrigação [mm]
            <input value={rainMm} onChange={(e) => setRainMm(e.target.value)} />
          </label>
        )}
        <label className="field">Umidade Prévia do Solo [% do intervalo residual→CC]
          <input value={moisture} onChange={(e) => setMoisture(e.target.value)} />
        </label>
        <label className="field">ET0 - Evapotranspiração de referência [mm/dia]
          <input value={et0} onChange={(e) => setEt0(e.target.value)} />
        </label>
      </div>
      {rainMode === "series" && (
        <>
          <div className="form-row" style={{ marginTop: 12 }}>
            <label className="field" style={{ flex: "1 1 100%" }}>Série diária de chuva (mm, separados por espaço/vírgula/linha)
              <textarea rows={3} value={series} onChange={(e) => setSeries(e.target.value)} placeholder="0 0 12.5 0 3 ..." />
            </label>
          </div>
          <div className="form-row" style={{ marginTop: 8 }}>
            <label className="field">Importar CSV diário (sem Excel)
              <input type="file" accept=".csv,.txt" onChange={handleFile} />
            </label>
          </div>
          <p style={{ fontSize: 12, opacity: 0.8 }}>
            CSV com colunas dia/dia opcional, chuva/rain em mm e ET0 opcional; separador &ldquo;,&rdquo; ou &ldquo;;&rdquo;; vírgula decimal aceita; cabeçalho opcional.
          </p>
          {fileError && <p className="error-text">{fileError}</p>}
          {fileInfo && <p style={{ fontSize: 12 }}>{fileInfo}</p>}
        </>
      )}
      <div className="form-row" style={{ marginTop: 12 }}>
        <label className="field" style={{ flex: "1 1 100%" }}>Série diária de ET0, opcional (mm/dia)
          <textarea rows={2} value={et0Series} onChange={(e) => setEt0Series(e.target.value)} placeholder="4 4.1 3.8 ..." />
        </label>
      </div>
      {fieldErrors.length > 0 && (
        <ul className="error-text">
          {fieldErrors.map((m, i) => <li key={i}>{m}</li>)}
        </ul>
      )}
      {error && <p className="error-text">{error}</p>}
      <div className="btn-row">
        <button className="btn" onClick={onBack}>Voltar</button>
        <button className="btn btn-primary" onClick={onRun}>Calcular Resultados</button>
      </div>
    </>
  );
}
