import fs from "node:fs";
import path from "node:path";

export type Person = {
  name: string;
  role: string;
  org: string;
  evidence: string;
};
export type Edge = { src: string; rel: string; dst: string; evidence: string };

export type Profile = {
  slug: string;
  company_name: string;
  core_product: string;
  tech_stack: string[];
  likely_bottleneck: string;
  value_prop_pitch: string;
  is_relevant: boolean;
  funding_stage?: string;
  source_url: string;
  discovered_at: string;
  people: Person[];
  edges: Edge[];
};

export type GraphNode = {
  id: string;
  label: string;
  type: "startup" | "person" | "org";
  degree: number;
};
export type GraphEdge = {
  source: string;
  target: string;
  rel: string;
  evidence: string;
};
export type Graph = { nodes: GraphNode[]; edges: GraphEdge[] };

export type Funnel = {
  candidates: number;
  selected: number;
  crawled: number;
  extracted: number;
  relevant: number;
  valid: number;
};

export type RunSummary = {
  run_id: string;
  started_at: string;
  duration_s: number;
  passed: boolean;
  funnel: Funnel;
  tokens: number;
  sources: Record<string, number>;
  failures: string[];
};

export type Stage = {
  name: string;
  started_at: string;
  offset_s: number;
  duration_s: number;
  status: "ok" | "error";
  counts: Record<string, number>;
  notes: string[];
};

export type RunDetail = RunSummary & {
  plan: { web_queries?: string[]; hn_keywords?: string[] };
  stages: Stage[];
  source_health: Record<
    string,
    { candidates: number; seconds: number; error: string }
  >;
  usage: {
    prompt_tokens?: number;
    completion_tokens?: number;
    total_tokens?: number;
    calls?: number;
  };
  quality: Record<string, unknown>;
  accepted: {
    company: string;
    url: string;
    source: string;
    people: number;
    edges: number;
  }[];
  rejections: { url: string; source: string; reasons: string[] }[];
  errors: string[];
};

export const TOKEN_BUDGET = 200_000; // Groq free tier, tokens per day

// The backend workflow commits these files; the frontend reads them at build time (no API, no DB).
const DATA_DIR =
  process.env.CALI_DEMO === "1"
    ? path.join(process.cwd(), "demo-data")
    : path.join(process.cwd(), "..", "backend", "data");

function readJson<T>(...parts: string[]): T | null {
  try {
    return JSON.parse(
      fs.readFileSync(path.join(DATA_DIR, ...parts), "utf-8"),
    ) as T;
  } catch {
    return null;
  }
}

export const readMeta = () => readJson<{ demo?: boolean }>("meta.json");
export const readIndex = (): RunSummary[] =>
  readJson<{ runs: RunSummary[] }>("runs_index.json")?.runs ?? [];
export const readRun = (id: string) =>
  readJson<RunDetail>("runs", `${id}.json`);
export const readProfiles = (): Profile[] =>
  readJson<Profile[]>("profiles.json") ?? [];
export const readGraph = (): Graph =>
  readJson<Graph>("graph.json") ?? { nodes: [], edges: [] };
