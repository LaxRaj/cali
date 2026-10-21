"use client";

import { useState } from "react";
import type { Profile } from "@/lib/data";
import { RetroButton } from "@/components/ui/retro-button";

type Draft = NonNullable<Profile["email_draft"]>;

/** First-email draft. Sends nothing: opens the user's mail client (published recipient only) or copies the text. */
const INTENT_LABEL = {
  work_for: "work for them",
  build_for: "build for them",
  build_with: "build with them",
} as const;

export function EmailDraft({
  draft,
  outreach,
}: {
  draft: Draft;
  outreach?: Profile["outreach"];
}) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(
        `Subject: ${draft.subject}\n\n${draft.body}`,
      );
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
    }
  }

  return (
    <details className="border border-zinc-900 p-2 text-xs dark:border-emerald-400/50">
      <summary className="cursor-pointer font-semibold uppercase tracking-wide">
        email draft
        {draft.to ? ` › ${draft.to}` : " › no published address"}
      </summary>
      {draft.intent && (
        <p className="mt-2 text-zinc-500">
          intent: {INTENT_LABEL[draft.intent]}
          {draft.intent_reason ? ` (${draft.intent_reason})` : ""}
        </p>
      )}
      {outreach && outreach.length > 0 && (
        <p className="mt-1 font-semibold">
          {outreach.map((o) => `${o.kind}: ${o.status}`).join(" · ")}
        </p>
      )}
      <p className="mt-2 font-semibold">{draft.subject}</p>
      <pre className="mt-1 whitespace-pre-wrap font-sans">{draft.body}</pre>
      {draft.to_source_url && (
        <a
          href={draft.to_source_url}
          target="_blank"
          rel="noreferrer"
          className="mt-1 block text-zinc-500 underline-offset-2 hover:underline"
        >
          address published on this page ↗
        </a>
      )}
      <div className="mt-2 flex gap-2">
        {draft.mailto && (
          <a
            href={draft.mailto}
            className="border-2 border-zinc-900 px-2 py-0.5 font-semibold hover:bg-emerald-100 dark:border-emerald-400/60 dark:hover:bg-emerald-950"
          >
            Open in mail
          </a>
        )}
        <RetroButton tone="emerald" onClick={copy}>
          <span aria-live="polite">{copied ? "Copied ✓" : "Copy draft"}</span>
        </RetroButton>
      </div>
    </details>
  );
}
