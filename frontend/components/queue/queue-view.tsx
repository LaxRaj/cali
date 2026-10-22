"use client";

import { useMemo, useState } from "react";
import { Empty } from "@/components/ascii/art";
import { LeadRow } from "@/components/outreach/lead-row";
import { RetroButton } from "@/components/ui/retro-button";
import type { Profile } from "@/lib/data";
import { useNowMs, useOutreach } from "@/lib/outreach-store";
import { BUCKETS, type Bucket, bucketFor, sortLeads } from "@/lib/queue";

const EMPTY_COPY: Partial<Record<Bucket, string>> = {
  due: "Nothing is waiting on you. Nice.",
  contact_now: "No fresh leads ready to contact. Wait for the next run.",
  waiting: "You have not written to anyone who is still pending.",
  done: "No meetings, wins or passes logged yet.",
};

export function QueueView({ profiles }: { profiles: Profile[] }) {
  const outreach = useOutreach(profiles);
  const nowMs = useNowMs();
  const [query, setQuery] = useState("");

  const all = useMemo(
    () =>
      sortLeads(
        profiles.map((p) => {
          const s = outreach.get(p.slug)!.state;
          return { p, s, bucket: bucketFor(p, s) };
        }),
      ),
    [profiles, outreach],
  );
  const counts = useMemo(() => {
    const c: Partial<Record<Bucket, number>> = {};
    all.forEach((r) => (c[r.bucket] = (c[r.bucket] ?? 0) + 1));
    return c;
  }, [all]);

  // Start where the work is: due follow-ups if there are any, otherwise fresh leads.
  const [picked, setPicked] = useState<Bucket | null>(null);
  const bucket: Bucket = picked ?? ((counts.due ?? 0) > 0 ? "due" : "contact_now");

  const q = query.trim().toLowerCase();
  const rows = all
    .filter((r) => r.bucket === bucket)
    .filter(
      (r) =>
        !q ||
        [r.p.company_name, r.p.core_product, ...r.p.people.map((x) => x.name)].some((t) => t.toLowerCase().includes(q)),
    );
  const current = BUCKETS.find((b) => b.key === bucket)!;

  return (
    <div className="space-y-4">
      <div className="space-y-2 border-2 border-zinc-900 bg-rose-100 p-3 shadow-[4px_4px_0_0] shadow-zinc-900 dark:border-rose-400/60 dark:bg-rose-950/40 dark:shadow-rose-400/30">
        <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Queue buckets">
          {BUCKETS.map((b) => (
            <RetroButton key={b.key} tone={b.key === "due" ? "rose" : "amber"} pressed={bucket === b.key} onClick={() => setPicked(b.key)}>
              {b.label} <span className="opacity-70">{counts[b.key] ?? 0}</span>
            </RetroButton>
          ))}
        </div>
        <label className="flex items-center gap-2 text-xs">
          <span className="font-semibold uppercase tracking-wide">search</span>
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="company, product or person"
            className="min-w-0 flex-1 border-2 border-zinc-900 bg-white px-2 py-1 text-sm dark:border-rose-400/60 dark:bg-black"
          />
        </label>
      </div>

      <p aria-live="polite" className="text-xs text-zinc-700 dark:text-zinc-300">
        {rows.length} lead{rows.length === 1 ? "" : "s"} · {current.label.toLowerCase()}: {current.hint}
      </p>

      {rows.length === 0 ? (
        <Empty art="radio" title="Queue is clear">
          {q ? "Nothing matches that search in this bucket." : (EMPTY_COPY[bucket] ?? "Nothing here right now.")}
        </Empty>
      ) : (
        <ol className="space-y-3">
          {rows.map((r, i) => (
            <LeadRow key={r.p.slug} p={r.p} s={r.s} bucket={r.bucket} nowMs={nowMs} rank={i + 1} />
          ))}
        </ol>
      )}
    </div>
  );
}
