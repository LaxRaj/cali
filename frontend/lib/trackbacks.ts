import type { Trackback } from "./data";

export type FactSource = {
  url: string;
  runId: string;
  firstSeen: string;
  lastSeen: string;
  seenCount: number;
};

export type Fact = {
  id: string;
  type: Trackback["entity_type"];
  label: string;
  evidence: string;
  /** Best trust among its sources: 1 = quote verified / published by the company, 0.6 = search match, 0.4 = inferred. */
  confidence: number;
  firstSeen: string;
  lastSeen: string;
  sources: FactSource[];
};

/** Group ledger rows into facts (same thing found on several pages becomes one fact with several sources), newest first. */
export function groupFacts(rows: Trackback[]): Fact[] {
  const byId = new Map<string, Fact>();
  for (const r of rows) {
    const id = `${r.entity_type}|${r.entity_key}|${r.field}|${r.value}`;
    const src: FactSource = {
      url: r.source_url,
      runId: r.run_id,
      firstSeen: r.first_seen,
      lastSeen: r.last_seen,
      seenCount: r.seen_count,
    };
    const f = byId.get(id);
    if (!f) {
      byId.set(id, {
        id,
        type: r.entity_type,
        label: r.label,
        evidence: r.evidence,
        confidence: r.confidence,
        firstSeen: r.first_seen,
        lastSeen: r.last_seen,
        sources: [src],
      });
      continue;
    }
    f.sources.push(src);
    f.confidence = Math.max(f.confidence, r.confidence);
    f.evidence ||= r.evidence;
    if (r.first_seen < f.firstSeen) f.firstSeen = r.first_seen;
    if (r.last_seen > f.lastSeen) f.lastSeen = r.last_seen;
  }
  const facts = [...byId.values()];
  for (const f of facts) f.sources.sort((a, b) => (a.firstSeen < b.firstSeen ? -1 : 1));
  return facts.sort((a, b) => (a.lastSeen < b.lastSeen ? 1 : a.lastSeen > b.lastSeen ? -1 : a.label.localeCompare(b.label)));
}

export function trustLabel(confidence: number): "verified" | "matched" | "inferred" {
  return confidence >= 1 ? "verified" : confidence >= 0.6 ? "matched" : "inferred";
}
