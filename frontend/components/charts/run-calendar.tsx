import Link from "next/link";
import type { RunStatus, RunSummary } from "@/lib/data";
import { fmtDate } from "@/lib/format";
import { runState } from "@/lib/metrics";

const STYLE: Record<RunStatus, { cls: string; glyph: string }> = {
  passed: { cls: "bg-emerald-300 dark:bg-emerald-500", glyph: "" },
  failed: { cls: "bg-rose-300 dark:bg-rose-500", glyph: "×" },
  // the Groq daily limit stopped it: not a quality failure
  quota: { cls: "bg-amber-200 dark:bg-amber-500", glyph: "q" },
};

/**
 * One square per run (oldest first): green = passed, red × = failed gates, amber q = stopped at the Groq quota.
 * State is also a glyph (not colour alone) and in the accessible name. Links to the run.
 */
export function RunCalendar({ runs }: { runs: RunSummary[] }) {
  if (runs.length === 0)
    return <p className="text-xs text-zinc-500">no runs yet</p>;
  return (
    <ul className="flex flex-wrap gap-1" aria-label="Run history, oldest first">
      {runs.map((r) => {
        const state = runState(r);
        const s = STYLE[state];
        return (
          <li key={r.run_id}>
            <Link
              href={`/runs/${r.run_id}`}
              title={`${fmtDate(r.started_at)} — ${state} — ${r.funnel.valid} valid`}
              data-state={state}
              className={`flex h-5 w-5 items-center justify-center border border-zinc-900/25 text-[10px] font-bold leading-none text-zinc-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-500 dark:border-black ${s.cls}`}
            >
              <span aria-hidden>{s.glyph}</span>
              <span className="sr-only">
                {fmtDate(r.started_at)}: {state}
              </span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
