import Link from "next/link";
import type { ComponentProps } from "react";
import { TONES, type Tone } from "./tone";

/** Flat outlined button (see .btn in globals.css). Works on <button>, <a> and <Link>. */
export function retroClass(tone: Tone = "amber", pressed = false) {
  const t = TONES[tone];
  return [
    "btn text-[11px] font-medium uppercase tracking-[0.14em]",
    "text-zinc-900 dark:text-zinc-100",
    t.accent,
    pressed ? "translate-y-px" : "",
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
