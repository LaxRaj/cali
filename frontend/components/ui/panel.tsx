import type { ReactNode } from "react";
import { TONES, type Tone } from "./tone";

/** A hairline-ruled section: a thin tone-coloured rule, a serif title, and room to breathe. */
export function Panel({
  title,
  tone = "emerald",
  right,
  children,
  className = "",
}: {
  title: string;
  tone?: Tone;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  const t = TONES[tone];
  return (
    <section className={`plate ${t.accent} ${className}`}>
      <header className="flex items-baseline justify-between gap-3 pt-2.5 pb-3">
        <h2 className="serif text-2xl leading-none text-zinc-900 dark:text-zinc-100">
          {title}
        </h2>
        {right && (
          <div className="text-xs text-zinc-600 dark:text-zinc-400">{right}</div>
        )}
      </header>
      <div>{children}</div>
    </section>
  );
}
