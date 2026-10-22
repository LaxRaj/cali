"use client";

import { useState } from "react";
import { RetroButton } from "@/components/ui/retro-button";
import type { Profile } from "@/lib/data";
import { PASS_REASONS, type EventType, type OutreachEvent, type OutreachState } from "@/lib/outreach";
import { logEvent, newEvent, removeEvent } from "@/lib/outreach-store";

type Props = { profile: Profile; state: OutreachState };

const SNOOZE_DAYS = [3, 7, 14];

/** Log what happened with a lead. Buttons follow the lead's state: you can only reply-log after a send, etc. */
export function StatusControl({ profile, state }: Props) {
  const [panel, setPanel] = useState<"pass" | "snooze" | null>(null);
  const [saved, setSaved] = useState<{ where: "local" | "browser"; event: OutreachEvent; text: string } | null>(null);
  const draft = profile.email_draft;
  const s = state.status;

  async function log(type: EventType, text: string, fields: Parameters<typeof newEvent>[2] = {}, at?: Date) {
    const event = newEvent(profile.company_name, type, fields, at);
    setPanel(null);
    setSaved({ where: await logEvent(event), event, text });
  }

  const sentFields = {
    channel: "email",
    subject: state.last_subject || draft?.subject,
    to: state.last_to || draft?.to,
    to_source_url: draft?.to && (state.last_to || draft.to) === draft.to ? draft.to_source_url : undefined,
  };
  const canSend = s === "none" || s === "contacted" || s === "replied" || s === "bounced" || s === "passed";

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Log outreach">
        {canSend && (
          <RetroButton tone="emerald" onClick={() => log("sent", "Logged: email sent", sentFields)}>
            {s === "none" ? "I sent this" : s === "replied" ? "I replied" : s === "passed" ? "Reopen: sent" : "Sent a follow-up"}
          </RetroButton>
        )}
        {(s === "contacted" || s === "bounced") && (
          <RetroButton tone="sky" onClick={() => log("replied", "Logged: they replied")}>
            They replied
          </RetroButton>
        )}
        {(s === "contacted" || s === "replied") && (
          <RetroButton tone="sky" onClick={() => log("meeting", "Logged: meeting booked")}>
            Meeting booked
          </RetroButton>
        )}
        {s === "meeting" && (
          <RetroButton tone="emerald" onClick={() => log("won", "Logged: won")}>
            Won
          </RetroButton>
        )}
        {s === "contacted" && (
          <RetroButton tone="rose" onClick={() => log("bounced", "Logged: bounced")}>
            Bounced
          </RetroButton>
        )}
        {(s === "contacted" || s === "replied" || s === "none") && (
          <RetroButton tone="amber" pressed={panel === "snooze"} onClick={() => setPanel(panel === "snooze" ? null : "snooze")}>
            Snooze
          </RetroButton>
        )}
        {s !== "passed" && s !== "won" && (
          <RetroButton tone="rose" pressed={panel === "pass"} onClick={() => setPanel(panel === "pass" ? null : "pass")}>
            Pass
          </RetroButton>
        )}
      </div>

      {panel === "pass" && (
        <div className="flex flex-wrap items-center gap-1.5 text-xs" role="group" aria-label="Why pass">
          <span className="font-semibold uppercase">why?</span>
          {PASS_REASONS.map((r) => (
            <RetroButton key={r} tone="rose" onClick={() => log("passed", `Logged: passed (${r.replace(/_/g, " ")})`, { reason: r })}>
              {r.replace(/_/g, " ")}
            </RetroButton>
          ))}
        </div>
      )}
      {panel === "snooze" && (
        <div className="flex flex-wrap items-center gap-1.5 text-xs" role="group" aria-label="Snooze for">
          <span className="font-semibold uppercase">snooze</span>
          {SNOOZE_DAYS.map((d) => (
            <RetroButton
              key={d}
              tone="amber"
              onClick={() => {
                const until = new Date(Date.now() + d * 86_400_000).toISOString().replace(/\.\d{3}Z$/, "+00:00");
                log("snooze", `Logged: snoozed ${d} days`, { until });
              }}
            >
              {d} days
            </RetroButton>
          ))}
        </div>
      )}

      {saved && (
        <p role="status" className="text-xs text-zinc-600 dark:text-zinc-400">
          {saved.text} ·{" "}
          {saved.where === "local"
            ? "saved to backend/data/outreach.jsonl"
            : "saved in this browser (export on the Outreach page to keep it)"}
          {saved.where === "browser" && (
            <>
              {" "}
              <button
                type="button"
                className="underline underline-offset-2"
                onClick={() => {
                  removeEvent(saved.event.id);
                  setSaved(null);
                }}
              >
                undo
              </button>
            </>
          )}
        </p>
      )}
    </div>
  );
}
