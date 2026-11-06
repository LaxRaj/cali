import type { Graph, GraphNode } from "./data";

export type Placed = GraphNode & { x: number; y: number };

export type SubgraphOptions = {
  /** Node id to centre on: only nodes within `hops` links of it are kept. */
  focus?: string | null;
  hops?: number;
  /** Node types to keep (default: all). The focus node is always kept. */
  types?: GraphNode["type"][];
  /** Only links of this relation (and the nodes they touch). */
  rel?: string | null;
  /** At most this many nodes, highest degree first (the focus first). */
  limit?: number;
};

/**
 * The part of a large graph worth drawing: a focused ego network, or the best-connected nodes after filters.
 * Never silently drops data: returns `total` so callers can say "N of M shown". Pure, deterministic.
 */
export function subgraph(graph: Graph, o: SubgraphOptions = {}): Graph & { total: number } {
  const limit = o.limit ?? 60;
  const types = new Set(o.types?.length ? o.types : ["startup", "person", "org"]);
  const edges = o.rel ? graph.edges.filter((e) => e.rel === o.rel) : graph.edges;
  const byId = new Map(graph.nodes.map((n) => [n.id, n]));
  let ids: string[];
  if (o.focus && byId.has(o.focus)) {
    const dist = new Map<string, number>([[o.focus, 0]]);
    let frontier = [o.focus];
    for (let h = 1; h <= (o.hops ?? 1) && frontier.length; h++) {
      const next: string[] = [];
      for (const id of frontier)
        for (const e of edges) {
          const other = e.source === id ? e.target : e.target === id ? e.source : null;
          if (other && !dist.has(other) && byId.has(other)) {
            dist.set(other, h);
            next.push(other);
          }
        }
      frontier = next;
    }
    ids = [...dist.keys()]
      .filter((id) => id === o.focus || types.has(byId.get(id)!.type))
      .sort((a, b) => dist.get(a)! - dist.get(b)! || byId.get(b)!.degree - byId.get(a)!.degree || a.localeCompare(b));
  } else {
    const touched = o.rel ? new Set(edges.flatMap((e) => [e.source, e.target])) : null;
    ids = graph.nodes
      .filter((n) => types.has(n.type) && (!touched || touched.has(n.id)))
      .sort((a, b) => b.degree - a.degree || a.id.localeCompare(b.id))
      .map((n) => n.id);
  }
  const total = ids.length;
  const keep = new Set(ids.slice(0, limit));
  return {
    nodes: graph.nodes.filter((n) => keep.has(n.id)),
    edges: edges.filter((e) => keep.has(e.source) && keep.has(e.target)),
    investors: graph.investors,
    total,
  };
}

/**
 * Deterministic static layout (no physics): startups on an inner ring; every other node on an outer
 * ring, ordered by the average angle of the startups it connects to so related nodes sit close together.
 */
export function layoutGraph(
  graph: Graph,
  size = 800,
  limit = 60,
): { nodes: Placed[]; edges: Graph["edges"] } {
  const keep = new Set(graph.nodes.slice(0, limit).map((n) => n.id));
  const nodes = graph.nodes.filter((n) => keep.has(n.id));
  const edges = graph.edges.filter(
    (e) => keep.has(e.source) && keep.has(e.target),
  );
  const c = size / 2;
  const pos = new Map<string, { x: number; y: number; a: number }>();

  const startups = nodes.filter((n) => n.type === "startup");
  startups.forEach((n, i) => {
    const a = (i / Math.max(startups.length, 1)) * Math.PI * 2 - Math.PI / 2;
    pos.set(n.id, {
      x: c + Math.cos(a) * size * 0.2,
      y: c + Math.sin(a) * size * 0.2,
      a,
    });
  });

  const neighbors = (id: string) =>
    edges.flatMap((e) =>
      e.source === id ? [e.target] : e.target === id ? [e.source] : [],
    );
  const desired = (n: GraphNode, i: number) => {
    const angles = neighbors(n.id).flatMap((m) =>
      pos.get(m) ? [pos.get(m)!.a] : [],
    );
    if (angles.length === 0) return -Math.PI / 2 + (i / 1000) * 0.001; // no startup neighbour: keep stable order
    const sx = angles.reduce((s, a) => s + Math.cos(a), 0);
    const sy = angles.reduce((s, a) => s + Math.sin(a), 0);
    return Math.atan2(sy, sx);
  };

  const outer = nodes
    .filter((n) => n.type !== "startup")
    .map((n, i) => ({ n, a: desired(n, i) }))
    .sort((p, q) => p.a - q.a);
  outer.forEach(({ n }, i) => {
    const a = (i / Math.max(outer.length, 1)) * Math.PI * 2 - Math.PI / 2;
    const r = size * (n.type === "person" ? 0.4 : 0.46); // people slightly inside orgs
    pos.set(n.id, { x: c + Math.cos(a) * r, y: c + Math.sin(a) * r, a });
  });

  return {
    // Rounded: Math.cos/sin differ in the last digits between Node and browsers, which breaks hydration.
    nodes: nodes.map((n) => ({
      ...n,
      x: Math.round(pos.get(n.id)!.x * 100) / 100,
      y: Math.round(pos.get(n.id)!.y * 100) / 100,
    })),
    edges,
  };
}
