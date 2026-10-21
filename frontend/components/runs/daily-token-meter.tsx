import type { RunSummary } from "@/lib/data";
import { fmtTokens } from "@/lib/format";

const hhmm = (iso: string) => `${new Date(iso).toISOString().slice(11, 16)} UTC`;

/** One UTC day of token use: a segment per run, sized against the day's budget. `runs` are that day's runs. */
export function DailyTokenMeter({
  runs,
  budget,
}: {
  runs: RunSummary[];
  budget: number;
}) {
  const total = runs.reduce((t, r) => t + r.tokens, 0);
  const scale = Math.max(budget, total, 1); // an overspent day still fits the bar
  const pct = budget > 0 ? Math.round((total / budget) * 100) : 0;
  const over = total > budget;
  const used = runs
    .filter((r) => r.tokens > 0)
    .sort((a, b) => a.run_id.localeCompare(b.run_id));
  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline gap-2">
        <span className="font-display text-4xl leading-none">
          {fmtTokens(total)}
        </span>
        <span className="text-xs text-zinc-600 dark:text-zinc-400">
          of {fmtTokens(budget)} · {pct}%
          {over && <strong className="text-rose-600"> · over budget</strong>}
        </span>
      </div>
      <div className="relative flex h-4 border border-zinc-900/25 bg-white/60 dark:border-amber-400/60 dark:bg-black/40">
        {used.map((r, i) => (
          <span
            key={r.run_id}
            role="img"
            aria-label={`${hhmm(r.started_at)}: ${fmtTokens(r.tokens)} tokens`}
            className={`h-full border-r border-zinc-900/60 ${i % 2 ? "bg-amber-300 dark:bg-amber-500" : "bg-amber-400 dark:bg-amber-600"}`}
            style={{ width: `${(r.tokens / scale) * 100}%` }}
          />
        ))}
        {over && (
          <span
            aria-hidden
            className="absolute inset-y-0 w-0.5 bg-rose-600"
            style={{ left: `${(budget / scale) * 100}%` }}
          />
        )}
      </div>
      <p className="text-[11px] text-zinc-600 dark:text-zinc-400">
        {over ? "0 left" : `${fmtTokens(budget - total)} left`} · resets 00:00 UTC
      </p>
    </div>
  );
}
