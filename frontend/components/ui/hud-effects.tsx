"use client";

import { useEffect, useSyncExternalStore } from "react";

/** Moves the blueprint-grid spotlight (--mx/--my on <html>) with the pointer. Renders nothing. */
export function Spotlight() {
  useEffect(() => {
    let raf = 0;
    const root = document.documentElement;
    function move(e: PointerEvent) {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        root.style.setProperty("--mx", `${e.clientX}px`);
        root.style.setProperty("--my", `${e.clientY}px`);
      });
    }
    window.addEventListener("pointermove", move, { passive: true });
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("pointermove", move);
    };
  }, []);
  return null;
}

function subscribe(cb: () => void) {
  const id = setInterval(cb, 1000);
  return () => clearInterval(id);
}
const tick = () => Math.floor(Date.now() / 1000);

const ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"];
export const roman = (n: number) => ROMAN[n] ?? String(n);

/** UTC HUD clock (the Groq quota resets at 00:00 UTC). Server renders a placeholder, no hydration mismatch. */
export function UtcClock() {
  const t = useSyncExternalStore(subscribe, tick, () => null);
  const text =
    t === null ? "--:--:--" : new Date(t * 1000).toISOString().slice(11, 19);
  return (
    <span
      className="font-hud text-xs tabular-nums tracking-[0.2em] text-emerald-800 dark:text-emerald-300"
      title="Current time, UTC"
    >
      <span className="mr-1.5 opacity-60">UTC</span>
      {text}
    </span>
  );
}
