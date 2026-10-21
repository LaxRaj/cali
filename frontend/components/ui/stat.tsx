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
    <div className={`frame px-4 py-3 ${t.accent} ${t.panel}`}>
      <div className="relative font-display text-[10px] font-semibold uppercase tracking-[0.22em] text-zinc-600 dark:text-zinc-400">
        {label}
      </div>
      <div
        className={`glow relative font-hud text-4xl leading-none tabular-nums ${t.text}`}
      >
        {value}
      </div>
      {sub && (
        <div className="relative mt-1.5 font-fell text-[13px] italic text-zinc-600 dark:text-zinc-400">
          {sub}
        </div>
      )}
    </div>
  );
}
