import fs from "node:fs";
import path from "node:path";

export type Finding = {
  source_url: string;
  company_name: string;
  core_product: string;
  tech_stack: string[];
  likely_bottleneck: string;
  value_prop_pitch: string;
  is_relevant: boolean;
};

export type Brief = {
  generated_at: string;
  findings: Finding[];
};

// The backend workflow commits this file; the frontend reads it at build time (no API).
const BRIEF_PATH = path.join(process.cwd(), "..", "backend", "data", "daily_brief.json");

export function readBrief(): Brief | null {
  try {
    return JSON.parse(fs.readFileSync(BRIEF_PATH, "utf-8")) as Brief;
  } catch {
    return null;
  }
}
