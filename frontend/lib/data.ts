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
  /** review = a good lead a human should look at first (below the unattended-send bar, or no company address). */
  action: "contact_now" | "review" | "enrich_more" | "watch" | "skip" | "follow_up";
  urgency: "hot" | "warm" | "cold";
  priority: number;
  reasons: string[];
  next_step: string;
  provider: string;
  /** Signal-adjusted score the outreach quality gate compares to 70. */
  score?: number;
  /** p(worth pursuing) from the head learned on your own outcomes, once it exists. */
  lead_p?: number;
};
export type Outcome = {
  company: string;
  status: string;
  note: string;
  reason?: string;
  /** How their reply reads: interested | not_now | referral | question | unsubscribe | complaint | bounce | other */
  intent?: string;
  updated: string;
};
export type TimelineEvent = {
  at: string;
  kind: "discovered" | "learned" | "hiring" | "funding" | "launch" | "seeking_freelancer";
  items: string[];
  source_urls: string[];
  count: number;
};
export type Similar = { company_name: string; slug: string; similarity: number };

export type ContactItem = { value: string; kind: string; source_url: string };
export type Contact = {
  website?: string;
  emails?: ContactItem[];
  phones?: ContactItem[];
  socials?: Record<string, string>;
  contact_page?: string;
  /** Links on the company's own pages to try or read the product ("use it first"). */
  product_access?: { label: string; url: string }[];
  /** Website technology fingerprinted on the company's own pages (not the product's stack). */
  site_tech?: { name: string; category: string }[];
  status?: string;
  pages_crawled?: string[];
  enriched_at?: string;
  attempts?: number;
  last_attempt?: string;
};
export type Trackback = {
  entity_type: "startup" | "person" | "edge" | "contact";
  entity_key: string;
  field: string;
  label: string;
  value: string;
  source_url: string;
  evidence: string;
  run_id: string;
  first_seen: string;
  last_seen: string;
  seen_count: number;
  confidence: number;
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
  axes?: Record<string, number>;
  /** Known stage, a named leader and a published way in: worth pursuing now. */
  qualified?: boolean;
  similar?: Similar[];
  timeline?: TimelineEvent[];
  /** Why this matches data/watchlist.json ("company", "keyword: vector search"); empty when it does not. */
  watch?: string[];
  trackbacks?: Trackback[];
  last_seen?: string;
  warm_path?: { via: string; summary: string; hops: Edge[] } | null;
  outreach?: { kind: string; status: string; to: string; updated: string }[];
  email_draft?: {
    intent?: "work_for" | "build_for" | "build_with";
    intent_reason?: string;
    to: string;
    to_source_url: string;
    subject: string;
    body: string;
    mailto: string;
    /** Nothing concrete to say: never sent unattended; a human should rewrite it. */
    needs_human?: boolean;
    needs_human_reason?: string;
  };
  why_now?:{ signal: string; text: string; source_url: string }[];
  /** Hiring / launch / funding signals the scout recorded (backend/signals.py). */
  signals?: {
    type: "hiring" | "launch" | "funding" | "seeking_freelancer";
    source: string;
    url: string;
    roles: string[];
    role_kinds: string[];
    posted_at: string;
    seen_at: string;
  }[];
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
  sources?: {
    source_url: string;
    run_id: string;
    first_seen: string;
    last_seen: string;
  }[];
};
export type InvestorCluster = {
  investor: string;
  companies: string[];
  count: number;
  co_investors: { name: string; shared: number }[];
};
export type Graph = {
  nodes: GraphNode[];
  edges: GraphEdge[];
  investors?: InvestorCluster[];
};

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

export type TokenUsage = {
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
  calls?: number;
};

/** backend/quality.RunReport.to_dict(); every field optional because older runs lack some. */
export type RunQuality = {
  candidates?: number;
  crawled?: number;
  extracted?: number;
  relevant?: number;
  valid?: number;
  validity_rate?: number;
  qualified?: number;
  avg_score?: number;
  avg_qualified_score?: number;
  dropped_ungrounded?: number;
  gated?: number;
  enriched?: number;
  with_website?: number;
  with_email?: number;
  with_phone?: number;
  people?: number;
  people_linked?: number;
  issues?: Record<string, number>;
  deferred_urls?: string[];
};

export type OutreachSummary = {
  generated_at: string;
  queued: number;
  statuses: Record<string, number>;
  sent: number;
  replied: number;
  reply_rate: number;
  bounce_rate: number;
  reply_intents: Record<string, number>;
  by_day: Record<string, { sent: number; bounced: number; replied: number; complaint: number }>;
  paused: boolean;
  send_enabled: boolean;
  skip_reasons: Record<string, number>;
};

export type EnrichLastRun = {
  started_at: string;
  finished_at?: string;
  skipped: string;
  tokens?: number;
  quota_exhausted?: boolean;
  startups: { company: string; status: string; score: number; emails: number; website: string }[];
};

export type RunDetail = RunSummary & {
  plan: { web_queries?: string[]; hn_keywords?: string[] };
  stages: Stage[];
  source_health: Record<
    string,
    { candidates: number; seconds: number; error: string }
  >;
  usage: TokenUsage & {
    by_purpose?: Record<string, TokenUsage>;
    by_model?: Record<string, TokenUsage>;
    by_key?: Record<string, TokenUsage>;
    quota_hits?: { key: string; model: string; at: string; limit?: number; used?: number }[];
  };
  quality: RunQuality;
  /** What the run changed in the store (absent on runs recorded before 2026-11-06). */
  diff?: {
    added: { company: string; score: number; source: string }[];
    updated: { company: string; score: number; score_before: number; source: string }[];
  };
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

// The backend workflow commits these files; the frontend reads them at build time (no API, no DB).
const DATA_DIR =
  process.env.CALI_DEMO === "1"
    ? path.join(process.cwd(), "demo-data")
    : path.join(process.cwd(), "..", "backend", "data");

/** Files that exist but could not be parsed: shown as a banner, never silently treated as "no data". */
const CORRUPT = new Map<string, string>();

function readJson<T>(...parts: string[]): T | null {
  const file = path.join(DATA_DIR, ...parts);
  let raw: string;
  try {
    raw = fs.readFileSync(file, "utf-8");
  } catch {
    return null; // missing: a normal state (e.g. before the first run, or a local-only file)
  }
  try {
    CORRUPT.delete(parts.join("/"));
    return JSON.parse(raw) as T;
  } catch (e) {
    CORRUPT.set(parts.join("/"), e instanceof Error ? e.message : String(e));
    return null;
  }
}

export function readDataHealth(): { file: string; error: string }[] {
  // the core files every page relies on; read them so a corrupt one is reported wherever the banner renders
  for (const f of ["runs_index.json", "profiles.json", "graph.json"]) readJson(f);
  return [...CORRUPT.entries()].map(([file, error]) => ({ file, error }));
}

export const readMeta = () => readJson<{ demo?: boolean }>("meta.json");
export const readIndex = (): RunSummary[] =>
  readJson<{ runs: RunSummary[] }>("runs_index.json")?.runs ?? [];
export const readRun = (id: string) =>
  readJson<RunDetail>("runs", `${id}.json`);
export const readProfiles = (): Profile[] =>
  readJson<Profile[]>("profiles.json") ?? [];
/** Local-only (gitignored): present when the outreach agent runs on this machine. */
export const readOutreachState = () =>
  readJson<{ paused: boolean; reason: string; last_sent: string }>(
    "outreach_state.json",
  );
export const readGraph = (): Graph =>
  readJson<Graph>("graph.json") ?? { nodes: [], edges: [] };
/** Written by `outreach.py summary` on the sending machine (address-free); absent until outreach runs. */
export const readOutreachSummary = () =>
  readJson<OutreachSummary>("outreach_summary.json");
export const readOutcomes = (): Record<string, Outcome> =>
  readJson<Record<string, Outcome>>("outcomes.json") ?? {};
export const readEnrichLastRun = () =>
  readJson<EnrichLastRun>("enrich_last_run.json");
