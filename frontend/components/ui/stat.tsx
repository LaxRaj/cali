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
    <div
      className={`border-2 border-zinc-900 px-3 py-2 shadow-[3px_3px_0_0] shadow-zinc-900 ${t.panel} ${t.border}`}
    >
      <div className="text-[10px] font-semibold uppercase tracking-widest text-zinc-600 dark:text-zinc-400">
        {label}
      </div>
      <div className={`glow font-display text-4xl leading-none ${t.text}`}>
        {value}
      </div>
      {sub && (
        <div className="mt-1 text-[11px] text-zinc-600 dark:text-zinc-400">
          {sub}
        </div>
      )}
    </div>
  );
}
