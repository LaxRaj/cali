"use client";

import Link from "next/link";
import { PersonLinks } from "@/components/startups/links";
import { ScoreBadge } from "@/components/startups/score-badge";
import { RetroButton, retroClass } from "@/components/ui/retro-button";
import type { Profile } from "@/lib/data";
import type { OutreachState } from "@/lib/outreach";
import { logEvent, newEvent } from "@/lib/outreach-store";
import { type Bucket, fallbackRoute, mailtoFor, nextStep } from "@/lib/queue";
import { StatusPill } from "./status-pill";

const URGENCY_STYLE = {
  hot: "bg-rose-300 text-zinc-900 dark:bg-rose-950 dark:text-rose-300 dark:border-rose-400/70",
  warm: "bg-amber-200 text-zinc-900 dark:bg-amber-950 dark:text-amber-300 dark:border-amber-400/70",
  cold: "bg-zinc-200 text-zinc-700 dark:bg-zinc-900 dark:text-zinc-400 dark:border-zinc-600",
} as const;

type Props = {
  p: Profile;
  s: OutreachState;
  bucket: Bucket;
  nowMs: number | null;
  rank?: number;
};

/** One lead as an actionable row: what to do, why now, who to write to, the way in, and a one-click log. */
export function LeadRow({ p, s, bucket, nowMs, rank }: Props) {
  const href = mailtoFor(p, s);
  const route = href ? null : fallbackRoute(p);
  const leaders = p.people.filter((x) => /founder|ceo|cto|chief/i.test(x.role)).slice(0, 2);
  const why = p.why_now?.[0];
  const open = bucket === "due" || bucket === "contact_now";
  const urgency = p.decision?.urgency;
  const logLabel = s.status === "none" ? "Mark sent" : s.status === "replied" ? "I replied" : "Sent follow-up";

  return (
    <li
      className={`border-2 border-zinc-900 bg-white shadow-[4px_4px_0_0] shadow-zinc-900 dark:bg-black ${
        bucket === "due" ? "dark:border-rose-400/70 dark:shadow-rose-400/30" : "dark:border-emerald-400/60 dark:shadow-emerald-400/30"
      }`}
    >
      <div className="flex flex-wrap items-start gap-3 p-3">
        {rank !== undefined && (
          <span className="font-display text-3xl leading-none text-zinc-500 dark:text-zinc-400" aria-label={`rank ${rank}`}>
            {rank}
          </span>
        )}
        <div className="min-w-0 flex-1 space-y-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <Link
              href={`/startups/${p.slug}`}
              className="glow font-display text-2xl leading-none hover:underline focus-visible:outline-2 focus-visible:outline-emerald-500"
            >
              {p.company_name}
            </Link>
            {urgency && s.status === "none" && (
              <span className={`border-2 border-zinc-900 px-1.5 text-xs font-semibold uppercase ${URGENCY_STYLE[urgency]}`}>{urgency}</span>
            )}
            <ScoreBadge score={p.score} />
            <StatusPill state={s} nowMs={nowMs} />
          </div>
          <p className="text-sm font-semibold">→ {nextStep(p, s, bucket, nowMs)}</p>
          {why && (
            <p className="text-xs">
              <span className="font-semibold uppercase tracking-wide text-emerald-700 dark:text-emerald-300">why now › </span>
              {why.text}
            </p>
          )}
          {leaders.length > 0 && (
            <p className="flex flex-wrap items-center gap-x-3 text-xs">
              {leaders.map((x) => (
                <span key={x.name}>
                  {x.name} <span className="text-zinc-600 dark:text-zinc-400">· {x.role}</span> <PersonLinks person={x} />
                </span>
              ))}
            </p>
          )}
          {open && p.email_draft?.body && (
            <details className="text-xs">
              <summary className="cursor-pointer font-semibold uppercase tracking-wide">preview the email</summary>
              <p className="mt-1 font-semibold">{p.email_draft.subject}</p>
              <pre className="whitespace-pre-wrap font-sans text-zinc-700 dark:text-zinc-300">{p.email_draft.body}</pre>
            </details>
          )}
        </div>
        <div className="flex shrink-0 flex-col items-stretch gap-2">
          {href && (
            <a href={href} className={retroClass("emerald")}>
              ✉ {s.touches > 0 ? "Write follow-up" : "Open email"}
            </a>
          )}
          {route && (
            <a href={route.href} target="_blank" rel="noreferrer" className={retroClass("sky")}>
              ↗ {route.label}
            </a>
          )}
          {!href && !route && (
            <Link href={`/startups/${p.slug}`} className={retroClass("amber")}>
              Find a contact
            </Link>
          )}
          {open && (
            <RetroButton
              tone="amber"
              onClick={() =>
                void logEvent(
                  newEvent(p.company_name, "sent", {
                    channel: href ? "email" : "other",
                    subject: s.last_subject || p.email_draft?.subject,
                    to: s.last_to || p.email_draft?.to,
                    to_source_url: p.email_draft?.to_source_url,
                  }),
                )
              }
            >
              {logLabel}
            </RetroButton>
          )}
        </div>
      </div>
    </li>
  );
}
