import type { ReactNode } from "react";
import { TONES, type Tone } from "./tone";

/** An illuminated plate: gilt double frame, HUD corner brackets, inscription-style title. */
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
    <section className={`frame ${t.accent} ${t.panel} ${className}`}>
      <header className="relative z-[1] flex items-center justify-between gap-3 px-4 pt-3 pb-2">
        <h2
          className={`glow font-display text-[15px] font-semibold uppercase leading-none tracking-[0.2em] ${t.text}`}
        >
          <span aria-hidden className="ascii mr-2 text-[0.8em] opacity-80">
            ❧
          </span>
          {title}
        </h2>
        {right && <div className="text-xs">{right}</div>}
      </header>
      <div
        aria-hidden
        className="rule relative z-[1] mx-4 mb-1"
        style={{ color: "color-mix(in oklab, var(--accent) 65%, transparent)" }}
      />
      <div className="relative z-[1] p-4 pt-3">{children}</div>
    </section>
  );
}
