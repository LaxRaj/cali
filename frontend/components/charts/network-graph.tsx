"use client";

import { useMemo, useState } from "react";
import type { Graph } from "@/lib/data";
import { layoutGraph } from "@/lib/network-layout";

const SIZE = 800;

function srcHost(url: string): string {
  try {
    return new URL(url).host.replace(/^www\./, "");
  } catch {
    return url;
  }
}
const FILL = {
  startup:
    "fill-emerald-300 stroke-zinc-900 dark:fill-emerald-500 dark:stroke-black",
  person: "fill-sky-300 stroke-zinc-900 dark:fill-sky-400 dark:stroke-black",
  org: "fill-amber-300 stroke-zinc-900 dark:fill-amber-400 dark:stroke-black",
} as const;
const LABEL = {
  startup: "Startup",
  person: "Person",
  org: "Org / investor",
} as const;

export function NetworkGraph({ graph }: { graph: Graph }) {
  const { nodes, edges } = useMemo(() => layoutGraph(graph, SIZE), [graph]);
  const [selected, setSelected] = useState<string | null>(null);
  const byId = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);
  const sel = selected ? byId.get(selected) : undefined;
  const links = sel
    ? edges.filter((e) => e.source === sel.id || e.target === sel.id)
    : [];
  const linked = new Set(links.flatMap((e) => [e.source, e.target]));
  const showAllLabels = nodes.length <= 40;

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_20rem]">
      <div className="border-2 border-zinc-900 bg-white dark:border-emerald-400/60 dark:bg-black">
        <svg
          viewBox={`0 0 ${SIZE} ${SIZE}`}
          role="group"
          aria-label={`Connection network with ${nodes.length} nodes and ${edges.length} links. Use the list beside it for details.`}
          className="h-auto w-full"
          onClick={() => setSelected(null)}
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
                  className={
                    hot
                      ? "stroke-rose-500"
                      : "stroke-zinc-400 dark:stroke-emerald-900"
                  }
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
              const label =
                showAllLabels ||
                n.type === "startup" ||
                n.id === selected ||
                linked.has(n.id);
              return (
                <g
                  key={n.id}
                  role="button"
                  tabIndex={0}
                  aria-label={`${LABEL[n.type]} ${n.label}, ${n.degree} connections`}
                  aria-pressed={n.id === selected}
                  onClick={(ev) => {
                    ev.stopPropagation();
                    setSelected(n.id === selected ? null : n.id);
                  }}
                  onKeyDown={(ev) => {
                    if (ev.key === "Enter" || ev.key === " ") {
                      ev.preventDefault();
                      setSelected(n.id === selected ? null : n.id);
                    }
                  }}
                  opacity={dim ? 0.3 : 1}
                  className="cursor-pointer outline-none focus-visible:[&>*:first-child]:stroke-rose-500"
                >
                  {n.type === "startup" ? (
                    <rect
                      x={n.x - r}
                      y={n.y - r}
                      width={r * 2}
                      height={r * 2}
                      strokeWidth={2}
                      className={FILL.startup}
                    />
                  ) : n.type === "org" ? (
                    <polygon
                      points={`${n.x},${n.y - r} ${n.x + r},${n.y} ${n.x},${n.y + r} ${n.x - r},${n.y}`}
                      strokeWidth={2}
                      className={FILL.org}
                    />
                  ) : (
                    <circle
                      cx={n.x}
                      cy={n.y}
                      r={r}
                      strokeWidth={2}
                      className={FILL.person}
                    />
                  )}
                  {label && (
                    <text
                      x={n.x}
                      y={n.y + r + 11}
                      textAnchor="middle"
                      className="fill-zinc-900 text-[10px] dark:fill-emerald-200"
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
        <ul className="flex flex-wrap gap-4 border-t-2 border-zinc-900 px-3 py-2 text-xs dark:border-emerald-400/60">
          <li>■ startup</li>
          <li>● person</li>
          <li>◆ org / investor</li>
          <li className="text-zinc-500">
            click a node · node size = connections
          </li>
        </ul>
      </div>

      <aside
        aria-live="polite"
        className="border-2 border-zinc-900 bg-violet-100 p-3 dark:border-violet-400/60 dark:bg-violet-950/40"
      >
        {sel ? (
          <>
            <p className="text-[10px] uppercase tracking-widest text-zinc-600 dark:text-zinc-400">
              {LABEL[sel.type]}
            </p>
            <h3 className="glow font-display text-3xl leading-none">
              {sel.label}
            </h3>
            <p className="mb-2 text-xs text-zinc-600 dark:text-zinc-400">
              {sel.degree} connections
            </p>
            <ul className="space-y-2">
              {links.map((e, i) => {
                const other = byId.get(
                  e.source === sel.id ? e.target : e.source,
                );
                const NodeLink = () => (
                  <button
                    type="button"
                    onClick={() => other && setSelected(other.id)}
                    className="underline underline-offset-2 hover:no-underline focus-visible:outline-2 focus-visible:outline-emerald-500"
                  >
                    {other?.label}
                  </button>
                );
                return (
                  <li
                    key={i}
                    className="border-l-2 border-zinc-900 pl-2 dark:border-violet-400/60"
                  >
                    {e.source === sel.id ? (
                      <>
                        <span className="italic">this</span>{" "}
                        <span className="font-semibold">
                          {e.rel.replace("_", " ")}
                        </span>{" "}
                        <NodeLink />
                      </>
                    ) : (
                      <>
                        <NodeLink />{" "}
                        <span className="font-semibold">
                          {e.rel.replace("_", " ")}
                        </span>{" "}
                        <span className="italic">this</span>
                      </>
                    )}
                    <blockquote className="mt-0.5 text-xs text-zinc-600 dark:text-zinc-400">
                      “{e.evidence}”
                    </blockquote>
                    {(e.sources ?? []).length > 0 && (
                      <p className="mt-0.5 text-xs text-zinc-500">
                        {e.sources?.map((s, i) => (
                          <span key={s.source_url}>
                            {i > 0 && " · "}
                            <a
                              href={s.source_url}
                              target="_blank"
                              rel="noreferrer"
                              className="underline-offset-2 hover:underline"
                            >
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
            Select a node to see who it is connected to, with the quote each
            link came from.
          </p>
        )}
      </aside>
    </div>
  );
}
