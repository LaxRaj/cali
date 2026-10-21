"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { Empty } from "@/components/ascii/art";
import { CopyPitchButton } from "@/components/copy-pitch-button";
import { PersonLinks } from "@/components/startups/links";
import { ScoreBadge } from "@/components/startups/score-badge";
import { RetroButton, retroClass } from "@/components/ui/retro-button";
import type { Decision, Profile } from "@/lib/data";

const ACTIONS: { key: Decision["action"]; label: string }[] = [
  { key: "contact_now", label: "Contact now" },
  { key: "follow_up", label: "Follow up" },
  { key: "enrich_more", label: "Enrich" },
  { key: "watch", label: "Watch" },
  { key: "skip", label: "Skip" },
];

const URGENCY_STYLE = {
  hot: "bg-rose-300 text-zinc-900 dark:bg-rose-950 dark:text-rose-300 dark:border-rose-400/70",
  warm: "bg-amber-200 text-zinc-900 dark:bg-amber-950 dark:text-amber-300 dark:border-amber-400/70",
  cold: "bg-zinc-200 text-zinc-700 dark:bg-zinc-900 dark:text-zinc-400 dark:border-zinc-600",
} as const;

function mailto(p: Profile) {
  const email = p.contact?.emails?.[0]?.value;
  if (!email) return null;
  const subject = `Quick idea for ${p.company_name}`;
  return `mailto:${email}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(p.value_prop_pitch)}`;
}

export function QueueView({ profiles }: { profiles: Profile[] }) {
  const [action, setAction] = useState<Decision["action"] | null>(
    "contact_now",
  );
  const [hotOnly, setHotOnly] = useState(false);

  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    profiles.forEach((p) => {
      const a = p.decision?.action ?? "watch";
      c[a] = (c[a] ?? 0) + 1;
    });
    return c;
  }, [profiles]);

  const rows = useMemo(
    () =>
      profiles
        .filter((p) => p.decision && (!action || p.decision.action === action))
        .filter((p) => !hotOnly || p.decision?.urgency === "hot")
        .sort(
          (a, b) => (b.decision?.priority ?? 0) - (a.decision?.priority ?? 0),
        ),
    [profiles, action, hotOnly],
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 border border-zinc-900/25 bg-rose-100 p-3 dark:border-rose-400/60 dark:bg-rose-950/40 dark:shadow-rose-400/30">
        <span className="text-xs font-semibold uppercase tracking-widest">
          action
        </span>
        {ACTIONS.map((a) => (
          <RetroButton
            key={a.key}
            tone="rose"
            pressed={action === a.key}
            onClick={() => setAction(action === a.key ? null : a.key)}
          >
            {a.label} <span className="opacity-60">{counts[a.key] ?? 0}</span>
          </RetroButton>
        ))}
        <RetroButton
          tone="amber"
          pressed={hotOnly}
          onClick={() => setHotOnly(!hotOnly)}
          className="ml-auto"
        >
          hot only
        </RetroButton>
      </div>

      <p
        aria-live="polite"
        className="text-xs text-zinc-600 dark:text-zinc-400"
      >
        {rows.length} lead{rows.length === 1 ? "" : "s"} · ranked by priority
        (fit + freshness + reachability)
      </p>

      {rows.length === 0 ? (
        <Empty art="radio" title="Queue is clear">
          Nothing matches this filter. Try another action, or wait for the next
          run.
        </Empty>
      ) : (
        <ol className="space-y-3">
          {rows.map((p, i) => {
            const d = p.decision!;
            const href = mailto(p);
            const leaders = p.people
              .filter((x) => /founder|ceo|cto|chief/i.test(x.role))
              .slice(0, 2);
            return (
              <li
                key={p.slug}
                className="border border-zinc-900/25 bg-white dark:border-emerald-400/60 dark:bg-black"
              >
                <div className="flex flex-wrap items-start gap-3 p-3">
                  <span
                    className="font-display text-3xl leading-none text-zinc-400"
                    aria-label={`rank ${i + 1}`}
                  >
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
                      <span
                        className={`border border-zinc-900/25 px-1.5 text-[11px] font-semibold uppercase ${URGENCY_STYLE[d.urgency]}`}
                      >
                        {d.urgency}
                      </span>
                      <ScoreBadge score={p.score} />
                      {p.outcome && (
                        <span className="border border-dashed border-zinc-900/25 px-1.5 text-[11px] uppercase dark:border-emerald-400/60">
                          you: {p.outcome.status}
                        </span>
                      )}
                    </div>
                    <p className="text-sm font-semibold">→ {d.next_step}</p>
                    <p className="text-xs text-zinc-600 dark:text-zinc-400">
                      {d.reasons.join(" · ")}
                    </p>
                    {leaders.length > 0 && (
                      <p className="flex flex-wrap items-center gap-x-3 text-xs">
                        {leaders.map((x) => (
                          <span key={x.name}>
                            {x.name}{" "}
                            <span className="text-zinc-500">· {x.role}</span>{" "}
                            <PersonLinks person={x} />
                          </span>
                        ))}
                      </p>
                    )}
                  </div>
                  <div className="flex shrink-0 flex-col items-stretch gap-2">
                    {href && (
                      <a href={href} className={retroClass("emerald")}>
                        ✉ Email with pitch
                      </a>
                    )}
                    <CopyPitchButton pitch={p.value_prop_pitch} />
                  </div>
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
