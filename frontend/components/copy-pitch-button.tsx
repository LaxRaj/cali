"use client";

import { useState } from "react";

export function CopyPitchButton({ pitch }: { pitch: string }) {
  const [state, setState] = useState<"idle" | "copied" | "error">("idle");

  async function copy() {
    try {
      await navigator.clipboard.writeText(pitch);
      setState("copied");
    } catch {
      setState("error");
    }
    setTimeout(() => setState("idle"), 1800);
  }

  return (
    <button
      type="button"
      onClick={copy}
      className="shrink-0 rounded-md border border-zinc-300 px-3 py-1.5 text-xs font-medium text-zinc-700 transition hover:bg-zinc-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-500 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
    >
      <span aria-live="polite">
        {state === "copied"
          ? "Copied ✓"
          : state === "error"
            ? "Copy failed"
            : "Copy Pitch"}
      </span>
    </button>
  );
}
