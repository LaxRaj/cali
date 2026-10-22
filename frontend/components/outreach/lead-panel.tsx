"use client";

import { Panel } from "@/components/ui/panel";
import type { Profile } from "@/lib/data";
import { useNowMs, useOutreach } from "@/lib/outreach-store";
import { StatusControl } from "./status-control";
import { StatusPill } from "./status-pill";
import { Timeline } from "./timeline";

/** The top of a lead's dossier: what to do next, where outreach stands, buttons to log it, and the full history. */
export function LeadPanel({ profile }: { profile: Profile }) {
  const lead = useOutreach([profile]).get(profile.slug);
  const nowMs = useNowMs();
  if (!lead) return null;
  const d = profile.decision;
  return (
    <Panel
      title="Outreach"
      tone={lead.state.overdue ? "rose" : lead.state.status === "none" ? "emerald" : "amber"}
      right={<StatusPill state={lead.state} nowMs={nowMs} />}
    >
      <div className="space-y-3">
        {d && (
          <div>
            <p className="text-sm font-semibold">→ {d.next_step}</p>
            <p className="text-xs text-zinc-600 dark:text-zinc-400">{d.reasons.join(" · ")}</p>
          </div>
        )}
        <StatusControl profile={profile} state={lead.state} />
        <details open={lead.events.length > 0 && lead.events.length <= 4}>
          <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide">
            history ({lead.events.length})
          </summary>
          <div className="mt-2">
            <Timeline events={lead.events} />
          </div>
        </details>
      </div>
    </Panel>
  );
}
