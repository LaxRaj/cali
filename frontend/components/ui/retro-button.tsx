import Link from "next/link";
import type { ComponentProps } from "react";
import { TONES, type Tone } from "./tone";

export function retroClass(tone: Tone = "amber", pressed = false) {
  const t = TONES[tone];
  return [
    "inline-flex items-center gap-1.5 border-2 border-zinc-900 px-3 py-1 text-xs font-semibold uppercase tracking-wide",
    "text-zinc-900 transition-transform focus-visible:outline-2 focus-visible:outline-offset-2",
    t.ring,
    t.btn,
    t.border,
    pressed
      ? "translate-x-[3px] translate-y-[3px] shadow-none"
      : "shadow-[3px_3px_0_0] shadow-zinc-900 active:translate-x-[3px] active:translate-y-[3px] active:shadow-none",
    "dark:shadow-[3px_3px_0_0]",
  ].join(" ");
}

export function RetroButton({
  tone,
  pressed,
  className = "",
  ...props
}: ComponentProps<"button"> & { tone?: Tone; pressed?: boolean }) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      className={`${retroClass(tone, pressed)} ${className}`}
      {...props}
    />
  );
}

export function RetroLink({
  tone,
  className = "",
  ...props
}: ComponentProps<typeof Link> & { tone?: Tone }) {
  return <Link className={`${retroClass(tone)} ${className}`} {...props} />;
}
