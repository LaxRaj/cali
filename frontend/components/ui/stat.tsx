import { TONES, type Tone } from "./tone";

export function Stat({
  label,
  value,
  sub,
  tone = "emerald",
}: {
  label: string;
  value: string | number;
  sub?: string;
  tone?: Tone;
}) {
  const t = TONES[tone];
  return (
    <div className={`plate ${t.accent} pt-2 pb-1`}>
      <div className="text-[10px] font-medium uppercase tracking-[0.18em] text-zinc-600 dark:text-zinc-400">
        {label}
      </div>
      <div
        className={`serif mt-1 text-5xl leading-none tabular-nums ${t.text}`}
      >
        {value}
      </div>
      {sub && (
        <div className="mt-2 text-[11px] text-zinc-600 dark:text-zinc-400">
          {sub}
        </div>
      )}
    </div>
  );
}
