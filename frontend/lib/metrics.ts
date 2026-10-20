// Every number the dashboard shows about runs, tokens and findings is computed here, once.
// Pure functions over the committed JSON: no I/O, no clock (callers pass `now`).
// Definitions (keep scripts/check-dashboard.ts and the dashboard-logic-check skill in step):
//  - a "day" is a UTC calendar day: the Groq quota resets at 00:00 UTC
//  - "tokens today" is the SUM over every run that started on that day
//  - a run is passed | failed | quota; quota (Groq limit hit) is not a quality failure

import { TOKEN_BUDGET } from "./data";
import type { Profile, RunStatus, RunSummary } from "./data";

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
};

/** One entry per UTC day that has runs, oldest first. */
export function dailyTotals(runs: RunSummary[]): DayTotal[] {
  const days = [...new Set(runs.map((r) => dayKey(r.started_at)))].sort();
  return days.map((day) => {
    const of = runsOnDay(runs, day);
    const count = (s: RunStatus) => of.filter((r) => runState(r) === s).length;
    return {
      day,
      tokens: dailyTokens(runs, day),
      budget: dailyBudget(runs, day),
      runs: of.length,
      passed: count("passed"),
      failed: count("failed"),
      quota: count("quota"),
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

export function dataFreshness(
  latest: RunSummary | undefined,
  now: Date,
): { ageHours: number; stale: boolean } {
  if (!latest) return { ageHours: Infinity, stale: true };
  const ageHours = (now.getTime() - new Date(latest.started_at).getTime()) / 3_600_000;
  return { ageHours, stale: ageHours > STALE_AFTER_HOURS };
}
