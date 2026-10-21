"use client";

import { useSyncExternalStore } from "react";

function subscribe(cb: () => void) {
  const id = setInterval(cb, 1000);
  return () => clearInterval(id);
}
const tick = () => Math.floor(Date.now() / 1000);

/** UTC clock (the Groq quota resets at 00:00 UTC). Server renders a placeholder, so no hydration mismatch. */
export function UtcClock() {
  const t = useSyncExternalStore(subscribe, tick, () => null);
  const text =
    t === null ? "--:--:--" : new Date(t * 1000).toISOString().slice(11, 19);
  return (
    <span
      className="text-xs tabular-nums tracking-wider text-zinc-600 dark:text-zinc-400"
      title="Current time, UTC"
    >
      <span className="mr-1.5 opacity-60">UTC</span>
      {text}
    </span>
  );
}
