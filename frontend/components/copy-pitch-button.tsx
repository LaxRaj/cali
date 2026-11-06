"use client";

import { useEffect, useRef, useState } from "react";
import { RetroButton } from "@/components/ui/retro-button";

export function CopyPitchButton({ pitch, label = "Copy Pitch" }: { pitch: string; label?: string }) {
  const [state, setState] = useState<"idle" | "copied" | "error">("idle");
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  useEffect(() => () => clearTimeout(timer.current), []); // no setState after unmount

  async function copy() {
    try {
      await navigator.clipboard.writeText(pitch);
      setState("copied");
    } catch {
      setState("error");
    }
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setState("idle"), 1800);
  }

  return (
    <RetroButton tone="emerald" onClick={copy} className="shrink-0">
      <span aria-live="polite">
        {state === "copied" ? "Copied ✓" : state === "error" ? "Copy failed" : label}
      </span>
    </RetroButton>
  );
}
