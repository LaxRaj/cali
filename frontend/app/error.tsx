"use client";

import { RetroButton } from "@/components/ui/retro-button";

export default function ErrorPage({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div role="alert" className="space-y-4">
      <h1 className="font-display text-4xl sm:text-6xl">Something broke</h1>
      <p className="text-xs text-zinc-700 dark:text-zinc-300">
        This page could not render. The most common cause is a data file in backend/data with an unexpected shape; run{" "}
        <code>npm run check:data</code> to see which one.
      </p>
      <pre className="max-h-40 overflow-auto whitespace-pre-wrap border border-rose-600 p-2 text-xs">
        {error.message}
        {error.digest ? `\n(digest ${error.digest})` : ""}
      </pre>
      <RetroButton tone="rose" onClick={reset}>
        Try again
      </RetroButton>
    </div>
  );
}
