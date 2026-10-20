import type { Stage } from "@/lib/data";
import { fmtDuration } from "@/lib/format";

const COLORS: Record<string, string> = {
  discover: "bg-sky-300 dark:bg-sky-500",
  triage: "bg-violet-300 dark:bg-violet-500",
  crawl: "bg-amber-300 dark:bg-amber-500",
  extract: "bg-emerald-300 dark:bg-emerald-500",
  gates: "bg-rose-300 dark:bg-rose-500",
  store: "bg-emerald-200 dark:bg-emerald-300",
};

/** Gantt-style view of one run: each stage is a bar positioned by start offset and duration. */
export function StageTimeline({ stages }: { stages: Stage[] }) {
  const total = Math.max(...stages.map((s) => s.offset_s + s.duration_s), 1);
  return (
    <ul className="space-y-1.5">
      {stages.map((s) => (
        <li
          key={s.name}
          className="grid grid-cols-[5.5rem_1fr_4.5rem] items-center gap-2"
        >
          <span className="uppercase">{s.name}</span>
          <span className="relative block h-4 border border-zinc-900/40 bg-white/60 dark:border-emerald-400/30 dark:bg-black/40">
            <span
              role="img"
              aria-label={`${s.name} took ${fmtDuration(s.duration_s)}${s.status === "error" ? " and failed" : ""}`}
              className={`absolute inset-y-0 border-x border-zinc-900 ${s.status === "error" ? "bg-rose-500" : (COLORS[s.name] ?? "bg-zinc-300")}`}
              style={{
                left: `${(s.offset_s / total) * 100}%`,
                width: `${Math.max((s.duration_s / total) * 100, 1)}%`,
              }}
            />
          </span>
          <span className="text-right tabular-nums">
            {fmtDuration(s.duration_s)}
          </span>
        </li>
      ))}
    </ul>
  );
}
