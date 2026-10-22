import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Profile } from "./data";
import { localWriteAllowed, eventLine } from "./outreach-local";
import {
  addEvent,
  buildOutreach,
  exportJson,
  getSnapshot,
  logEvent,
  mergeEvents,
  newEvent,
  parseImport,
  pruneSynced,
  removeEvent,
  resetOutreachStore,
} from "./outreach-store";

const NOW = Date.parse("2026-10-20T09:00:00Z");

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
  resetOutreachStore();
});

const profile = (name: string, events: ReturnType<typeof newEvent>[] = []) =>
  ({
    slug: name.toLowerCase(),
    company_name: name,
    outreach: events.length
      ? { status: "contacted", touches: 1, last_contact: events[0].at, replied_at: "", next_due: "", overdue: false, snoozed: false, exhausted: false, last_to: "", last_subject: "", pass_reason: "", events }
      : undefined,
  }) as unknown as Profile;

describe("browser overlay", () => {
  it("adds, reads back and removes events, ignoring corrupt storage", () => {
    const e = newEvent("Acme", "sent", { subject: "Hi", to: "hi@acme.io", note: "" });
    expect(e.subject).toBe("Hi");
    expect("note" in e).toBe(false);
    addEvent(e);
    expect(getSnapshot().map((x) => x.id)).toEqual([e.id]);
    expect(getSnapshot()).toBe(getSnapshot()); // stable reference between reads
    removeEvent(e.id);
    expect(getSnapshot()).toEqual([]);
    localStorage.setItem("cali.outreach.v1", "{not json");
    expect(getSnapshot()).toEqual([]);
    localStorage.setItem("cali.outreach.v1", JSON.stringify([{ id: "x", type: "sent" }, e]));
    expect(getSnapshot().map((x) => x.id)).toEqual([e.id]); // invalid rows dropped
  });

  it("keeps working in memory when localStorage refuses writes", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("quota");
    });
    const e = newEvent("Acme", "sent");
    addEvent(e);
    expect(getSnapshot().map((x) => x.id)).toEqual([e.id]);
  });

  it("prunes events the build already contains", () => {
    const a = newEvent("Acme", "sent");
    const b = newEvent("Acme", "replied");
    addEvent(a);
    addEvent(b);
    pruneSynced(new Set([a.id]));
    expect(getSnapshot().map((x) => x.id)).toEqual([b.id]);
  });

  it("logEvent saves in the browser and reports whether the local log took it", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true }));
    expect(await logEvent(newEvent("Acme", "sent"))).toBe("local");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));
    expect(await logEvent(newEvent("Acme", "replied"))).toBe("browser");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    expect(await logEvent(newEvent("Acme", "note"))).toBe("browser");
    expect(getSnapshot()).toHaveLength(3);
  });
});

describe("merge, import and export", () => {
  it("merges by id and orders by time", () => {
    const a = { ...newEvent("Acme", "sent"), id: "a", at: "2026-10-02T09:00:00+00:00" };
    const b = { ...newEvent("Acme", "replied"), id: "b", at: "2026-10-01T09:00:00+00:00" };
    expect(mergeEvents([a], [a, b]).map((e) => e.id)).toEqual(["b", "a"]);
  });

  it("round-trips an export and skips junk on import", () => {
    const e = newEvent("Acme", "sent");
    const text = exportJson([e], new Date("2026-10-20T00:00:00Z"));
    expect(JSON.parse(text).version).toBe(1);
    expect(parseImport(text)).toEqual({ events: [e], skipped: 0 });
    expect(parseImport(JSON.stringify([e, { id: "x" }]))).toEqual({ events: [e], skipped: 1 });
    expect(parseImport("nope")).toEqual({ events: [], skipped: 0 });
  });
});

describe("buildOutreach", () => {
  it("uses the build-time state until the clock is known, then folds baked + browser events", () => {
    const sent = { ...newEvent("Acme", "sent"), id: "s1", at: "2026-10-01T09:00:00+00:00" };
    const acme = profile("Acme", [sent]);
    const quiet = profile("Quiet");
    expect(buildOutreach([acme, quiet], [], null).get("acme")?.state.status).toBe("contacted");
    expect(buildOutreach([acme, quiet], [], null).get("quiet")?.state.status).toBe("none");
    const replied = { ...newEvent("acme", "replied"), id: "r1", at: "2026-10-03T09:00:00+00:00" };
    const got = buildOutreach([acme, quiet], [replied], NOW).get("acme")!;
    expect(got.state).toMatchObject({ status: "replied", touches: 1, overdue: true });
    expect(got.events.map((e) => e.id)).toEqual(["s1", "r1"]);
    expect(buildOutreach([acme], [], NOW).get("acme")?.state.overdue).toBe(true); // 7 days passed
  });
});

describe("local write guard", () => {
  const ok = { CALI_LOCAL: "1" };
  it("needs CALI_LOCAL=1, a localhost host and a same-origin request", () => {
    expect(localWriteAllowed(ok, "localhost:3000", "http://localhost:3000")).toBe(true);
    expect(localWriteAllowed(ok, "127.0.0.1:3000", "http://127.0.0.1:3000")).toBe(true);
    expect(localWriteAllowed({}, "localhost:3000", "http://localhost:3000")).toBe(false);
    expect(localWriteAllowed({ ...ok, CALI_DEMO: "1" }, "localhost:3000", "http://localhost:3000")).toBe(false);
    expect(localWriteAllowed(ok, "cali.vercel.app", "https://cali.vercel.app")).toBe(false);
    expect(localWriteAllowed(ok, "localhost:3000", "https://evil.example")).toBe(false);
    expect(localWriteAllowed(ok, "localhost:3000", null)).toBe(false);
    expect(localWriteAllowed(ok, null, "http://localhost:3000")).toBe(false);
  });

  it("writes one clean line per valid event and nothing for bad input", () => {
    const e = { ...newEvent("Acme", "sent", { subject: "Hi" }), evil: "<x>" };
    const line = eventLine(e)!;
    expect(line.includes("\n")).toBe(false);
    expect(JSON.parse(line)).toMatchObject({ company: "Acme", type: "sent", subject: "Hi" });
    expect(JSON.parse(line).evil).toBeUndefined();
    expect(eventLine({ id: "x" })).toBeNull();
  });
});
