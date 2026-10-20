import type { Graph, GraphNode } from "./data";

export type Placed = GraphNode & { x: number; y: number };

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
