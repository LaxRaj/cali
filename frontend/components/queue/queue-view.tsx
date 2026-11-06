"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { Empty } from "@/components/ascii/art";
import { CopyPitchButton } from "@/components/copy-pitch-button";
import { PersonLinks } from "@/components/startups/links";
import { ScoreBadge } from "@/components/startups/score-badge";
import { DownloadButton } from "@/components/ui/download-button";
import { RetroButton, retroClass } from "@/components/ui/retro-button";
import { ShortcutHelp } from "@/components/ui/shortcut-help";
import type { Decision, Profile } from "@/lib/data";
import { humanize, toCsv } from "@/lib/format";
import { actionCounts } from "@/lib/metrics";
import { useListKeys } from "@/lib/use-list-keys";
import { useQueryParams } from "@/lib/use-query-params";

const ACTIONS: { key: Decision["action"]; label: string }[] = [
  { key: "contact_now", label: "Contact now" },
  { key: "review", label: "Review" },
  { key: "follow_up", label: "Follow up" },
  { key: "enrich_more", label: "Enrich" },
  { key: "watch", label: "Watch" },
  { key: "skip", label: "Skip" },
];
const PAGE = 25;

const URGENCY_STYLE = {
  hot: "bg-rose-300 text-zinc-900 dark:bg-rose-950 dark:text-rose-300 dark:border-rose-400/70",
  warm: "bg-amber-200 text-zinc-900 dark:bg-amber-950 dark:text-amber-300 dark:border-amber-400/70",
  cold: "bg-zinc-200 text-zinc-700 dark:bg-zinc-900 dark:text-zinc-400 dark:border-zinc-600",
} as const;

const KEYS: [string, string][] = [
  ["j / k", "next / previous lead"],
  ["o", "open the startup"],
  ["e", "email with the drafted message"],
  ["c", "copy the drafted email"],
  ["/", "search"],
  ["?", "toggle this help"],
];

export function queueCsv(rows: Profile[]): string {
  return toCsv(
    ["company", "action", "urgency", "priority", "score", "next_step", "email", "email_source", "website", "url"],
    rows.map((p) => [
      p.company_name,
      p.decision?.action,
      p.decision?.urgency,
      p.decision?.priority,
      p.score,
      p.decision?.next_step,
      p.email_draft?.to,
      p.email_draft?.to_source_url,
      p.website,
      `/startups/${p.slug}`,
    ]),
  );
}

export function QueueView({ profiles }: { profiles: Profile[] }) {
  const router = useRouter();
  const [params, setParams] = useQueryParams();
  const action = (params.get("action") ?? "contact_now") as Decision["action"] | "all";
  const hotOnly = params.get("hot") === "1";
  const q = (params.get("q") ?? "").trim().toLowerCase();
  const [limit, setLimit] = useState(PAGE);
  const counts = useMemo(() => actionCounts(profiles), [profiles]);

  const rows = useMemo(
    () =>
      profiles
        .filter((p) => p.decision && (action === "all" || p.decision.action === action))
        .filter((p) => !hotOnly || p.decision?.urgency === "hot")
        .filter((p) => !q || `${p.company_name} ${p.core_product} ${p.decision?.next_step}`.toLowerCase().includes(q))
        .sort((a, b) => (b.decision?.priority ?? 0) - (a.decision?.priority ?? 0)),
    [profiles, action, hotOnly, q],
  );
  const shown = rows.slice(0, limit);

  const handlers = useMemo(
    () => ({
      onOpen: (i: number) => shown[i] && router.push(`/startups/${shown[i].slug}`),
      actions: {
        e: (i: number) => {
          const href = shown[i]?.email_draft?.mailto;
          if (href) window.location.href = href;
        },
        c: (i: number) => {
          const body = shown[i]?.email_draft?.body;
          if (body) void navigator.clipboard?.writeText(body);
        },
      },
    }),
    [shown, router],
  );
  const keys = useListKeys(shown.length, handlers);
  const total = Object.values(counts).reduce((t, n) => t + n, 0);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 border border-zinc-900/25 bg-rose-100 p-3 dark:border-rose-400/60 dark:bg-rose-950/40 dark:shadow-rose-400/30">
        <span className="text-xs font-semibold uppercase tracking-widest">action</span>
        <RetroButton tone="rose" pressed={action === "all"} onClick={() => setParams({ action: "all" })}>
          All <span className="opacity-60">{total}</span>
        </RetroButton>
        {ACTIONS.map((a) => (
          <RetroButton
            key={a.key}
            tone="rose"
            pressed={action === a.key}
            onClick={() => {
              setParams({ action: a.key === "contact_now" ? null : a.key });
              setLimit(PAGE);
            }}
          >
            {a.label} <span className="opacity-60">{counts[a.key] ?? 0}</span>
          </RetroButton>
        ))}
        <span className="ml-auto flex flex-wrap items-center gap-2">
          <input
            type="search"
            aria-label="Filter the queue"
            value={params.get("q") ?? ""}
            onChange={(e) => setParams({ q: e.target.value })}
            placeholder="filter…"
            className="w-32 border border-zinc-900/25 bg-white px-2 py-1 text-xs placeholder:text-zinc-500 focus-visible:outline-2 focus-visible:outline-emerald-500 dark:border-rose-400/60 dark:bg-black"
          />
          <RetroButton tone="amber" pressed={hotOnly} onClick={() => setParams({ hot: hotOnly ? null : "1" })}>
            hot only
          </RetroButton>
          <DownloadButton filename={`cali-queue-${action}.csv`} build={() => queueCsv(rows)}>
            CSV
          </DownloadButton>
        </span>
      </div>

      <p aria-live="polite" className="text-xs text-zinc-600 dark:text-zinc-400">
        {rows.length} lead{rows.length === 1 ? "" : "s"} · ranked by priority (fit + freshness + reachability) ·{" "}
        <kbd className="border border-zinc-900/25 px-1 dark:border-zinc-100/25">?</kbd> shortcuts
      </p>

      {rows.length === 0 ? (
        <Empty art="radio" title="Queue is clear">
          Nothing matches this filter. Try another action, or wait for the next run.
        </Empty>
      ) : (
        <ol className="space-y-3">
          {shown.map((p, i) => {
            const d = p.decision!;
            const draft = p.email_draft;
            const leaders = p.people.filter((x) => /founder|ceo|cto|chief/i.test(x.role)).slice(0, 2);
            const isActive = keys.active === i;
            return (
              <li
                key={p.slug}
                data-row={i}
                aria-current={isActive ? "true" : undefined}
                onClick={() => keys.setActive(i)}
                className={`border bg-white dark:bg-black ${
                  isActive
                    ? "border-rose-500 outline-2 outline-rose-500"
                    : "border-zinc-900/25 dark:border-emerald-400/60"
                }`}
              >
                <div className="flex flex-wrap items-start gap-3 p-3">
                  <span className="font-display text-3xl leading-none text-zinc-500" aria-label={`rank ${i + 1}`}>
                    {i + 1}
                  </span>
                  <div className="min-w-0 flex-1 space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <Link
                        href={`/startups/${p.slug}`}
                        className="font-display text-2xl leading-none hover:underline focus-visible:outline-2 focus-visible:outline-emerald-500"
                      >
                        {p.company_name}
                      </Link>
                      <span className={`border border-zinc-900/25 px-1.5 text-[11px] font-semibold uppercase ${URGENCY_STYLE[d.urgency]}`}>
                        {d.urgency}
                      </span>
                      {action === "all" && (
                        <span className="border border-zinc-900/25 px-1.5 text-[11px] uppercase dark:border-zinc-100/25">
                          {humanize(d.action)}
                        </span>
                      )}
                      <ScoreBadge score={p.score} />
                      {draft?.needs_human && (
                        <span
                          title={draft.needs_human_reason}
                          className="border border-dashed border-amber-600 px-1.5 text-[11px] uppercase text-amber-800 dark:text-amber-300"
                        >
                          needs a human
                        </span>
                      )}
                      {p.outcome && (
                        <span className="border border-dashed border-zinc-900/25 px-1.5 text-[11px] uppercase dark:border-emerald-400/60">
                          you: {p.outcome.status}
                          {p.outcome.intent ? ` · ${humanize(p.outcome.intent)}` : ""}
                        </span>
                      )}
                    </div>
                    <p className="text-sm font-semibold">→ {d.next_step}</p>
                    <p className="text-xs text-zinc-600 dark:text-zinc-400">{d.reasons.join(" · ")}</p>
                    {leaders.length > 0 && (
                      <p className="flex flex-wrap items-center gap-x-3 text-xs">
                        {leaders.map((x) => (
                          <span key={x.name}>
                            {x.name} <span className="text-zinc-600 dark:text-zinc-400">· {x.role}</span>{" "}
                            <PersonLinks person={x} />
                          </span>
                        ))}
                      </p>
                    )}
                  </div>
                  <div className="flex shrink-0 flex-col items-stretch gap-2">
                    {draft?.mailto && (
                      <a href={draft.mailto} className={retroClass("emerald")} title={`${draft.subject} (source: ${draft.to_source_url})`}>
                        ✉ Email {draft.intent ? `(${humanize(draft.intent)})` : ""}
                      </a>
                    )}
                    <CopyPitchButton pitch={draft?.body || p.value_prop_pitch} label={draft?.body ? "Copy email" : "Copy pitch"} />
                  </div>
                </div>
              </li>
            );
          })}
        </ol>
      )}
      {rows.length > shown.length && (
        <RetroButton tone="sky" onClick={() => setLimit(limit + PAGE)}>
          Show {Math.min(PAGE, rows.length - shown.length)} more ({rows.length - shown.length} left)
        </RetroButton>
      )}
      <ShortcutHelp open={keys.help} onClose={() => keys.setHelp(false)} keys={KEYS} />
    </div>
  );
}
