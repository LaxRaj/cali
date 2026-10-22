"use client";

import { useEffect, useRef, useState } from "react";
import { RetroButton } from "@/components/ui/retro-button";
import type { OutreachEvent } from "@/lib/outreach";
import { addEvent, exportJson, parseImport, pruneSynced, useOutreachEvents } from "@/lib/outreach-store";

/**
 * Events you logged in this browser, and how to keep them: export a file, then
 * `uv run python outreach.py import <file>` and commit backend/data/outreach.jsonl. After the next build the
 * events are part of the data and the browser copies are dropped automatically.
 */
export function SyncControls({ bakedIds }: { bakedIds: string[] }) {
  const mine: OutreachEvent[] = useOutreachEvents();
  const file = useRef<HTMLInputElement>(null);
  const [msg, setMsg] = useState("");

  // Events the build already contains no longer need a browser copy.
  useEffect(() => {
    pruneSynced(new Set(bakedIds));
  }, [bakedIds]);

  function download() {
    const blob = new Blob([exportJson(mine)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `cali-outreach-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
    setMsg(`Exported ${mine.length} event${mine.length === 1 ? "" : "s"}. Now run: uv run python outreach.py import <file>`);
  }

  async function upload(f: File | undefined) {
    if (!f) return;
    const { events, skipped } = parseImport(await f.text());
    events.forEach(addEvent);
    setMsg(`Imported ${events.length} event${events.length === 1 ? "" : "s"}${skipped ? ` (${skipped} invalid skipped)` : ""}.`);
    if (file.current) file.current.value = "";
  }

  return (
    <div className="space-y-2 text-xs">
      <p>
        <span className="font-semibold">{mine.length}</span> event{mine.length === 1 ? "" : "s"} saved in this browser only.
        {mine.length > 0 ? " Export them so they survive clearing site data and show up on other devices." : " Anything you log appears here until it is exported."}
      </p>
      <div className="flex flex-wrap gap-2">
        <RetroButton tone="emerald" onClick={download} disabled={mine.length === 0}>
          Export events
        </RetroButton>
        <RetroButton tone="sky" onClick={() => file.current?.click()}>
          Import file
        </RetroButton>
        <input ref={file} type="file" accept="application/json" className="sr-only" aria-label="Import outreach file" onChange={(e) => void upload(e.target.files?.[0])} />
      </div>
      {msg && (
        <p role="status" className="text-zinc-700 dark:text-zinc-300">
          {msg}
        </p>
      )}
    </div>
  );
}
