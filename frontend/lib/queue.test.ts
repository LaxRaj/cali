import { describe, expect, it } from "vitest";
import type { Profile } from "./data";
import { foldOutreach, type OutreachEvent } from "./outreach";
import { bucketFor, fallbackRoute, mailtoFor, nextStep, sortLeads } from "./queue";

const NOW = Date.parse("2026-10-20T09:00:00Z");
const ev = (id: string, type: OutreachEvent["type"], at: string, extra: Partial<OutreachEvent> = {}): OutreachEvent => ({ id, company: "Acme", type, at, ...extra });
const lead = (over: Partial<Profile> = {}): Profile =>
  ({
    slug: "acme",
    company_name: "Acme",
    value_prop_pitch: "We cut review time.",
    people: [{ name: "Ada Lovelace", role: "CEO", org: "Acme", evidence: "" }],
    decision: { action: "contact_now", urgency: "hot", priority: 80, reasons: [], next_step: "Email hi@acme.io", provider: "policy" },
    email_draft: { to: "hi@acme.io", to_source_url: "u", subject: "Acme: a thought", body: "b", mailto: "mailto:hi@acme.io?subject=x" },
    ...over,
  }) as Profile;
const sent = (daysAgo: number, id = "s") => ev(id, "sent", new Date(NOW - daysAgo * 86_400_000).toISOString(), { subject: "Acme: a thought" });

describe("bucketFor", () => {
  it("uses the baked decision until you touch the lead, then your own state", () => {
    expect(bucketFor(lead(), foldOutreach([], NOW))).toBe("contact_now");
    expect(bucketFor(lead(), foldOutreach([sent(2)], NOW))).toBe("waiting");
    expect(bucketFor(lead(), foldOutreach([sent(8)], NOW))).toBe("due");
    expect(bucketFor(lead(), foldOutreach([sent(8), ev("b", "bounced", new Date(NOW - 7 * 86_400_000).toISOString())], NOW))).toBe("enrich_more");
    expect(bucketFor(lead(), foldOutreach([sent(8), ev("p", "passed", new Date(NOW - 86_400_000).toISOString())], NOW))).toBe("done");
    expect(bucketFor(lead({ decision: { ...lead().decision!, action: "skip" } }), foldOutreach([], NOW))).toBe("skip");
  });

  it("a snoozed fresh lead waits and a snoozed follow-up is not due", () => {
    const until = new Date(NOW + 5 * 86_400_000).toISOString();
    const snooze = ev("z", "snooze", new Date(NOW).toISOString(), { until });
    expect(bucketFor(lead(), foldOutreach([snooze], NOW))).toBe("watch");
    expect(bucketFor(lead(), foldOutreach([sent(9), snooze], NOW))).toBe("waiting");
  });
});

describe("nextStep", () => {
  it("says what to do in step with the log", () => {
    const due = foldOutreach([sent(8)], NOW);
    expect(nextStep(lead(), due, "due", NOW)).toMatch(/^Follow up \(touch 2\): no reply since 2026-10-12/);
    const replied = foldOutreach([sent(10), ev("r", "replied", new Date(NOW - 5 * 86_400_000).toISOString())], NOW);
    expect(nextStep(lead(), replied, "due", NOW)).toMatch(/^Reply: they answered on 2026-10-15/);
    expect(nextStep(lead(), foldOutreach([sent(2)], NOW), "waiting", NOW)).toBe("Waiting on their reply (due in 5d)");
    expect(nextStep(lead(), foldOutreach([sent(2)], NOW), "waiting", null)).toBe("Waiting on their reply");
    expect(nextStep(lead(), foldOutreach([], NOW), "contact_now", NOW)).toBe("Email hi@acme.io");
  });
});

describe("sortLeads", () => {
  it("puts due leads first (most overdue on top), then fresh leads by priority", () => {
    const row = (name: string, daysAgo: number | null, priority: number) => {
      const p = lead({ slug: name, decision: { ...lead().decision!, priority } });
      const s = foldOutreach(daysAgo === null ? [] : [sent(daysAgo)], NOW);
      return { p, s, bucket: bucketFor(p, s) };
    };
    const out = sortLeads([row("fresh", null, 99), row("late", 20, 10), row("later", 30, 10), row("mid", null, 50)]);
    expect(out.map((r) => r.p.slug)).toEqual(["later", "late", "fresh", "mid"]);
    expect(sortLeads([row("mid", null, 50), row("fresh", null, 99)]).map((r) => r.p.slug)).toEqual(["fresh", "mid"]);
  });
});

describe("routes", () => {
  it("first touch uses the drafted email; later touches reply on the same subject", () => {
    expect(mailtoFor(lead(), foldOutreach([], NOW))).toBe("mailto:hi@acme.io?subject=x");
    const m = mailtoFor(lead(), foldOutreach([sent(8)], NOW))!;
    expect(m).toContain("mailto:hi%40acme.io?subject=Re%3A%20Acme%3A%20a%20thought");
    expect(decodeURIComponent(m)).toContain("Hi Ada,");
    expect(mailtoFor(lead({ email_draft: undefined }), foldOutreach([], NOW))).toBeNull();
  });

  it("falls back to a leader's profile, then the contact page", () => {
    const withLi = lead({ people: [{ name: "Ada L", role: "CEO", org: "Acme", evidence: "", linkedin: "https://linkedin.com/in/ada" }] });
    expect(fallbackRoute(withLi)).toEqual({ label: "Ada L (LinkedIn)", href: "https://linkedin.com/in/ada" });
    expect(fallbackRoute(lead({ contact: { contact_page: "https://acme.io/contact" } }))).toEqual({ label: "contact page", href: "https://acme.io/contact" });
    expect(fallbackRoute(lead())).toBeNull();
  });
});
