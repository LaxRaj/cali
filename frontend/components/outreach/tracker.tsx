"use client";

import Link from "next/link";
import { useMemo } from "react";
import { Empty } from "@/components/ascii/art";
import { Panel } from "@/components/ui/panel";
import { Stat } from "@/components/ui/stat";
import type { Profile } from "@/lib/data";
import { fmtDateTime } from "@/lib/format";
import type { OutreachStatus } from "@/lib/outreach";
import { outreachFunnel, replyRate } from "@/lib/outreach-metrics";
import { useNowMs, useOutreach } from "@/lib/outreach-store";
import { StatusPill } from "./status-pill";
import { SyncControls } from "./sync-controls";

const COLUMNS: { status: OutreachStatus; title: string; tone: "amber" | "emerald" | "sky" | "rose" }[] = [
  { status: "contacted", title: "Contacted", tone: "amber" },
  { status: "replied", title: "Replied", tone: "emerald" },
  { status: "meeting", title: "Meeting", tone: "sky" },
  { status: "won", title: "Won", tone: "emerald" },
  { status: "bounced", title: "Bounced", tone: "rose" },
  { status: "passed", title: "Passed", tone: "rose" },
];

const FEED_LIMIT = 12;

/** Every lead you have touched, by stage, plus the latest activity across all of them. */
export function Tracker({ profiles }: { profiles: Profile[] }) {
  const outreach = useOutreach(profiles);
  const nowMs = useNowMs();

  const touched = useMemo(
    () =>
      profiles
        .map((p) => ({ p, lead: outreach.get(p.slug)! }))
        .filter((r) => r.lead.state.status !== "none")
        .sort((a, b) => {
          const ta = a.lead.state.next_due || "9999";
          const tb = b.lead.state.next_due || "9999";
          return ta < tb ? -1 : ta > tb ? 1 : 0;
        }),
    [profiles, outreach],
  );
  const funnel = outreachFunnel(profiles.map((p) => outreach.get(p.slug)!.state));
  const rate = replyRate(funnel);
  const feed = useMemo(
    () =>
      profiles
        .flatMap((p) => outreach.get(p.slug)!.events.map((e) => ({ e, p })))
        .sort((a, b) => (a.e.at < b.e.at ? 1 : a.e.at > b.e.at ? -1 : 0))
        .slice(0, FEED_LIMIT),
    [profiles, outreach],
  );
  const bakedIds = useMemo(() => profiles.flatMap((p) => p.outreach?.events.map((e) => e.id) ?? []), [profiles]);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Contacted" value={funnel.contacted} tone="amber" sub={`of ${funnel.leads} leads`} />
        <Stat label="Reply rate" value={rate === null ? "—" : `${rate}%`} tone="sky" sub={`${funnel.replied} replied`} />
        <Stat label="Meetings" value={funnel.meeting} tone="sky" sub={`${funnel.won} won`} />
        <Stat label="Due now" value={funnel.due} tone={funnel.due > 0 ? "rose" : "emerald"} sub="waiting on you" />
      </div>

      {touched.length === 0 ? (
        <Panel title="Nothing logged yet" tone="amber">
          <Empty art="radio" title="No outreach yet">
            Open a lead from the <Link href="/queue" className="underline">queue</Link> and press “I sent this” after you email them. It lands here, with follow-up dates.
          </Empty>
        </Panel>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {COLUMNS.map((c) => {
            const col = touched.filter((r) => r.lead.state.status === c.status);
            return (
              <Panel key={c.status} title={`${c.title} · ${col.length}`} tone={c.tone}>
                {col.length === 0 ? (
                  <p className="text-xs text-zinc-600 dark:text-zinc-400">none</p>
                ) : (
                  <ul className="space-y-2">
                    {col.map(({ p, lead }) => (
                      <li key={p.slug} className="text-sm">
                        <Link href={`/startups/${p.slug}`} className="font-semibold underline-offset-2 hover:underline">
                          {p.company_name}
                        </Link>{" "}
                        <StatusPill state={lead.state} nowMs={nowMs} />
                        <p className="text-xs text-zinc-700 dark:text-zinc-300">
                          {lead.state.last_contact ? `last sent ${fmtDateTime(lead.state.last_contact)}` : "no send logged"}
                        </p>
                      </li>
                    ))}
                  </ul>
                )}
              </Panel>
            );
          })}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[3fr_2fr]">
        <Panel title="Recent activity" tone="violet">
          {feed.length === 0 ? (
            <p className="text-xs text-zinc-600 dark:text-zinc-400">No events yet.</p>
          ) : (
            <ul className="space-y-1.5 text-xs">
              {feed.map(({ e, p }) => (
                <li key={e.id}>
                  <span className="text-zinc-600 dark:text-zinc-400">{fmtDateTime(e.at)} · </span>
                  <Link href={`/startups/${p.slug}`} className="font-semibold underline-offset-2 hover:underline">
                    {p.company_name}
                  </Link>{" "}
                  <span className="uppercase">{e.type}</span>
                  {e.subject && <span className="text-zinc-600 dark:text-zinc-400"> “{e.subject}”</span>}
                  {e.reason && <span className="text-zinc-600 dark:text-zinc-400"> ({e.reason.replace(/_/g, " ")})</span>}
                </li>
              ))}
            </ul>
          )}
        </Panel>
        <Panel title="Keep your log" tone="sky">
          <SyncControls bakedIds={bakedIds} />
        </Panel>
      </div>
    </div>
  );
}
