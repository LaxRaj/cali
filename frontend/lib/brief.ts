import fs from "node:fs";
import path from "node:path";

export type Person = {
  name: string;
  role: string;
  org: string;
  evidence: string;
};
export type Edge = { src: string; rel: string; dst: string; evidence: string };

export type Finding = {
  source_url: string;
  source?: string;
  company_name: string;
  core_product: string;
  tech_stack: string[];
  likely_bottleneck: string;
  value_prop_pitch: string;
  is_relevant: boolean;
  funding_stage?: string;
  people?: Person[];
  edges?: Edge[];
};

export type Brief = {
  generated_at: string;
  findings: Finding[];
};

export type QualityReport = {
  candidates: number;
  crawled: number;
  relevant: number;
  valid: number;
  validity_rate: number;
  sources: Record<string, number>;
  people: number;
  edges: number;
  dropped_ungrounded: number;
  passed: boolean;
};

// The backend workflow commits these files; the frontend reads them at build time (no API).
const DATA_DIR = path.join(process.cwd(), "..", "backend", "data");

function readJson<T>(file: string): T | null {
  try {
    return JSON.parse(fs.readFileSync(path.join(DATA_DIR, file), "utf-8")) as T;
  } catch {
    return null;
  }
}

export const readBrief = () => readJson<Brief>("daily_brief.json");
export const readQuality = () => readJson<QualityReport>("quality_report.json");
