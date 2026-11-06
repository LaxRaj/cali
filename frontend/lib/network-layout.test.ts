import { describe, expect, it } from "vitest";
import type { Graph } from "./data";
import { layoutGraph, subgraph } from "./network-layout";

const node = (id: string, type: "startup" | "person" | "org", degree: number) => ({ id, label: id.toUpperCase(), type, degree });
const G: Graph = {
  nodes: [node("a", "startup", 3), node("p", "person", 1), node("v", "org", 2), node("b", "startup", 1), node("x", "org", 1), node("lone", "person", 0)],
  edges: [
    { source: "p", target: "a", rel: "founded", evidence: "" },
    { source: "v", target: "a", rel: "invested_in", evidence: "" },
    { source: "v", target: "b", rel: "invested_in", evidence: "" },
    { source: "x", target: "a", rel: "previously_at", evidence: "" },
  ],
};

describe("subgraph", () => {
  it("keeps the best-connected nodes and reports the total so callers can say N of M", () => {
    const s = subgraph(G, { limit: 3 });
    // a (3), v (2), then the degree-1 tie broken by id: b
    expect(s.nodes.map((n) => n.id).sort()).toEqual(["a", "b", "v"]);
    expect(s.total).toBe(6);
    expect(s.edges.every((e) => ["a", "b", "v"].includes(e.source) && ["a", "b", "v"].includes(e.target))).toBe(true);
  });
  it("focuses on one node's neighbourhood, 1 or 2 hops", () => {
    expect(subgraph(G, { focus: "b", hops: 1 }).nodes.map((n) => n.id).sort()).toEqual(["b", "v"]);
    expect(subgraph(G, { focus: "b", hops: 2 }).nodes.map((n) => n.id).sort()).toEqual(["a", "b", "v"]);
  });
  it("filters by node type (the focus always stays) and by relation", () => {
    expect(subgraph(G, { focus: "a", types: ["org"] }).nodes.map((n) => n.id).sort()).toEqual(["a", "v", "x"]);
    const inv = subgraph(G, { rel: "invested_in" });
    expect(inv.nodes.map((n) => n.id).sort()).toEqual(["a", "b", "v"]);
    expect(inv.edges.every((e) => e.rel === "invested_in")).toBe(true);
  });
  it("falls back to the overview for an unknown focus id", () => {
    expect(subgraph(G, { focus: "nope" }).total).toBe(6);
  });
  it("handles an empty graph", () => {
    expect(subgraph({ nodes: [], edges: [] })).toEqual({ nodes: [], edges: [], investors: undefined, total: 0 });
  });
});

describe("layoutGraph", () => {
  it("places every node inside the canvas with finite coordinates", () => {
    const { nodes } = layoutGraph(G, 800);
    expect(nodes).toHaveLength(6);
    for (const n of nodes) {
      expect(Number.isFinite(n.x) && Number.isFinite(n.y)).toBe(true);
      expect(n.x).toBeGreaterThanOrEqual(0);
      expect(n.x).toBeLessThanOrEqual(800);
    }
  });
});
