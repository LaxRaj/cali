import Link from "next/link";
import { Empty } from "@/components/ascii/art";
import { AsciiBar } from "@/components/charts/ascii-bar";
import { Sparkline } from "@/components/charts/sparkline";
import { DayRollupTable } from "@/components/runs/day-rollup-table";
import { RunStateBadge } from "@/components/runs/run-state-badge";
import { Panel } from "@/components/ui/panel";
import { readIndex } from "@/lib/data";
import { fmtDateTime, fmtDuration, fmtTokens } from "@/lib/format";
import { dailyBudget, dailyTotals, dayKey, runState } from "@/lib/metrics";

export const metadata = { title: "Runs — cali" };

export default function RunsPage() {
  const runs = readIndex();
  const desc = [...runs].reverse();
  const days = dailyTotals(runs);

  return (
    <div className="space-y-6">
      <h1 className="font-display text-6xl">
        Process monitor
      </h1>
      {runs.length === 0 ? (
        <Panel title="Runs" tone="amber">
          <Empty art="floppy" title="No runs recorded">
            Each scout run writes a log here, including failed ones.
          </Empty>
        </Panel>
      ) : (
        <>
          <div className="grid gap-6 md:grid-cols-3">
            <Panel title="Valid startups / run" tone="emerald">
              <div className="text-emerald-700 dark:text-emerald-300">
                <Sparkline
                  values={runs.map((r) => r.funnel.valid)}
                  label="Valid startups per run"
                />
              </div>
            </Panel>
            <Panel title="Tokens / run" tone="amber">
              <div className="text-amber-700 dark:text-amber-300">
                <Sparkline
                  values={runs.map((r) => r.tokens)}
                  label="Tokens used per run (the daily budget applies to the sum of a day's runs, see By day)"
                />
              </div>
            </Panel>
            <Panel title="Duration / run" tone="sky">
              <div className="text-sky-700 dark:text-sky-300">
                <Sparkline
                  values={runs.map((r) => r.duration_s)}
                  label="Run duration in seconds"
                />
              </div>
            </Panel>
          </div>

          <Panel title="By day" tone="amber" right={<span>UTC days</span>}>
            <DayRollupTable days={days} />
          </Panel>

          <Panel
            title="Run log"
            tone="violet"
            right={<span>{runs.length} runs</span>}
          >
            <div className="overflow-x-auto">
              <table className="w-full min-w-[40rem] text-left">
                <thead>
                  <tr className="border-b-2 border-zinc-900/25 text-[11px] uppercase tracking-widest dark:border-violet-400/60">
                    <th className="py-1 pr-3">Status</th>
                    <th className="pr-3">Started (UTC)</th>
                    <th className="pr-3">Funnel (found → valid)</th>
                    <th className="pr-3">Tokens</th>
                    <th className="pr-3 text-right">Time</th>
                  </tr>
                </thead>
                <tbody>
                  {desc.map((r) => (
                    <tr
                      key={r.run_id}
                      className="border-b border-zinc-900/20 dark:border-violet-400/20"
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
                        {r.funnel.candidates} → {r.funnel.selected} →{" "}
                        {r.funnel.crawled} → {r.funnel.valid}
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
                      <td className="pr-3 text-right tabular-nums">
                        {fmtDuration(r.duration_s)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </>
      )}
    </div>
  );
}
