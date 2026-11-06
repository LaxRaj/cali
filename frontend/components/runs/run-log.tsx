"use client";

import Link from "next/link";
import { AsciiBar } from "@/components/charts/ascii-bar";
import { DownloadButton } from "@/components/ui/download-button";
import { RetroButton } from "@/components/ui/retro-button";
import type { RunStatus, RunSummary } from "@/lib/data";
import { fmtDateTime, fmtDuration, fmtTokens, toCsv } from "@/lib/format";
import { dailyBudget, dayKey, runState, sortedRuns } from "@/lib/metrics";
import { useQueryParams } from "@/lib/use-query-params";
import { RunStateBadge } from "./run-state-badge";

const STATES: RunStatus[] = ["passed", "failed", "quota"];

export function runsCsv(runs: RunSummary[]): string {
  return toCsv(
    ["run_id", "started_at", "status", "tokens", "token_budget", "duration_s", "candidates", "selected", "crawled", "valid", "failures"],
    runs.map((r) => [
      r.run_id,
      r.started_at,
      runState(r),
      r.tokens,
      r.token_budget,
      r.duration_s,
      r.funnel.candidates,
      r.funnel.selected,
      r.funnel.crawled,
      r.funnel.valid,
      r.failures.join("; "),
    ]),
  );
}

/** Newest first; filter by state and UTC day (kept in the URL), export what is shown. */
export function RunLog({ runs }: { runs: RunSummary[] }) {
  const [params, setParams] = useQueryParams();
  const state = params.get("state") as RunStatus | null;
  const day = params.get("day");
  const days = [...new Set(runs.map((r) => dayKey(r.started_at)))].sort().reverse();
  const shown = sortedRuns(runs)
    .reverse()
    .filter((r) => !state || runState(r) === state)
    .filter((r) => !day || dayKey(r.started_at) === day);

  return (
    <>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <RetroButton tone="violet" pressed={!state} onClick={() => setParams({ state: null })}>
          all
        </RetroButton>
        {STATES.map((s) => (
          <RetroButton key={s} tone="violet" pressed={state === s} onClick={() => setParams({ state: state === s ? null : s })}>
            {s} <span className="opacity-60">{runs.filter((r) => runState(r) === s).length}</span>
          </RetroButton>
        ))}
        <select
          aria-label="Day (UTC)"
          value={day ?? ""}
          onChange={(e) => setParams({ day: e.target.value || null })}
          className="border border-zinc-900/25 bg-white px-1 py-1 text-xs dark:border-violet-400/60 dark:bg-black"
        >
          <option value="">every day</option>
          {days.map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </select>
        <span className="ml-auto flex gap-2">
          <DownloadButton filename="cali-runs.csv" build={() => runsCsv(shown)}>
            CSV
          </DownloadButton>
          <DownloadButton filename="cali-runs.json" mime="application/json" build={() => JSON.stringify(shown, null, 2)}>
            JSON
          </DownloadButton>
        </span>
      </div>
      {/* one table; on phones each row stacks into a card (no sideways scrolling) */}
      <table className="w-full text-left max-sm:block">
        <thead className="max-sm:hidden">
          <tr className="border-b-2 border-zinc-900/25 text-[11px] uppercase tracking-widest dark:border-violet-400/60">
            <th className="py-1 pr-3">Status</th>
            <th className="pr-3">Started (UTC)</th>
            <th className="pr-3">Funnel (found → valid)</th>
            <th className="pr-3">Tokens</th>
            <th className="pr-3 text-right">Time</th>
          </tr>
        </thead>
        <tbody className="max-sm:block max-sm:space-y-2">
          {shown.map((r) => (
            <tr
              key={r.run_id}
              className="border-b border-zinc-900/20 dark:border-violet-400/20 max-sm:flex max-sm:flex-wrap max-sm:items-center max-sm:gap-x-3 max-sm:gap-y-1 max-sm:border max-sm:p-2 max-sm:text-xs [&>td]:max-sm:p-0"
            >
              <td className="py-1.5 pr-3">
                <RunStateBadge state={runState(r)} />
              </td>
              <td className="pr-3">
                <Link
                  href={`/runs/${r.run_id}`}
                  className="underline underline-offset-2 hover:no-underline focus-visible:outline-2 focus-visible:outline-emerald-500"
                >
                  {fmtDateTime(r.started_at)}
                </Link>
              </td>
              <td className="pr-3 tabular-nums">
                {r.funnel.candidates} → {r.funnel.selected} → {r.funnel.crawled} → {r.funnel.valid}
              </td>
              <td className="pr-3">
                <AsciiBar
                  label=""
                  value={r.tokens}
                  max={dailyBudget(runs, dayKey(r.started_at))}
                  width={10}
                  display={fmtTokens(r.tokens)}
                  className="text-amber-700 dark:text-amber-300"
                />
              </td>
              <td className="pr-3 text-right tabular-nums">{fmtDuration(r.duration_s)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {shown.length === 0 && <p className="text-xs text-zinc-600 dark:text-zinc-400">no runs match this filter</p>}
    </>
  );
}
