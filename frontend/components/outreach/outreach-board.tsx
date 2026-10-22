"use client";

import Link from "next/link";
import { useMemo } from "react";
import { AsciiBar } from "@/components/charts/ascii-bar";
import { Panel } from "@/components/ui/panel";
import { RetroLink } from "@/components/ui/retro-button";
import { Stat } from "@/components/ui/stat";
import type { Profile } from "@/lib/data";
import { dueLabel } from "@/lib/outreach";
import { outreachFunnel, replyRate } from "@/lib/outreach-metrics";
import { useNowMs, useOutreach } from "@/lib/outreach-store";
import { bucketFor, sortLeads } from "@/lib/queue";
import { LeadRow } from "./lead-row";

const TODAY_LIMIT = 5;

/** The top of the overview: what is waiting on you, how outreach is converting, and the leads to act on today. */
export function OutreachBoard({ profiles }: { profiles: Profile[] }) {
  const outreach = useOutreach(profiles);
  const nowMs = useNowMs();

  const rows = useMemo(
    () => profiles.map((p) => ({ p, s: outreach.get(p.slug)!.state })).map((r) => ({ ...r, bucket: bucketFor(r.p, r.s) })),
    [profiles, outreach],
  );
  const funnel = useMemo(() => outreachFunnel(rows.map((r) => r.s)), [rows]);
  const rate = replyRate(funnel);
  const ready = rows.filter((r) => r.bucket === "contact_now").length;
  // Next follow-ups that are coming due (not overdue, not snoozed, not given up on), soonest first.
  const comingUp = useMemo(
    () =>
      rows
        .filter((r) => r.bucket === "waiting" && r.s.next_due && !r.s.snoozed)
        .sort((a, b) => (a.s.next_due < b.s.next_due ? -1 : 1))
        .slice(0, 4),
    [rows],
  );
  const today = useMemo(() => sortLeads(rows.filter((r) => r.bucket === "due" || r.bucket === "contact_now")).slice(0, TODAY_LIMIT), [rows]);

  return (
    <section aria-label="Outreach" className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Due now" value={funnel.due} tone={funnel.due > 0 ? "rose" : "emerald"} sub={funnel.due > 0 ? "follow-ups and replies waiting on you" : "nothing waiting on you"} />
        <Stat label="Ready to contact" value={ready} tone="emerald" sub="fresh, strong fit, a way in" />
        <Stat label="Waiting on them" value={funnel.waiting} tone="amber" sub="written, inside the follow-up window" />
        <Stat label="Reply rate" value={rate === null ? "—" : `${rate}%`} tone="sky" sub={funnel.contacted ? `${funnel.replied} of ${funnel.contacted} contacted` : "log your first send"} />
      </div>

      <div className="grid gap-4 lg:grid-cols-[3fr_2fr]">
        <Panel
          title="Do today"
          tone={funnel.due > 0 ? "rose" : "emerald"}
          right={
            <Link href="/queue" className="text-xs underline">
              full queue →
            </Link>
          }
        >
          {today.length === 0 ? (
            <p className="text-sm">Nothing is due and no fresh lead is ready. Check back after the next scout run.</p>
          ) : (
            <ol className="space-y-3">
              {today.map((r, i) => (
                <LeadRow key={r.p.slug} p={r.p} s={r.s} bucket={r.bucket} nowMs={nowMs} rank={i + 1} />
              ))}
            </ol>
          )}
        </Panel>

        <Panel title="Outreach pipeline" tone="sky" right={<RetroLink href="/outreach" tone="sky">Tracker</RetroLink>}>
          <div className="space-y-1 text-sm">
            <AsciiBar label="leads" value={funnel.leads} max={Math.max(funnel.leads, 1)} width={18} className="text-zinc-600 dark:text-zinc-400" />
            <AsciiBar label="contacted" value={funnel.contacted} max={Math.max(funnel.leads, 1)} width={18} className="text-amber-700 dark:text-amber-400" />
            <AsciiBar label="replied" value={funnel.replied} max={Math.max(funnel.leads, 1)} width={18} className="text-emerald-700 dark:text-emerald-400" />
            <AsciiBar label="meeting" value={funnel.meeting} max={Math.max(funnel.leads, 1)} width={18} className="text-sky-700 dark:text-sky-400" />
            <AsciiBar label="won" value={funnel.won} max={Math.max(funnel.leads, 1)} width={18} className="text-emerald-800 dark:text-emerald-300" />
          </div>
          <p className="mt-3 text-xs text-zinc-700 dark:text-zinc-300">
            {funnel.passed} passed · {funnel.bounced} bounced
            {funnel.bounced > 0 && " (need another contact route)"}
          </p>
          {comingUp.length > 0 && (
            <div className="mt-4 border-t-2 border-dashed border-zinc-900/40 pt-3 dark:border-sky-400/30">
              <h3 className="mb-1 text-xs font-semibold uppercase tracking-widest text-zinc-700 dark:text-zinc-300">coming up</h3>
              <ul className="space-y-1 text-sm">
                {comingUp.map((r) => (
                  <li key={r.p.slug} className="flex items-baseline justify-between gap-2">
                    <Link href={`/startups/${r.p.slug}`} className="underline-offset-2 hover:underline">
                      {r.p.company_name}
                    </Link>
                    <span className="text-xs text-zinc-700 dark:text-zinc-300">
                      {nowMs !== null ? dueLabel(r.s.next_due, nowMs) : ""}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Panel>
      </div>
    </section>
  );
}
