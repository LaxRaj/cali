import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import {
  dueLabel,
  foldOutreach,
  isEvent,
  parseTime,
  type OutreachEvent,
  type OutreachState,
} from "./outreach";

type Case = {
  name: string;
  now: string;
  events: OutreachEvent[];
  expected: Partial<OutreachState>;
};

// The same file backend/tests/test_outreach.py runs: the two implementations must agree on every case.
const CASES: Case[] = JSON.parse(
  fs.readFileSync(
    path.join(__dirname, "../../backend/tests/fixtures/outreach_cases.json"),
    "utf8",
  ),
);

describe("foldOutreach matches the backend contract", () => {
  it.each(CASES.map((c) => [c.name, c] as const))("%s", (_name, c) => {
    const got = foldOutreach(c.events, Date.parse(c.now));
    const picked = Object.fromEntries(
      Object.keys(c.expected).map((k) => [k, got[k as keyof OutreachState]]),
    );
    expect(picked).toEqual(c.expected);
  });
});

describe("helpers", () => {
  it("treats a time without a zone as UTC and rejects garbage", () => {
    expect(parseTime("2026-10-01T09:00:00")).toBe(Date.parse("2026-10-01T09:00:00Z"));
    expect(parseTime("nope")).toBeNull();
    expect(parseTime("")).toBeNull();
  });

  it("validates events", () => {
    const ok = { id: "a", company: "Acme", type: "sent", at: "2026-10-01T09:00:00+00:00" };
    expect(isEvent(ok)).toBe(true);
    expect(isEvent({ ...ok, type: "teleported" })).toBe(false);
    expect(isEvent({ ...ok, at: "later" })).toBe(false);
    expect(isEvent({ ...ok, id: "" })).toBe(false);
    expect(isEvent(null)).toBe(false);
  });

  it("labels due dates", () => {
    const now = Date.parse("2026-10-10T09:00:00Z");
    expect(dueLabel("2026-10-10T09:00:00+00:00", now)).toBe("due today");
    expect(dueLabel("2026-10-13T09:00:00+00:00", now)).toBe("due in 3d");
    expect(dueLabel("2026-10-08T09:00:00+00:00", now)).toBe("2d overdue");
    expect(dueLabel("", now)).toBe("");
  });
});
