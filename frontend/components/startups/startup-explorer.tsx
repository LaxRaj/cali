"use client";

import { useRouter } from "next/navigation";
import { useMemo, useRef, useState } from "react";
import { Empty } from "@/components/ascii/art";
import { StartupCard } from "@/components/startup-card";
import { DownloadButton } from "@/components/ui/download-button";
import { RetroButton } from "@/components/ui/retro-button";
import { RockerSwitch } from "@/components/ui/rocker-switch";
import { ShortcutHelp } from "@/components/ui/shortcut-help";
import type { Profile } from "@/lib/data";
import { normalizeStage, STAGES, toCsv, UNKNOWN_STAGE } from "@/lib/format";
import { useListKeys } from "@/lib/use-list-keys";
import { useQueryParams } from "@/lib/use-query-params";

type Sort = "score" | "newest" | "connected" | "name";
const SORTS: Sort[] = ["score", "newest", "connected", "name"];
const PAGE = 24;
const KEYS: [string, string][] = [
  ["j / k", "next / previous startup"],
  ["o", "open it"],
  ["/", "search"],
  ["?", "toggle this help"],
];

/** Everything the search box matches against. */
export function searchText(p: Profile): string {
  return [
    p.company_name,
    p.core_product,
    p.likely_bottleneck,
    p.hq,
    p.funding_stage,
    ...p.tech_stack,
    ...p.people.map((x) => x.name),
    ...(p.why_now ?? []).map((w) => w.text),
    ...(p.signals ?? []).flatMap((s) => [s.type, ...(s.roles ?? [])]),
    ...(p.contact?.site_tech ?? []).map((t) => t.name),
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

export function filterProfiles(
  profiles: Profile[],
  f: { q?: string; stage?: string | null; tag?: string | null; linked?: boolean; email?: boolean; qualified?: boolean; sort?: Sort },
): Profile[] {
  const q = (f.q ?? "").trim().toLowerCase();
  const terms = q.split(/\s+/).filter(Boolean);
  return profiles
    .filter((p) => !f.stage || normalizeStage(p.funding_stage) === f.stage)
    .filter((p) => !f.tag || p.tech_stack.includes(f.tag))
    .filter((p) => !f.linked || p.edges.length > 0)
    .filter((p) => !f.email || (p.contact?.emails?.length ?? 0) > 0)
    .filter((p) => !f.qualified || p.qualified)
    .filter((p) => {
      if (!terms.length) return true;
      const text = searchText(p);
      return terms.every((t) => text.includes(t)); // every word must match, in any field
    })
    .sort((a, b) =>
      f.sort === "name"
        ? a.company_name.localeCompare(b.company_name)
        : f.sort === "connected"
          ? b.edges.length - a.edges.length
          : f.sort === "newest"
            ? b.discovered_at.localeCompare(a.discovered_at)
            : (b.score ?? 0) - (a.score ?? 0),
    );
}

export function startupsCsv(rows: Profile[]): string {
  return toCsv(
    ["company", "score", "qualified", "stage", "hq", "website", "core_product", "bottleneck", "tech_stack", "emails", "action", "discovered_at", "source_url"],
    rows.map((p) => [
      p.company_name,
      p.score,
      p.qualified ? "yes" : "no",
      normalizeStage(p.funding_stage),
      p.hq,
      p.website,
      p.core_product,
      p.likely_bottleneck,
      p.tech_stack.join("; "),
      (p.contact?.emails ?? []).map((e) => e.value).join("; "),
      p.decision?.action,
      p.discovered_at,
      p.source_url,
    ]),
  );
}

export function StartupExplorer({ profiles }: { profiles: Profile[] }) {
  const router = useRouter();
  const [params, setParams] = useQueryParams();
  const query = params.get("q") ?? "";
  const stage = params.get("stage");
  const tag = params.get("tech");
  const linkedOnly = params.get("linked") === "1";
  const emailOnly = params.get("email") === "1";
  const qualifiedOnly = params.get("qualified") === "1";
  const sort = (SORTS.includes(params.get("sort") as Sort) ? params.get("sort") : "score") as Sort;
  const [limit, setLimit] = useState(PAGE);
  const searchRef = useRef<HTMLInputElement>(null);

  const stages = useMemo(() => {
    const counts = new Map<string, number>();
    profiles.forEach((p) => {
      const s = normalizeStage(p.funding_stage);
      counts.set(s, (counts.get(s) ?? 0) + 1);
    });
    const known: string[] = [...STAGES];
    // canonical order first, then anything else as written, then "unknown" last
    return [...counts.entries()].sort(([a], [b]) => {
      const rank = (s: string) => (s === UNKNOWN_STAGE ? 99 : known.indexOf(s) === -1 ? 50 : known.indexOf(s));
      return rank(a) - rank(b) || a.localeCompare(b);
    });
  }, [profiles]);
  const tags = useMemo(() => {
    const counts = new Map<string, number>();
    profiles.forEach((p) => p.tech_stack.forEach((t) => counts.set(t, (counts.get(t) ?? 0) + 1)));
    return [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 12).map(([t]) => t);
  }, [profiles]);

  const shown = useMemo(
    () => filterProfiles(profiles, { q: query, stage, tag, linked: linkedOnly, email: emailOnly, qualified: qualifiedOnly, sort }),
    [profiles, query, stage, tag, linkedOnly, emailOnly, qualifiedOnly, sort],
  );
  const page = shown.slice(0, limit);
  const handlers = useMemo(
    () => ({ onOpen: (i: number) => page[i] && router.push(`/startups/${page[i].slug}`), searchRef }),
    [page, router],
  );
  const keys = useListKeys(page.length, handlers);
  const set = (patch: Record<string, string | null>) => {
    setParams(patch);
    setLimit(PAGE);
  };

  return (
    <div className="space-y-4">
      <div className="space-y-3 border border-zinc-900/25 bg-sky-100 p-3 dark:border-sky-400/60 dark:bg-sky-950/40 dark:shadow-sky-400/30">
        <label className="flex items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-widest">search</span>
          <input
            ref={searchRef}
            type="search"
            value={query}
            onChange={(e) => set({ q: e.target.value })}
            placeholder="company, tech, founder, city, hiring role…  ( / )"
            className="min-w-0 flex-1 border border-zinc-900/25 bg-white px-2 py-1 placeholder:text-zinc-500 focus-visible:outline-2 focus-visible:outline-emerald-500 dark:border-sky-400/60 dark:bg-black"
          />
        </label>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-widest">stage</span>
          {stages.map(([s, n]) => (
            <RetroButton key={s} tone="violet" pressed={stage === s} onClick={() => set({ stage: stage === s ? null : s })}>
              {s} <span className="opacity-60">{n}</span>
            </RetroButton>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-widest">tech</span>
          {tags.map((t) => (
            <RetroButton key={t} tone="sky" pressed={tag === t} onClick={() => set({ tech: tag === t ? null : t })}>
              {t}
            </RetroButton>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
          {(
            [
              ["linked", linkedOnly, "only with connections"],
              ["email", emailOnly, "only with a published email"],
              ["qualified", qualifiedOnly, "only qualified leads"],
            ] as const
          ).map(([key, on, label]) => (
            <span key={key} className="flex items-center gap-2">
              <RockerSwitch checked={on} onChange={(v) => set({ [key]: v ? "1" : null })} label={label} />
              <span aria-hidden className="text-xs">
                {label}
              </span>
            </span>
          ))}
          <span className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-widest">sort</span>
            {SORTS.map((s) => (
              <RetroButton key={s} tone="amber" pressed={sort === s} onClick={() => set({ sort: s === "score" ? null : s })}>
                {s}
              </RetroButton>
            ))}
          </span>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <p aria-live="polite" className="text-xs text-zinc-600 dark:text-zinc-400">
          {shown.length} of {profiles.length} startups ·{" "}
          <kbd className="border border-zinc-900/25 px-1 dark:border-zinc-100/25">?</kbd> shortcuts
        </p>
        <DownloadButton filename="cali-startups.csv" build={() => startupsCsv(shown)}>
          Export {shown.length} as CSV
        </DownloadButton>
      </div>
      {shown.length === 0 ? (
        <Empty art="floppy" title="Nothing matches">
          Loosen a filter or clear the search.
        </Empty>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {page.map((p, i) => (
            <div
              key={p.slug}
              data-row={i}
              onClick={() => keys.setActive(i)}
              className={keys.active === i ? "outline-2 outline-offset-2 outline-rose-500" : ""}
            >
              <StartupCard p={p} />
            </div>
          ))}
        </div>
      )}
      {shown.length > page.length && (
        <RetroButton tone="sky" onClick={() => setLimit(limit + PAGE)}>
          Show {Math.min(PAGE, shown.length - page.length)} more ({shown.length - page.length} left)
        </RetroButton>
      )}
      <ShortcutHelp open={keys.help} onClose={() => keys.setHelp(false)} keys={KEYS} />
    </div>
  );
}
