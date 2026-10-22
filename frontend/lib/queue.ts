import type { Profile } from "./data";
import { dueLabel, parseTime, type OutreachState } from "./outreach";

/**
 * Where a lead sits in your day. Derived from your outreach state (which reacts to what you just logged) and, for leads
 * you haven't touched, from the build-time decision.
 */
export type Bucket = "due" | "contact_now" | "waiting" | "enrich_more" | "watch" | "done" | "skip";

export const BUCKETS: { key: Bucket; label: string; hint: string }[] = [
  { key: "due", label: "Due", hint: "follow-ups and replies that are waiting on you" },
  { key: "contact_now", label: "Contact now", hint: "fresh, strong fit, a published way in" },
  { key: "waiting", label: "Waiting", hint: "you wrote; give them time" },
  { key: "enrich_more", label: "Enrich", hint: "needs a contact route" },
  { key: "watch", label: "Watch", hint: "not yet" },
  { key: "done", label: "Done", hint: "meeting, won or passed" },
  { key: "skip", label: "Skip", hint: "weak fit" },
];

export function bucketFor(p: Profile, s: OutreachState): Bucket {
  switch (s.status) {
    case "passed":
    case "won":
    case "meeting":
      return "done";
    case "bounced":
      return "enrich_more";
    case "contacted":
    case "replied":
      return s.overdue ? "due" : "waiting";
    default: {
      if (s.snoozed) return "watch";
      const a = p.decision?.action;
      if (a === "contact_now" || a === "enrich_more" || a === "skip") return a;
      if (a === "follow_up") return "contact_now"; // baked follow-up without a log: treat as actionable
      return "watch";
    }
  }
}

const day = (iso: string) => iso.slice(0, 10);

/** One line saying what to do, kept in step with the logged state. */
export function nextStep(p: Profile, s: OutreachState, bucket: Bucket, nowMs: number | null): string {
  if (bucket === "due") {
    return s.status === "replied"
      ? `Reply: they answered on ${day(s.replied_at)} and it has been waiting`
      : `Follow up (touch ${s.touches + 1}): no reply since ${day(s.last_contact)}`;
  }
  if (bucket === "waiting") {
    if (s.snoozed) return `Snoozed until ${day(s.next_due)}`;
    if (s.exhausted) return "No reply after several touches: leave it for now";
    const due = nowMs !== null && s.next_due ? ` (${dueLabel(s.next_due, nowMs)})` : "";
    return (s.status === "replied" ? "Continue the conversation" : "Waiting on their reply") + due;
  }
  if (bucket === "done") return "No action needed";
  if (bucket === "enrich_more" && s.status === "bounced") return "Your email bounced: find another published contact route";
  return p.decision?.next_step ?? "Review";
}

/** Buckets in the order of your day (due first), then most overdue first within "due" and highest priority within the rest. */
export function sortLeads<T extends { p: Profile; s: OutreachState; bucket: Bucket }>(rows: T[]): T[] {
  const rank = (b: Bucket) => BUCKETS.findIndex((x) => x.key === b);
  return [...rows].sort((a, b) => {
    if (a.bucket !== b.bucket) return rank(a.bucket) - rank(b.bucket);
    if (a.bucket === "due") return (parseTime(a.s.next_due) ?? 0) - (parseTime(b.s.next_due) ?? 0);
    return (b.p.decision?.priority ?? 0) - (a.p.decision?.priority ?? 0);
  });
}

const firstName = (p: Profile) => {
  const lead = p.people.find((x) => /founder|ceo|cto|chief/i.test(x.role)) ?? p.people[0];
  return lead ? lead.name.split(" ")[0] : null;
};

/** mailto for the right message: the drafted first email, or a short follow-up on the same thread subject. */
export function mailtoFor(p: Profile, s: OutreachState): string | null {
  const draft = p.email_draft;
  if (!draft?.to) return null;
  if (s.touches === 0 && s.status === "none") return draft.mailto || null;
  const subject = `Re: ${s.last_subject || draft.subject}`.replace(/^Re: Re: /, "Re: ");
  const body = `Hi ${firstName(p) ?? `${p.company_name} team`},\n\nFloating this back up in case it got buried.\n\n${p.value_prop_pitch}\n`;
  return `mailto:${encodeURIComponent(draft.to)}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
}

/** Best way in when there is no published email: a leader's profile, then the contact page, else null. */
export function fallbackRoute(p: Profile): { label: string; href: string } | null {
  const lead = p.people.find((x) => /founder|ceo|cto|chief/i.test(x.role)) ?? p.people[0];
  const profile = lead && (lead.linkedin || lead.twitter || lead.github);
  if (lead && profile) return { label: `${lead.name} (${lead.linkedin ? "LinkedIn" : lead.twitter ? "X" : "GitHub"})`, href: profile };
  if (p.contact?.contact_page) return { label: "contact page", href: p.contact.contact_page };
  return null;
}
