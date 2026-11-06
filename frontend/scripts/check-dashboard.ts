// Checks that what the dashboard will show agrees with the raw data, before anyone looks at it.
//
//   npm run check:data            (real data: ../backend/data)
//   CALI_DEMO=1 npm run check:data   (demo-data/)
//
// The "raw" numbers below are recomputed straight from runs/<id>.json and profiles.json and
// deliberately do NOT use lib/metrics.ts; they are then compared with what lib/metrics.ts returns,
// so a bug in either side shows up as a mismatch. Exits 1 on any error; warnings do not fail.

import { execSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import {
  dailyBudget,
  dailyTokens,
  dailyTotals,
  dataFreshness,
  dayKey,
  latestRun,
  passRate,
  runState,
  actionCounts,
} from "../lib/metrics";
import { RECORDS_START } from "../lib/constants";
import { normalizeStage } from "../lib/format";
import { subgraph } from "../lib/network-layout";
import type { RunSummary } from "../lib/data";

const demo = process.env.CALI_DEMO === "1";
const root = path.join(__dirname, "..");
const dataDir =
  process.env.CALI_CHECK_DIR ?? // point at a copy of the data (used to prove the checks can fail)
  (demo
    ? path.join(root, "demo-data")
    : path.join(root, "..", "backend", "data"));

type Level = "ok" | "warn" | "error";
const results: { level: Level; name: string; detail: string }[] = [];
const report = (level: Level, name: string, detail = "") =>
  results.push({ level, name, detail });
const check = (cond: boolean, name: string, detail = "", level: Level = "error") =>
  report(cond ? "ok" : level, name, cond ? "" : detail);

function readJson<T>(...parts: string[]): T | null {
  try {
    return JSON.parse(fs.readFileSync(path.join(dataDir, ...parts), "utf-8")) as T;
  } catch {
    return null;
  }
}

const runs = readJson<{ runs: RunSummary[] }>("runs_index.json")?.runs ?? [];
if (runs.length === 0) {
  console.log(`check:data  ${dataDir}\n  no runs in runs_index.json: nothing to check`);
  process.exit(0);
}

// 2. index integrity
const ids = runs.map((r) => r.run_id);
check(new Set(ids).size === ids.length, "run ids are unique");
check(
  ids.every((id, i) => i === 0 || ids[i - 1] < id),
  "runs_index is sorted oldest-first",
  "the dashboard reads the last entry as the latest run",
);

// 1. tokens: index vs the run files, and the day total vs the dashboard's
const details = new Map<string, { usage?: { total_tokens?: number } } | null>();
for (const r of runs) details.set(r.run_id, readJson("runs", `${r.run_id}.json`));
const missing = runs.filter((r) => !details.get(r.run_id)).map((r) => r.run_id);
check(missing.length === 0, "every indexed run has a runs/<id>.json", missing.join(", "));
const drift = runs.filter((r) => {
  const d = details.get(r.run_id);
  return d && (d.usage?.total_tokens ?? 0) !== r.tokens;
});
check(
  drift.length === 0,
  "index tokens equal the run files' usage.total_tokens",
  drift.map((r) => `${r.run_id}: index ${r.tokens}`).join("; "),
);

const latest = latestRun(runs)!;
const today = latest.started_at.slice(0, 10); // raw: the UTC date as written in the file
const rawToday = runs
  .filter((r) => r.started_at.startsWith(today) || new Date(r.started_at).toISOString().startsWith(today))
  .reduce((t, r) => t + (details.get(r.run_id)?.usage?.total_tokens ?? r.tokens), 0);
const shown = dailyTokens(runs, dayKey(latest.started_at));
check(
  shown === rawToday,
  `tokens today (${today} UTC) shown = ${shown}, raw sum of run files = ${rawToday}`,
  "dashboard and raw data disagree",
);
check(
  shown >= latest.tokens,
  "tokens today is at least the latest run's tokens",
  `${shown} < ${latest.tokens}: only the latest run is being counted`,
);

// 3. states add up
const states = runs.map(runState);
const count = (s: string) => states.filter((x) => x === s).length;
check(
  count("passed") + count("failed") + count("quota") === runs.length,
  "passed + failed + quota = all runs",
  `${count("passed")}+${count("failed")}+${count("quota")} != ${runs.length}`,
);
const totals = dailyTotals(runs);
check(
  totals.reduce((t, d) => t + d.runs, 0) === runs.length,
  "daily totals cover every run exactly once",
);
check(
  totals.reduce((t, d) => t + d.tokens, 0) === runs.reduce((t, r) => t + r.tokens, 0),
  "daily token totals add up to the all-runs token sum",
);
const pr = passRate(runs, runs.length);
check(
  pr.passed + pr.failed + pr.skipped === runs.length,
  "pass-rate buckets cover every run",
);

// 4. funnel is a funnel
const chain = ["candidates", "selected", "crawled", "extracted", "relevant", "valid"] as const;
const brokenFunnel = runs.filter((r) =>
  chain.some((k, i) => i > 0 && r.funnel[k] > r.funnel[chain[i - 1]]),
);
check(
  brokenFunnel.length === 0,
  "funnel stages never grow (found >= triaged >= crawled >= extracted >= relevant >= valid)",
  brokenFunnel.map((r) => r.run_id).join(", "),
);

// 5. profiles
const profiles =
  readJson<{ slug: string; score?: number; discovered_at: string }[]>("profiles.json") ?? [];
const slugs = profiles.map((p) => p.slug);
check(new Set(slugs).size === slugs.length, "startup slugs are unique");
check(
  profiles.every((p) => p.score === undefined || (p.score >= 0 && p.score <= 100)),
  "lead scores are within 0-100",
);
const future = profiles.filter((p) => new Date(p.discovered_at).getTime() > Date.now() + 5 * 60_000);
check(future.length === 0, "no startup was discovered in the future", future.map((p) => p.slug).join(", "));

// 5b. stages fold into the canonical set (raw re-implementation, independent of lib/format.normalizeStage)
const rawStages = (profiles as { funding_stage?: string }[]).map((p) =>
  (p.funding_stage ?? "").replace(/[‐-—]/g, "-").trim().toLowerCase(),
);
const odd = [...new Set(rawStages.filter((s) => s && !/seed|series|yc|y ?combinator|angel|bridge|growth|ipo|public/.test(s)))];
check(odd.length === 0, "every funding stage maps to a known stage chip", `shown as written: ${odd.join(", ")}`, "warn");
const variants = new Set(profiles.map((p) => (p as { funding_stage?: string }).funding_stage).filter(Boolean)).size;
const chips = new Set(profiles.map((p) => normalizeStage((p as { funding_stage?: string }).funding_stage))).size;
check(chips <= variants + 1, "stage chips never outnumber the raw stage spellings", `${chips} chips from ${variants} spellings`);

// 5c. queue counts equal the queue list (only profiles with a decision are listed)
const decided = (profiles as { decision?: { action: string } }[]).filter((p) => p.decision);
const counted = Object.values(actionCounts(profiles as never)).reduce((t, n) => t + n, 0);
check(counted === decided.length, "queue counts add up to the listed leads", `${counted} counted vs ${decided.length} listed`);

// 5d. contact_now leads carry a sourced address (the agent may only send those)
const sendable = (profiles as { decision?: { action: string }; email_draft?: { to: string; to_source_url: string } }[]).filter(
  (p) => p.decision?.action === "contact_now",
);
const unsourced = sendable.filter((p) => p.email_draft?.to && !p.email_draft.to_source_url).length;
check(unsourced === 0, "every contact_now draft address has a source page", `${unsourced} without a source`);

// 5e. graph: every edge endpoint is a node; the network page says "N of M" so nothing is hidden silently
const graph = readJson<{ nodes: { id: string }[]; edges: { source: string; target: string }[] }>("graph.json");
if (graph) {
  const ids = new Set(graph.nodes.map((n) => n.id));
  const dangling = graph.edges.filter((e) => !ids.has(e.source) || !ids.has(e.target)).length;
  check(dangling === 0, "every graph edge connects two known nodes", `${dangling} dangling edges`);
  const shown = subgraph(graph as never, {}).total;
  check(shown === graph.nodes.length, "the network page's total equals all nodes (unfiltered)", `${shown} vs ${graph.nodes.length}`);
}

// 7. numbers are sane
const budget = dailyBudget(runs, dayKey(latest.started_at));
check(Number.isFinite(budget) && budget > 0, "daily budget is a positive number", String(budget));
check(
  runs.every((r) => Number.isFinite(r.tokens) && r.tokens >= 0 && Number.isFinite(r.duration_s)),
  "token and duration values are finite and non-negative",
);

// 6. freshness (warnings: the data can be valid and still old or behind the remote)
if (!demo) {
  const f = dataFreshness(latest, new Date());
  check(
    !f.stale,
    `latest run is ${f.ageHours.toFixed(1)} h old`,
    `older than the daily cadence allows: the scout may have stopped or this checkout is behind`,
    "warn",
  );
  try {
    // Without a fetch the comparison only knows about commits seen last time. Best effort, short timeout.
    execSync("git fetch --quiet origin main", { cwd: root, stdio: "ignore", timeout: 8000 });
  } catch {
    /* offline: fall back to the last fetched ref */
  }
  try {
    const behind = Number(
      execSync("git rev-list --count HEAD..origin/main", { cwd: root, stdio: ["ignore", "pipe", "ignore"] })
        .toString()
        .trim(),
    );
    check(
      behind === 0,
      "checkout is not behind origin/main",
      `${behind} commit(s) behind: newer scout runs may exist upstream (git pull; run \`git fetch\` first for a current answer)`,
      "warn",
    );
  } catch {
    report("warn", "checkout vs origin/main", "could not compare (no origin/main ref)");
  }
  // Every scout execution since run records began should have exactly one indexed run.
  try {
    const out = execSync(
      "gh run list --workflow scout.yml --limit 200 --json createdAt,status",
      { cwd: root, stdio: ["ignore", "pipe", "ignore"], timeout: 15000 },
    ).toString();
    const since = new Date(RECORDS_START).getTime();
    const executed = (JSON.parse(out) as { createdAt: string; status: string }[]).filter(
      (w) => w.status === "completed" && new Date(w.createdAt).getTime() >= since,
    ).length;
    const recorded = runs.filter((r) => new Date(r.started_at).getTime() >= since).length;
    check(
      recorded >= executed,
      `every scout execution since ${RECORDS_START} has a run record (${recorded} recorded, ${executed} executed)`,
      `${executed - recorded} execution(s) have no run record here: this checkout may be behind origin/main, or a run died before logging`,
      "warn",
    );
  } catch {
    /* gh missing or not logged in: skip silently */
  }
}

// --- report ---------------------------------------------------------------------------
const icon = { ok: "✓", warn: "!", error: "✗" } as const;
const quiet = process.argv.includes("--quiet"); // used by `predev`: say nothing unless something is off
const errors = results.filter((r) => r.level === "error").length;
const warns = results.filter((r) => r.level === "warn").length;
if (!quiet || errors || warns) console.log(`check:data  ${dataDir}${demo ? "  (demo)" : ""}`);
for (const r of results) {
  if (r.level === "ok") {
    if (!quiet) console.log(`  ${icon.ok} ${r.name}`);
  } else console.log(`  ${icon[r.level]} ${r.name}${r.detail ? `\n      ${r.detail}` : ""}`);
}
if (!quiet) {
  console.log(
    `\nHeadline: ${runs.length} runs, latest ${latest.run_id}; ${today} UTC: ` +
      `${shown} tokens of ${budget} (${Math.round((shown / budget) * 100)}%), ` +
      `${pr.passed} passed / ${pr.failed} failed / ${pr.skipped} quota, pass rate ${pr.pct ?? "n/a"}%`,
  );
  console.log(`${errors} error(s), ${warns} warning(s)`);
}
process.exit(errors ? 1 : 0);
