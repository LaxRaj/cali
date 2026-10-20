"use client";

import { useSyncExternalStore } from "react";

const LIT = `   .-.
  /___\\
 ' | | '
   | |
   \\_/
  __|__`;
const OFF = `   .-.
  /___\\
   | |
   | |
   \\_/
  __|__`;

function subscribe(cb: () => void) {
  const mo = new MutationObserver(cb);
  mo.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ["class"],
  });
  return () => mo.disconnect();
}

/** ASCII desk lamp: lit = light mode, off = dark phosphor mode. Click the lamp to flip the theme. */
export function LampToggle() {
  const dark = useSyncExternalStore(
    subscribe,
    () => document.documentElement.classList.contains("dark"),
    () => true,
  );

  function toggle() {
    const next = !dark;
    document.documentElement.classList.toggle("dark", next);
    try {
      localStorage.setItem("cali-theme", next ? "dark" : "light");
    } catch {}
  }

  return (
    <button
      type="button"
      onClick={toggle}
      aria-pressed={!dark}
      aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
      title={
        dark ? "Turn the lamp on (light mode)" : "Turn the lamp off (dark mode)"
      }
      className="cursor-pointer leading-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-500"
    >
      <pre
        aria-hidden
        className={`ascii select-none text-[10px] leading-[1.05] ${
          dark
            ? "text-emerald-700"
            : "text-amber-500 drop-shadow-[0_0_4px_rgb(251_191_36)]"
        }`}
      >
        {dark ? OFF : LIT}
      </pre>
    </button>
  );
}
