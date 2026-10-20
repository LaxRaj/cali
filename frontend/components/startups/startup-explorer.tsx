"use client";

import { useMemo, useState } from "react";
import { Empty } from "@/components/ascii/art";
import { StartupCard } from "@/components/startup-card";
import { RetroButton } from "@/components/ui/retro-button";
import { RockerSwitch } from "@/components/ui/rocker-switch";
import type { Profile } from "@/lib/data";

type Sort = "newest" | "connected" | "name";

export function StartupExplorer({ profiles }: { profiles: Profile[] }) {
  const [query, setQuery] = useState("");
  const [stage, setStage] = useState<string | null>(null);
  const [tag, setTag] = useState<string | null>(null);
  const [linkedOnly, setLinkedOnly] = useState(false);
  const [sort, setSort] = useState<Sort>("newest");

  const stages = useMemo(
    () =>
      [
        ...new Set(profiles.map((p) => p.funding_stage).filter(Boolean)),
      ] as string[],
    [profiles],
  );
  const tags = useMemo(() => {
    const counts = new Map<string, number>();
    profiles.forEach((p) =>
      p.tech_stack.forEach((t) => counts.set(t, (counts.get(t) ?? 0) + 1)),
    );
    return [...counts.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10)
      .map(([t]) => t);
  }, [profiles]);

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return profiles
      .filter((p) => !stage || p.funding_stage === stage)
      .filter((p) => !tag || p.tech_stack.includes(tag))
      .filter((p) => !linkedOnly || p.edges.length > 0)
      .filter(
        (p) =>
          !q ||
          [
            p.company_name,
            p.core_product,
            p.likely_bottleneck,
            ...p.tech_stack,
            ...p.people.map((x) => x.name),
          ]
            .join(" ")
            .toLowerCase()
            .includes(q),
      )
      .sort((a, b) =>
        sort === "name"
          ? a.company_name.localeCompare(b.company_name)
          : sort === "connected"
            ? b.edges.length - a.edges.length
            : b.discovered_at.localeCompare(a.discovered_at),
      );
  }, [profiles, query, stage, tag, linkedOnly, sort]);

  return (
    <div className="space-y-4">
      <div className="space-y-3 border-2 border-zinc-900 bg-sky-100 p-3 shadow-[4px_4px_0_0] shadow-zinc-900 dark:border-sky-400/60 dark:bg-sky-950/40 dark:shadow-sky-400/30">
        <label className="flex items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-widest">
            search
          </span>
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="company, tech, founder…"
            className="flex-1 border-2 border-zinc-900 bg-white px-2 py-1 placeholder:text-zinc-400 focus-visible:outline-2 focus-visible:outline-emerald-500 dark:border-sky-400/60 dark:bg-black"
          />
        </label>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-widest">
            stage
          </span>
          {stages.map((s) => (
            <RetroButton
              key={s}
              tone="violet"
              pressed={stage === s}
              onClick={() => setStage(stage === s ? null : s)}
            >
              {s}
            </RetroButton>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-widest">
            tech
          </span>
          {tags.map((t) => (
            <RetroButton
              key={t}
              tone="sky"
              pressed={tag === t}
              onClick={() => setTag(tag === t ? null : t)}
            >
              {t}
            </RetroButton>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
          <RockerSwitch
            checked={linkedOnly}
            onChange={setLinkedOnly}
            label="Only with connections"
          />
          <span className="text-xs">only with connections</span>
          <span className="flex items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-widest">
              sort
            </span>
            {(["newest", "connected", "name"] as Sort[]).map((s) => (
              <RetroButton
                key={s}
                tone="amber"
                pressed={sort === s}
                onClick={() => setSort(s)}
              >
                {s}
              </RetroButton>
            ))}
          </span>
        </div>
      </div>

      <p
        aria-live="polite"
        className="text-xs text-zinc-600 dark:text-zinc-400"
      >
        {shown.length} of {profiles.length} startups
      </p>
      {shown.length === 0 ? (
        <Empty art="floppy" title="Nothing matches">
          Loosen a filter or clear the search.
        </Empty>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {shown.map((p) => (
            <StartupCard key={p.slug} p={p} />
          ))}
        </div>
      )}
    </div>
  );
}
