"use client";

import Link from "next/link";
import { useMemo, useState, useSyncExternalStore } from "react";
import { Empty } from "@/components/ascii/art";
import { StatusPill } from "@/components/outreach/status-pill";
import { StartupCard } from "@/components/startup-card";
import { RetroButton } from "@/components/ui/retro-button";
import { RockerSwitch } from "@/components/ui/rocker-switch";
import type { Profile } from "@/lib/data";
import {
  type ExplorerState,
  SORTS,
  parseExplorerState,
  serializeExplorerState,
} from "@/lib/explorer-url";
import { leadsToCsv, publishedEmails } from "@/lib/leads-csv";
import { useNowMs, useOutreach } from "@/lib/outreach-store";
import { BUCKETS, bucketFor } from "@/lib/queue";
import { ScoreBadge } from "./score-badge";

// The view lives in the URL (shareable, survives back/forward). Reading it through useSyncExternalStore keeps the
// server markup and the first client render identical (both see an empty query string) and updates right after.
const urlListeners = new Set<() => void>();
function subscribeToUrl(cb: () => void) {
  urlListeners.add(cb);
  window.addEventListener("popstate", cb);
  return () => {
    urlListeners.delete(cb);
    window.removeEventListener("popstate", cb);
  };
}

export function StartupExplorer({ profiles }: { profiles: Profile[] }) {
  const search = useSyncExternalStore(subscribeToUrl, () => window.location.search, () => "");
  const state = useMemo(() => parseExplorerState(search), [search]);
  const [note, setNote] = useState("");
  const outreach = useOutreach(profiles);
  const nowMs = useNowMs();
  const set = (patch: Partial<ExplorerState>) => {
    const qs = serializeExplorerState({ ...state, ...patch });
    window.history.replaceState(null, "", qs ? `?${qs}` : window.location.pathname);
    urlListeners.forEach((l) => l());
  };
  const { query, stage, tag, status, linkedOnly, emailOnly, sort, view } = state;

  const stages = useMemo(
    () => [...new Set(profiles.map((p) => p.funding_stage).filter(Boolean))] as string[],
    [profiles],
  );
  const tags = useMemo(() => {
    const counts = new Map<string, number>();
    profiles.forEach((p) => p.tech_stack.forEach((t) => counts.set(t, (counts.get(t) ?? 0) + 1)));
    return [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 10).map(([t]) => t);
  }, [profiles]);

  const rows = useMemo(
    () =>
      profiles.map((p) => {
        const s = outreach.get(p.slug)!.state;
        return { p, s, bucket: bucketFor(p, s) };
      }),
    [profiles, outreach],
  );
  const bucketCounts = useMemo(() => {
    const c: Record<string, number> = {};
    rows.forEach((r) => (c[r.bucket] = (c[r.bucket] ?? 0) + 1));
    return c;
  }, [rows]);

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return rows
      .filter((r) => !stage || r.p.funding_stage === stage)
      .filter((r) => !tag || r.p.tech_stack.includes(tag))
      .filter((r) => !status || r.bucket === status)
      .filter((r) => !linkedOnly || r.p.edges.length > 0)
      .filter((r) => !emailOnly || (r.p.contact?.emails?.length ?? 0) > 0)
      .filter(
        (r) =>
          !q ||
          [r.p.company_name, r.p.core_product, r.p.likely_bottleneck, ...r.p.tech_stack, ...r.p.people.map((x) => x.name)]
            .join(" ")
            .toLowerCase()
            .includes(q),
      )
      .sort((a, b) =>
        sort === "name"
          ? a.p.company_name.localeCompare(b.p.company_name)
          : sort === "score"
            ? (b.p.score ?? 0) - (a.p.score ?? 0)
            : sort === "connected"
              ? b.p.edges.length - a.p.edges.length
              : sort === "newest"
                ? b.p.discovered_at.localeCompare(a.p.discovered_at)
                : (b.p.decision?.priority ?? 0) - (a.p.decision?.priority ?? 0),
      );
  }, [rows, query, stage, tag, status, linkedOnly, emailOnly, sort]);

  async function copyEmails() {
    const emails = publishedEmails(shown);
    try {
      await navigator.clipboard.writeText(emails.join("\n"));
      setNote(`Copied ${emails.length} published address${emails.length === 1 ? "" : "es"} (${shown.length - emails.length} lead${shown.length - emails.length === 1 ? "" : "s"} had none).`);
    } catch {
      setNote("Copy failed. Use Download CSV instead.");
    }
  }
  function downloadCsv() {
    const blob = new Blob([leadsToCsv(shown, window.location.origin)], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `cali-leads-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
    setNote(`Downloaded ${shown.length} lead${shown.length === 1 ? "" : "s"}.`);
  }

  return (
    <div className="space-y-4">
      <div className="space-y-3 border-2 border-zinc-900 bg-sky-100 p-3 shadow-[4px_4px_0_0] shadow-zinc-900 dark:border-sky-400/60 dark:bg-sky-950/40 dark:shadow-sky-400/30">
        <label className="flex items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-widest">search</span>
          <input
            type="search"
            value={query}
            onChange={(e) => set({ query: e.target.value })}
            placeholder="company, tech, founder…"
            className="flex-1 border-2 border-zinc-900 bg-white px-2 py-1 placeholder:text-zinc-500 focus-visible:outline-2 focus-visible:outline-emerald-500 dark:border-sky-400/60 dark:bg-black"
          />
        </label>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-widest">outreach</span>
          {BUCKETS.map((b) => (
            <RetroButton key={b.key} tone={b.key === "due" ? "rose" : "amber"} pressed={status === b.key} onClick={() => set({ status: status === b.key ? null : b.key })}>
              {b.label} <span className="opacity-70">{bucketCounts[b.key] ?? 0}</span>
            </RetroButton>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-widest">stage</span>
          {stages.map((s) => (
            <RetroButton key={s} tone="violet" pressed={stage === s} onClick={() => set({ stage: stage === s ? null : s })}>
              {s}
            </RetroButton>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-widest">tech</span>
          {tags.map((t) => (
            <RetroButton key={t} tone="sky" pressed={tag === t} onClick={() => set({ tag: tag === t ? null : t })}>
              {t}
            </RetroButton>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
          <label className="flex items-center gap-2 text-xs">
            <RockerSwitch checked={linkedOnly} onChange={(v) => set({ linkedOnly: v })} label="Only with connections" />
            only with connections
          </label>
          <label className="flex items-center gap-2 text-xs">
            <RockerSwitch checked={emailOnly} onChange={(v) => set({ emailOnly: v })} label="Only with a published email" />
            only with email
          </label>
          <span className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-widest">sort</span>
            {SORTS.map((s) => (
              <RetroButton key={s} tone="amber" pressed={sort === s} onClick={() => set({ sort: s })}>
                {s}
              </RetroButton>
            ))}
          </span>
          <span className="ml-auto flex items-center gap-2">
            <RetroButton tone="emerald" pressed={view === "cards"} onClick={() => set({ view: "cards" })}>
              cards
            </RetroButton>
            <RetroButton tone="emerald" pressed={view === "table"} onClick={() => set({ view: "table" })}>
              table
            </RetroButton>
          </span>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <p aria-live="polite" className="text-xs text-zinc-700 dark:text-zinc-300">
          {shown.length} of {profiles.length} startups
        </p>
        <span className="flex flex-wrap items-center gap-2">
          <RetroButton tone="sky" onClick={copyEmails} disabled={shown.length === 0}>
            Copy emails
          </RetroButton>
          <RetroButton tone="sky" onClick={downloadCsv} disabled={shown.length === 0}>
            Download CSV
          </RetroButton>
        </span>
      </div>
      {note && (
        <p role="status" className="text-xs text-zinc-700 dark:text-zinc-300">
          {note}
        </p>
      )}

      {shown.length === 0 ? (
        <Empty art="floppy" title="Nothing matches">
          Loosen a filter or clear the search.
        </Empty>
      ) : view === "table" ? (
        <div className="overflow-x-auto border-2 border-zinc-900 bg-white dark:border-emerald-400/60 dark:bg-black">
          <table className="w-full min-w-[40rem] text-left text-sm">
            <thead>
              <tr className="border-b-2 border-zinc-900 text-xs uppercase tracking-wide dark:border-emerald-400/60">
                <th scope="col" className="px-2 py-1.5">company</th>
                <th scope="col" className="px-2 py-1.5">score</th>
                <th scope="col" className="px-2 py-1.5">stage</th>
                <th scope="col" className="px-2 py-1.5">outreach</th>
                <th scope="col" className="px-2 py-1.5">next step</th>
                <th scope="col" className="px-2 py-1.5">email</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((r) => (
                <tr key={r.p.slug} className="border-b border-zinc-900/15 align-top dark:border-emerald-400/15">
                  <td className="px-2 py-1.5">
                    <Link href={`/startups/${r.p.slug}`} className="font-semibold underline-offset-2 hover:underline">
                      {r.p.company_name}
                    </Link>
                  </td>
                  <td className="px-2 py-1.5"><ScoreBadge score={r.p.score} /></td>
                  <td className="px-2 py-1.5">{r.p.funding_stage || "—"}</td>
                  <td className="px-2 py-1.5"><StatusPill state={r.s} nowMs={nowMs} /></td>
                  <td className="px-2 py-1.5 text-xs">{r.p.decision?.next_step ?? "—"}</td>
                  <td className="px-2 py-1.5 text-xs">{r.p.email_draft?.to ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {shown.map((r) => (
            <StartupCard key={r.p.slug} p={r.p} badge={r.s.status !== "none" ? <StatusPill state={r.s} nowMs={nowMs} /> : undefined} />
          ))}
        </div>
      )}
    </div>
  );
}
