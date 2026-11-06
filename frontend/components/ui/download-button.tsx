"use client";

import { RetroButton } from "./retro-button";
import type { Tone } from "./tone";

/** Builds the file in the browser from data already on the page (static site: nothing is fetched). */
export function DownloadButton({
  filename,
  mime = "text/csv",
  build,
  children,
  tone = "amber",
}: {
  filename: string;
  mime?: string;
  build: () => string;
  children: React.ReactNode;
  tone?: Tone;
}) {
  return (
    <RetroButton
      tone={tone}
      onClick={() => {
        const url = URL.createObjectURL(new Blob([build()], { type: `${mime};charset=utf-8` }));
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        a.click();
        setTimeout(() => URL.revokeObjectURL(url), 0);
      }}
    >
      {children}
    </RetroButton>
  );
}
