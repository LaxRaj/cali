import Link from "next/link";
import type { RunSummary } from "@/lib/data";
import { fmtDate } from "@/lib/format";

/** One square per run (oldest first): green = passed, red = failed gates. Links to the run. */
export function RunCalendar({ runs }: { runs: RunSummary[] }) {
  if (runs.length === 0)
    return <p className="text-xs text-zinc-500">no runs yet</p>;
  return (
    <ul className="flex flex-wrap gap-1" aria-label="Run history, oldest first">
      {runs.map((r) => (
        <li key={r.run_id}>
          <Link
            href={`/runs/${r.run_id}`}
            title={`${fmtDate(r.started_at)} — ${r.passed ? "passed" : "failed"} — ${r.funnel.valid} valid`}
            className={`block h-5 w-5 border-2 border-zinc-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-500 dark:border-black ${
              r.passed
                ? "bg-emerald-300 dark:bg-emerald-500"
                : "bg-rose-300 dark:bg-rose-500"
            }`}
          >
            <span className="sr-only">
              {fmtDate(r.started_at)}: {r.passed ? "passed" : "failed"}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
