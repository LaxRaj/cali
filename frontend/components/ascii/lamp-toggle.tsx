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
    () => false, // the default theme is light (paper), so the server render matches most first paints
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
      role="switch"
      aria-checked={dark}
      aria-label="Dark mode"
      title={
        dark ? "Turn the lamp on (light mode)" : "Turn the lamp off (dark mode)"
      }
      className="cursor-pointer leading-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-500"
    >
      <pre
        aria-hidden
        className={`ascii select-none text-[10px] leading-[1.05] ${
          dark
            ? "text-zinc-500"
            : "text-amber-500"
        }`}
      >
        {dark ? OFF : LIT}
      </pre>
    </button>
  );
}
