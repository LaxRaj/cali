import type { Funnel as FunnelData } from "@/lib/data";
import { asciiBar } from "@/lib/format";

const STEPS: { key: keyof FunnelData; label: string }[] = [
  { key: "candidates", label: "found" },
  { key: "selected", label: "triaged" },
  { key: "crawled", label: "crawled" },
  { key: "extracted", label: "extracted" },
  { key: "relevant", label: "relevant" },
  { key: "valid", label: "valid" },
];

export function Funnel({ funnel }: { funnel: FunnelData }) {
  const max = Math.max(funnel.candidates, 1);
  return (
    <ol className="space-y-1">
      {STEPS.map((s, i) => {
        const v = funnel[s.key];
        const prev = i === 0 ? null : funnel[STEPS[i - 1].key];
        const last = i === STEPS.length - 1;
        return (
          <li key={s.key} className="flex items-center gap-2 whitespace-pre">
            <span className="w-20 shrink-0 uppercase">{s.label}</span>
            <span
              role="img"
              aria-label={`${s.label}: ${v}`}
              className={`tracking-tighter ${last ? "text-emerald-700 dark:text-emerald-300" : "text-sky-700 dark:text-sky-400"}`}
            >
              {asciiBar(v, max, 28)}
            </span>
            <span className="w-8 text-right tabular-nums">{v}</span>
            <span className="text-xs text-zinc-500">
              {prev ? `${prev ? Math.round((v / prev) * 100) : 0}%` : ""}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
