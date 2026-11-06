import { fmtDate, fmtTokens } from "@/lib/format";
import type { DayTotal } from "@/lib/metrics";

/** One row per UTC day (newest first): how many runs, how they ended, and the day's token total. */
export function DayRollupTable({ days }: { days: DayTotal[] }) {
  if (days.length === 0)
    return <p className="text-xs text-zinc-500">no runs yet</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[28rem] text-left">
        <thead>
          <tr className="border-b-2 border-zinc-900 text-[11px] uppercase tracking-widest dark:border-violet-400/60">
            <th className="py-1 pr-3">Day (UTC)</th>
            <th className="pr-3">Runs</th>
            <th className="pr-3">Result</th>
            <th className="pr-3 text-right">Tokens</th>
            <th className="pr-3 text-right" title="tokens ÷ valid startups found that day">
              Per valid
            </th>
          </tr>
        </thead>
        <tbody>
          {[...days].reverse().map((d) => (
            <tr
              key={d.day}
              className="border-b border-zinc-900/20 dark:border-violet-400/20"
            >
              <td className="py-1.5 pr-3">{fmtDate(`${d.day}T00:00:00Z`)}</td>
              <td className="pr-3 tabular-nums">{d.runs}</td>
              <td className="pr-3 text-xs">
                {[
                  d.passed && `${d.passed} pass`,
                  d.failed && `${d.failed} fail`,
                  d.quota && `${d.quota} quota`,
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </td>
              <td className="pr-3 text-right tabular-nums">
                {fmtTokens(d.tokens)}{" "}
                <span className="text-xs text-zinc-600 dark:text-zinc-400">
                  {Math.round((d.tokens / d.budget) * 100)}%
                </span>
              </td>
              <td className="pr-3 text-right tabular-nums">
                {d.tokensPerValid === null ? (
                  <span className="text-zinc-500">—</span>
                ) : (
                  <>
                    {fmtTokens(d.tokensPerValid)}{" "}
                    <span className="text-xs text-zinc-600 dark:text-zinc-400">
                      ×{d.valid}
                    </span>
                  </>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
