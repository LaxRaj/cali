// Every number the dashboard shows about runs, tokens and findings is computed here, once.
// Pure functions over the committed JSON: no I/O, no clock (callers pass `now`).
// Definitions (keep scripts/check-dashboard.ts and the dashboard-logic-check skill in step):
//  - a "day" is a UTC calendar day: the Groq quota resets at 00:00 UTC
//  - "tokens today" is the SUM over every run that started on that day
//  - a run is passed | failed | quota; quota (Groq limit hit) is not a quality failure

import { RECORDS_START, TOKEN_BUDGET } from "./constants";
import type { Profile, RunStatus, RunSummary } from "./data"; // types only: data.ts is server-only

/** The scout runs daily; anything older than a day plus slack means the data is stale. */
export const STALE_AFTER_HOURS = 26;

export function dayKey(iso: string): string {
  return new Date(iso).toISOString().slice(0, 10);
}

export function latestRun(runs: RunSummary[]): RunSummary | undefined {
  return runs.reduce<RunSummary | undefined>(
    (best, r) => (!best || r.run_id > best.run_id ? r : best),
    undefined,
  );
}

export function runState(run: RunSummary): RunStatus {
  if (run.status) return run.status;
  if (run.passed) return "passed";
  // Older entries: a run that crawled but extracted nothing because the quota was spent
  // fails every gate with next to no tokens used.
  const noWork = run.failures.some((f) => f.startsWith("only 0 valid"));
  return noWork && run.tokens < 5_000 ? "quota" : "failed";
}

export function runsOnDay(runs: RunSummary[], day: string): RunSummary[] {
  return runs.filter((r) => dayKey(r.started_at) === day);
}

export function dailyTokens(runs: RunSummary[], day: string): number {
  return runsOnDay(runs, day).reduce((t, r) => t + r.tokens, 0);
}

export function dailyBudget(runs: RunSummary[], day: string): number {
  const recorded = runsOnDay(runs, day).map((r) => r.token_budget ?? 0);
  return Math.max(TOKEN_BUDGET, ...recorded);
}

export type DayTotal = {
  day: string;
  tokens: number;
  budget: number;
  runs: number;
  passed: number;
  failed: number;
  quota: number;
  /** Valid startups found that day (sum of funnel.valid over its runs). */
  valid: number;
  /** tokens ÷ valid, rounded; null when nothing valid was found (no divide-by-zero). */
  tokensPerValid: number | null;
};

/** One entry per UTC day that has runs, oldest first. */
export function dailyTotals(runs: RunSummary[]): DayTotal[] {
  const days = [...new Set(runs.map((r) => dayKey(r.started_at)))].sort();
  return days.map((day) => {
    const of = runsOnDay(runs, day);
    const count = (s: RunStatus) => of.filter((r) => runState(r) === s).length;
    const tokens = dailyTokens(runs, day);
    const valid = of.reduce((t, r) => t + (r.funnel?.valid ?? 0), 0);
    return {
      day,
      tokens,
      budget: dailyBudget(runs, day),
      runs: of.length,
      passed: count("passed"),
      failed: count("failed"),
      quota: count("quota"),
      valid,
      tokensPerValid: valid ? Math.round(tokens / valid) : null,
    };
  });
}

export type PassRate = {
  /** passed / (passed + failed), whole percent; null when no run counts. */
  pct: number | null;
  passed: number;
  failed: number;
  /** Quota-limited runs, left out of the rate. */
  skipped: number;
};

export function passRate(runs: RunSummary[], window = 30): PassRate {
  const recent = [...runs]
    .sort((a, b) => a.run_id.localeCompare(b.run_id))
    .slice(-window);
  const states = recent.map(runState);
  const passed = states.filter((s) => s === "passed").length;
  const failed = states.filter((s) => s === "failed").length;
  const skipped = states.length - passed - failed;
  return {
    pct: passed + failed ? Math.round((passed / (passed + failed)) * 100) : null,
    passed,
    failed,
    skipped,
  };
}

export function latestFindings(profiles: Profile[], n: number): Profile[] {
  return [...profiles]
    .sort((a, b) => b.discovered_at.localeCompare(a.discovered_at))
    .slice(0, n);
}

export function topFindings(profiles: Profile[], n: number): Profile[] {
  return [...profiles]
    .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
    .slice(0, n);
}

/** Runs sorted by run_id (oldest first), whatever order the index file has. */
export function sortedRuns(runs: RunSummary[]): RunSummary[] {
  return [...runs].sort((a, b) => a.run_id.localeCompare(b.run_id));
}

export type FunnelStep = {
  stage: string;
  count: number;
  /** Share of the previous step, whole percent; null for the first step or when the previous is 0. */
  conversion: number | null;
};

/**
 * Outreach funnel from what you recorded (backend/outcomes.py, mirrored by the outreach agent):
 * ready to send (contact_now with an address) -> contacted -> replied -> meeting -> won. Each later status counts
 * toward every earlier step (a meeting was also a reply and a contact). `passed` leads are counted separately.
 */
export function outreachFunnel(
  profiles: Profile[],
  outcomes: Record<string, { status: string }>,
): { steps: FunnelStep[]; passed: number } {
  const order = ["contacted", "replied", "meeting", "won"];
  const rank = (s: string) => order.indexOf(s);
  const statuses = Object.values(outcomes).map((o) => o.status);
  const atLeast = (s: string) => statuses.filter((x) => rank(x) >= rank(s)).length;
  const ready = profiles.filter(
    (p) => p.decision?.action === "contact_now" && p.email_draft?.to,
  ).length;
  const counts: [string, number][] = [
    ["ready to send", ready],
    ["contacted", atLeast("contacted")],
    ["replied", atLeast("replied")],
    ["meeting", atLeast("meeting")],
    ["won", atLeast("won")],
  ];
  const steps = counts.map(([stage, count], i) => {
    const prev = i > 0 ? counts[i - 1][1] : 0;
    // "ready" is a pool, not the step before contacted: only rate the outreach steps against each other
    const conversion = i >= 2 && prev > 0 ? Math.round((count / prev) * 100) : null;
    return { stage, count, conversion };
  });
  return { steps, passed: statuses.filter((s) => s === "passed").length };
}

/** Counts per decision action, over exactly the profiles the queue lists (those with a decision). */
export function actionCounts(profiles: Profile[]): Record<string, number> {
  const c: Record<string, number> = {};
  for (const p of profiles) {
    if (!p.decision) continue;
    c[p.decision.action] = (c[p.decision.action] ?? 0) + 1;
  }
  return c;
}

/** True when the oldest indexed run is the first one ever recorded, so earlier executions have no record. */
export function historyStartsAtRecordCutoff(runs: RunSummary[]): boolean {
  if (runs.length === 0) return false;
  const oldest = Math.min(...runs.map((r) => new Date(r.started_at).getTime()));
  return oldest >= new Date(RECORDS_START).getTime();
}

export function dataFreshness(
  latest: Pick<RunSummary, "started_at"> | undefined,
  now: Date,
): { ageHours: number; stale: boolean } {
  if (!latest) return { ageHours: Infinity, stale: true };
  const ageHours = (now.getTime() - new Date(latest.started_at).getTime()) / 3_600_000;
  return { ageHours, stale: ageHours > STALE_AFTER_HOURS };
}
