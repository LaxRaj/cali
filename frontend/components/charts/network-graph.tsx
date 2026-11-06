"use client";

import Link from "next/link";
import { useMemo } from "react";
import { RetroButton } from "@/components/ui/retro-button";
import type { Graph, GraphEdge, GraphNode } from "@/lib/data";
import { humanize } from "@/lib/format";
import { layoutGraph, subgraph } from "@/lib/network-layout";
import { useQueryParams } from "@/lib/use-query-params";

const SIZE = 800;
const LIMITS = [40, 80, 150];
const TYPES: GraphNode["type"][] = ["startup", "person", "org"];

function srcHost(url: string): string {
  try {
    return new URL(url).host.replace(/^www\./, "");
  } catch {
    return url;
  }
}
const FILL = {
  startup: "fill-emerald-300 stroke-zinc-900 dark:fill-emerald-500 dark:stroke-black",
  person: "fill-sky-300 stroke-zinc-900 dark:fill-sky-400 dark:stroke-black",
  org: "fill-amber-300 stroke-zinc-900 dark:fill-amber-400 dark:stroke-black",
} as const;
const LABEL = { startup: "Startup", person: "Person", org: "Org / investor" } as const;
const GLYPH = { startup: "■", person: "●", org: "◆" } as const;

function NodeButton({ node, onSelect }: { node?: GraphNode; onSelect: (id: string) => void }) {
  if (!node) return null;
  return (
    <button
      type="button"
      onClick={() => onSelect(node.id)}
      className="underline underline-offset-2 hover:no-underline focus-visible:outline-2 focus-visible:outline-emerald-500"
    >
      {node.label}
    </button>
  );
}

/**
 * The full network is hundreds of nodes; drawing all of them is unreadable. Show the best-connected N (with an
 * explicit "N of M shown"), or focus on one node's 1-2 hop neighbourhood. State lives in the URL (?focus=..).
 */
export function NetworkGraph({ graph, slugs }: { graph: Graph; slugs: Record<string, string> }) {
  const [params, setParams] = useQueryParams();
  const focus = params.get("focus");
  const hops = params.get("hops") === "2" ? 2 : 1;
  const rel = params.get("rel");
  const limit = Number(params.get("n")) || LIMITS[0];
  const typesParam = params.get("types");
  const types = useMemo(
    () => (typesParam?.split(",").filter((t) => TYPES.includes(t as GraphNode["type"])) ?? TYPES) as GraphNode["type"][],
    [typesParam],
  );
  const query = params.get("q") ?? "";

  const full = useMemo(() => new Map(graph.nodes.map((n) => [n.id, n])), [graph]);
  const rels = useMemo(
    () =>
      Object.entries(graph.edges.reduce<Record<string, number>>((a, e) => ({ ...a, [e.rel]: (a[e.rel] ?? 0) + 1 }), {})).sort(
        (a, b) => b[1] - a[1],
      ),
    [graph],
  );
  const sub = useMemo(() => subgraph(graph, { focus, hops, rel, types, limit }), [graph, focus, hops, rel, types, limit]);
  const { nodes, edges } = useMemo(() => layoutGraph(sub, SIZE, sub.nodes.length), [sub]);
  const byId = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);
  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? graph.nodes.filter((n) => n.label.toLowerCase().includes(q)).slice(0, 8) : [];
  }, [graph, query]);

  const sel = focus ? full.get(focus) : undefined;
  const links: GraphEdge[] = sel ? graph.edges.filter((e) => e.source === sel.id || e.target === sel.id) : [];
  const linked = new Set(links.flatMap((e) => [e.source, e.target]));
  const showAllLabels = nodes.length <= 40;
  const select = (id: string | null) => setParams({ focus: id, q: null });
  const toggleType = (t: GraphNode["type"]) => {
    const next = types.includes(t) ? types.filter((x) => x !== t) : [...types, t];
    setParams({ types: next.length === TYPES.length || next.length === 0 ? null : next.join(",") });
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 border border-zinc-900/25 bg-sky-100 p-3 dark:border-sky-400/60 dark:bg-sky-950/40">
        <label className="relative flex min-w-[12rem] flex-1 items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-widest">find</span>
          <input
            type="search"
            value={query}
            onChange={(e) => setParams({ q: e.target.value })}
            placeholder="startup, person or investor…"
            aria-label="Find a node to focus on"
            className="min-w-0 flex-1 border border-zinc-900/25 bg-white px-2 py-1 placeholder:text-zinc-500 focus-visible:outline-2 focus-visible:outline-emerald-500 dark:border-sky-400/60 dark:bg-black"
          />
          {matches.length > 0 && (
            <ul className="absolute left-12 right-0 top-full z-10 border border-zinc-900/40 bg-white text-xs shadow dark:bg-black" role="listbox" aria-label="Matches">
              {matches.map((m) => (
                <li key={m.id}>
                  <button type="button" onClick={() => select(m.id)} className="block w-full px-2 py-1 text-left hover:bg-sky-100 dark:hover:bg-sky-950">
                    {GLYPH[m.type]} {m.label} <span className="text-zinc-600 dark:text-zinc-400">· {m.degree}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </label>
        {TYPES.map((t) => (
          <RetroButton key={t} tone="violet" pressed={types.includes(t)} onClick={() => toggleType(t)}>
            {GLYPH[t]} {t}
          </RetroButton>
        ))}
        <select
          aria-label="Link type"
          value={rel ?? ""}
          onChange={(e) => setParams({ rel: e.target.value || null })}
          className="border border-zinc-900/25 bg-white px-1 py-1 text-xs dark:border-sky-400/60 dark:bg-black"
        >
          <option value="">all links</option>
          {rels.map(([r, n]) => (
            <option key={r} value={r}>
              {humanize(r)} ({n})
            </option>
          ))}
        </select>
        {sel ? (
          <>
            <RetroButton tone="amber" pressed={hops === 2} onClick={() => setParams({ hops: hops === 2 ? null : "2" })}>
              2 hops
            </RetroButton>
            <RetroButton tone="rose" onClick={() => select(null)}>
              clear focus
            </RetroButton>
          </>
        ) : (
          LIMITS.map((l) => (
            <RetroButton key={l} tone="amber" pressed={limit === l} onClick={() => setParams({ n: l === LIMITS[0] ? null : String(l) })}>
              top {l}
            </RetroButton>
          ))
        )}
      </div>
      <p aria-live="polite" className="text-xs text-zinc-600 dark:text-zinc-400">
        Showing {nodes.length} of {sub.total} {sel ? `nodes within ${hops} hop${hops > 1 ? "s" : ""} of ${sel.label}` : "nodes (best connected first)"} ·{" "}
        {graph.nodes.length} in the whole network
      </p>

      <div className="grid gap-4 lg:grid-cols-[1fr_20rem]">
        <div className="border border-zinc-900/25 bg-white dark:border-emerald-400/60 dark:bg-black">
          <svg
            viewBox={`0 0 ${SIZE} ${SIZE}`}
            role="group"
            aria-label={`Connection network: ${nodes.length} nodes and ${edges.length} links shown. The list below has the same nodes.`}
            className="hidden h-auto w-full sm:block"
            onClick={() => select(null)}
          >
            <g>
              {edges.map((e, i) => {
                const a = byId.get(e.source)!;
                const b = byId.get(e.target)!;
                const hot = sel && (e.source === sel.id || e.target === sel.id);
                return (
                  <line
                    key={i}
                    x1={a.x}
                    y1={a.y}
                    x2={b.x}
                    y2={b.y}
                    className={hot ? "stroke-rose-500" : "stroke-zinc-400 dark:stroke-emerald-900"}
                    strokeWidth={hot ? 2.5 : 1}
                    opacity={sel && !hot ? 0.25 : 0.9}
                  />
                );
              })}
            </g>
            <g>
              {nodes.map((n) => {
                const dim = sel && n.id !== sel.id && !linked.has(n.id);
                const r = 7 + Math.min(n.degree, 6) * 1.6;
                const label = showAllLabels || n.type === "startup" || n.id === focus || linked.has(n.id);
                return (
                  <g
                    key={n.id}
                    role="button"
                    tabIndex={-1}
                    aria-label={`${LABEL[n.type]} ${n.label}, ${n.degree} connections`}
                    onClick={(ev) => {
                      ev.stopPropagation();
                      select(n.id === focus ? null : n.id);
                    }}
                    opacity={dim ? 0.3 : 1}
                    className="cursor-pointer outline-none"
                  >
                    {n.type === "startup" ? (
                      <rect x={n.x - r} y={n.y - r} width={r * 2} height={r * 2} strokeWidth={2} className={FILL.startup} />
                    ) : n.type === "org" ? (
                      <polygon
                        points={`${n.x},${n.y - r} ${n.x + r},${n.y} ${n.x},${n.y + r} ${n.x - r},${n.y}`}
                        strokeWidth={2}
                        className={FILL.org}
                      />
                    ) : (
                      <circle cx={n.x} cy={n.y} r={r} strokeWidth={2} className={FILL.person} />
                    )}
                    {label && (
                      <text
                        x={n.x}
                        y={n.y + r + 13}
                        textAnchor="middle"
                        className="fill-zinc-900 text-[13px] dark:fill-emerald-200"
                        style={{ paintOrder: "stroke" }}
                      >
                        {n.label}
                      </text>
                    )}
                  </g>
                );
              })}
            </g>
          </svg>
          <ul className="flex flex-wrap gap-4 border-t-2 border-zinc-900/25 px-3 py-2 text-xs dark:border-emerald-400/60">
            <li>■ startup</li>
            <li>● person</li>
            <li>◆ org / investor</li>
            <li className="text-zinc-600 dark:text-zinc-400">click a node to focus · size = connections</li>
          </ul>
          {/* the same nodes as a keyboard- and phone-friendly list (the only view below the sm breakpoint) */}
          <details className="border-t border-zinc-900/15 px-3 py-2 text-xs">
            <summary className="cursor-pointer font-semibold uppercase tracking-widest">List of the {nodes.length} nodes shown</summary>
            <ul className="mt-2 columns-1 gap-4 sm:columns-2">
              {[...nodes].sort((a, b) => b.degree - a.degree).map((n) => (
                <li key={n.id} className="break-inside-avoid">
                  <button type="button" onClick={() => select(n.id)} className="text-left hover:underline">
                    {GLYPH[n.type]} {n.label}
                  </button>{" "}
                  <span className="tabular-nums text-zinc-600 dark:text-zinc-400">{n.degree}</span>
                </li>
              ))}
            </ul>
          </details>
        </div>

        <aside aria-live="polite" className="border border-zinc-900/25 bg-violet-100 p-3 dark:border-violet-400/60 dark:bg-violet-950/40">
          {sel ? (
            <>
              <p className="text-[10px] uppercase tracking-widest text-zinc-600 dark:text-zinc-400">{LABEL[sel.type]}</p>
              <h3 className="font-display text-3xl leading-none">{sel.label}</h3>
              <p className="mb-2 text-xs text-zinc-600 dark:text-zinc-400">
                {sel.degree} connections
                {sel.role ? ` · ${sel.role}` : ""}
              </p>
              {sel.type === "startup" && slugs[sel.id] && (
                <p className="mb-2">
                  <Link href={`/startups/${slugs[sel.id]}`} className="text-xs font-semibold underline underline-offset-2">
                    Open the startup →
                  </Link>
                </p>
              )}
              {sel.links && Object.keys(sel.links).length > 0 && (
                <p className="mb-2 flex flex-wrap gap-x-3 text-xs">
                  {Object.entries(sel.links).map(([k, url]) => (
                    <a key={k} href={url} target="_blank" rel="noreferrer" className="underline">
                      {k} ↗
                    </a>
                  ))}
                </p>
              )}
              <ul className="space-y-2">
                {links.map((e, i) => {
                  const other = full.get(e.source === sel.id ? e.target : e.source);
                  return (
                    <li key={i} className="border-l-2 border-zinc-900/25 pl-2 dark:border-violet-400/60">
                      {e.source === sel.id ? (
                        <>
                          <span className="italic">this</span> <span className="font-semibold">{humanize(e.rel)}</span>{" "}
                          <NodeButton node={other} onSelect={select} />
                        </>
                      ) : (
                        <>
                          <NodeButton node={other} onSelect={select} /> <span className="font-semibold">{humanize(e.rel)}</span>{" "}
                          <span className="italic">this</span>
                        </>
                      )}
                      <blockquote className="mt-0.5 text-xs text-zinc-600 dark:text-zinc-400">“{e.evidence}”</blockquote>
                      {(e.sources ?? []).length > 0 && (
                        <p className="mt-0.5 text-xs text-zinc-600 dark:text-zinc-400">
                          {e.sources?.map((s, j) => (
                            <span key={s.source_url}>
                              {j > 0 && " · "}
                              <a href={s.source_url} target="_blank" rel="noreferrer" className="underline-offset-2 hover:underline">
                                {srcHost(s.source_url)}
                              </a>
                            </span>
                          ))}
                        </p>
                      )}
                    </li>
                  );
                })}
              </ul>
            </>
          ) : (
            <p className="text-xs text-zinc-600 dark:text-zinc-400">
              Find or click a node to focus on its neighbourhood and see each link with the quote it came from.
            </p>
          )}
        </aside>
      </div>
    </div>
  );
}
