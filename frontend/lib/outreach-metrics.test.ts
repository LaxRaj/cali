import { describe, expect, it } from "vitest";
import { foldOutreach, type OutreachEvent } from "./outreach";
import { outreachFunnel, replyRate } from "./outreach-metrics";

const NOW = Date.parse("2026-10-20T09:00:00Z");
const day = (n: number) => new Date(NOW - n * 86_400_000).toISOString();
const ev = (id: string, type: OutreachEvent["type"], daysAgo: number): OutreachEvent => ({ id, company: "A", type, at: day(daysAgo) });
const state = (...e: OutreachEvent[]) => foldOutreach(e, NOW);

describe("outreachFunnel", () => {
  const states = [
    state(), // never contacted
    state(ev("1", "sent", 2)), // waiting
    state(ev("2", "sent", 10)), // due
    state(ev("3", "sent", 9), ev("4", "replied", 8)), // replied, overdue
    state(ev("5", "sent", 9), ev("6", "replied", 8), ev("7", "meeting", 1)),
    state(ev("8", "sent", 9), ev("9", "meeting", 5), ev("10", "won", 1)),
    state(ev("11", "sent", 9), ev("12", "passed", 8)),
    state(ev("13", "sent", 3), ev("14", "bounced", 3)),
    state(ev("15", "meeting", 1)), // legacy: meeting with no logged send
  ];
  const f = outreachFunnel(states);

  it("counts each stage", () => {
    expect(f).toEqual({ leads: 9, contacted: 8, replied: 4, meeting: 3, won: 1, passed: 1, bounced: 1, due: 2, waiting: 1 });
  });

  it("is monotonic: contacted >= replied >= meeting >= won, and every lead is somewhere", () => {
    expect(f.contacted).toBeGreaterThanOrEqual(f.replied);
    expect(f.replied).toBeGreaterThanOrEqual(f.meeting);
    expect(f.meeting).toBeGreaterThanOrEqual(f.won);
    expect(f.contacted).toBeLessThanOrEqual(f.leads);
  });

  it("computes the reply rate from contacted leads, or null before any outreach", () => {
    expect(replyRate(f)).toBe(50); // 4 of 8
    expect(replyRate(outreachFunnel([state()]))).toBeNull();
    expect(replyRate(outreachFunnel([]))).toBeNull();
  });
});
