import { Empty } from "@/components/ascii/art";
import { Sparkline } from "@/components/charts/sparkline";
import { DayRollupTable } from "@/components/runs/day-rollup-table";
import { RunLog } from "@/components/runs/run-log";
import { Panel } from "@/components/ui/panel";
import { readIndex } from "@/lib/data";
import { fmtDateTime } from "@/lib/format";
import { RECORDS_START } from "@/lib/constants";
import { dailyTotals, historyStartsAtRecordCutoff, sortedRuns } from "@/lib/metrics";

export const metadata = { title: "Runs — cali" };

export default function RunsPage() {
  const runs = sortedRuns(readIndex());
  const days = dailyTotals(runs);

  return (
    <div className="space-y-6">
      <h1 className="font-display text-4xl sm:text-6xl">Process monitor</h1>
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
            {historyStartsAtRecordCutoff(runs) && (
              <p className="mb-2 text-xs text-zinc-600 dark:text-zinc-400">
                Run records start {fmtDateTime(RECORDS_START)}; earlier scout
                executions were not logged.
              </p>
            )}
            <RunLog runs={runs} />
          </Panel>
        </>
      )}
    </div>
  );
}
