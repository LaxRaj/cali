import fs from "node:fs";
import path from "node:path";

export type Person = {
  name: string;
  role: string;
  org: string;
  evidence: string;
  linkedin?: string;
  twitter?: string;
  github?: string;
  homepage?: string;
  link_source?: string;
};

export type Decision = {
  action: "contact_now" | "enrich_more" | "watch" | "skip" | "follow_up";
  urgency: "hot" | "warm" | "cold";
  priority: number;
  reasons: string[];
  next_step: string;
  provider: string;
};
export type Outcome = {
  company: string;
  status: string;
  note: string;
  updated: string;
};

export type ContactItem = { value: string; kind: string; source_url: string };
export type Contact = {
  website?: string;
  emails?: ContactItem[];
  phones?: ContactItem[];
  socials?: Record<string, string>;
  contact_page?: string;
  status?: string;
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
  funding_amount?: string;
  hq?: string;
  website?: string;
  source_url: string;
  discovered_at: string;
  score?: number;
  score_parts?: Record<string, number>;
  gaps?: string[];
  email_draft?: {
    to: string;
    to_source_url: string;
    subject: string;
    body: string;
    mailto: string;
  };
  why_now?:{ signal: string; text: string; source_url: string }[];
  contact?: Contact;
  decision?: Decision;
  outcome?: Outcome | null;
  people: Person[];
  edges: Edge[];
};

export type GraphNode = {
  id: string;
  label: string;
  type: "startup" | "person" | "org";
  degree: number;
  website?: string;
  score?: number;
  role?: string;
  links?: Record<string, string>;
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

export type RunStatus = "passed" | "failed" | "quota";

export type RunSummary = {
  run_id: string;
  started_at: string;
  duration_s: number;
  passed: boolean;
  /** Absent on runs recorded before the backend wrote it; see runState() in lib/metrics.ts. */
  status?: RunStatus;
  funnel: Funnel;
  tokens: number;
  /** Tokens/day across all Groq keys when the run was recorded; absent on older runs. */
  token_budget?: number;
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
  decisions?: {
    provider: string;
    calls: number;
    fallbacks: number;
    avg_latency_ms: number;
    jev_input_tokens: number;
    gated_pages: number;
    tokens_saved_est: number;
  };
  feedback?: {
    source_stats?: Record<
      string,
      { crawled: number; accepted: number; yield: number; avg_score: number }
    >;
    caps?: Record<string, number>;
  };
  accepted: {
    company: string;
    url: string;
    source: string;
    people: number;
    edges: number;
    score?: number;
    gaps?: string[];
    website?: string;
    emails?: number;
    phones?: number;
  }[];
  rejections: { url: string; source: string; reasons: string[] }[];
  errors: string[];
};

export { TOKEN_BUDGET } from "./constants";

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
