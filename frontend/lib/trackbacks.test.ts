import { describe, expect, it } from "vitest";
import type { Trackback } from "./data";
import { groupFacts, trustLabel } from "./trackbacks";

const row = (o: Partial<Trackback>): Trackback => ({
  entity_type: "edge",
  entity_key: "fund|invested_in|acme",
  field: "invested_in",
  label: "Fund invested in Acme",
  value: "Fund invested_in Acme",
  source_url: "https://n.example/a",
  evidence: "",
  run_id: "r1",
  first_seen: "2026-10-01T00:00:00",
  last_seen: "2026-10-01T00:00:00",
  seen_count: 1,
  confidence: 0.4,
  ...o,
});

describe("groupFacts", () => {
  it("merges one fact found on several pages into one fact with sources in first-seen order", () => {
    const facts = groupFacts([
      row({ source_url: "https://n.example/b", first_seen: "2026-10-05T00:00:00", last_seen: "2026-10-09T00:00:00", confidence: 1, evidence: "Fund backed Acme" }),
      row({}),
    ]);
    expect(facts).toHaveLength(1);
    expect(facts[0].sources.map((s) => s.url)).toEqual(["https://n.example/a", "https://n.example/b"]);
    expect(facts[0]).toMatchObject({ confidence: 1, firstSeen: "2026-10-01T00:00:00", lastSeen: "2026-10-09T00:00:00", evidence: "Fund backed Acme" });
  });

  it("keeps different values apart and sorts by last seen, newest first", () => {
    const facts = groupFacts([
      row({ field: "hq", entity_type: "startup", entity_key: "acme", value: "Berlin", label: "hq: Berlin" }),
      row({ field: "hq", entity_type: "startup", entity_key: "acme", value: "Paris", label: "hq: Paris", last_seen: "2026-10-08T00:00:00" }),
    ]);
    expect(facts.map((f) => f.label)).toEqual(["hq: Paris", "hq: Berlin"]);
  });

  it("returns nothing for no rows", () => {
    expect(groupFacts([])).toEqual([]);
  });
});

describe("trustLabel", () => {
  it.each([
    [1, "verified"],
    [0.6, "matched"],
    [0.4, "inferred"],
  ])("%d is %s", (c, label) => {
    expect(trustLabel(c)).toBe(label);
  });
});
