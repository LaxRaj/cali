import type { ReactNode } from "react";
import { TONES, type Tone } from "./tone";

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
    <section
      className={`border-2 border-zinc-900 shadow-[4px_4px_0_0] shadow-zinc-900 ${t.panel} ${t.border} ${className}`}
    >
      <header
        className={`flex items-center justify-between gap-3 border-b-2 border-zinc-900 bg-white/70 px-3 py-1 dark:bg-black/50 ${t.border}`}
      >
        <h2
          className={`glow font-display text-xl uppercase leading-none tracking-wider ${t.text}`}
        >
          <span aria-hidden>┤ </span>
          {title}
          <span aria-hidden> ├</span>
        </h2>
        {right && <div className="text-xs">{right}</div>}
      </header>
      <div className="p-3">{children}</div>
    </section>
  );
}
