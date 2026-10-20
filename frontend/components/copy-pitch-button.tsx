"use client";

import { useState } from "react";
import { RetroButton } from "@/components/ui/retro-button";

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
    <RetroButton tone="emerald" onClick={copy} className="shrink-0">
      <span aria-live="polite">
        {state === "copied"
          ? "Copied ✓"
          : state === "error"
            ? "Copy failed"
            : "Copy Pitch"}
      </span>
    </RetroButton>
  );
}
