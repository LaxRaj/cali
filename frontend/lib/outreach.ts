/**
 * Outreach log types and the fold that turns a lead's events into its current state.
 * Mirrors backend/outreach.py; both run backend/tests/fixtures/outreach_cases.json, so they cannot drift apart.
 */

export const EVENT_TYPES = [
  "sent",
  "replied",
  "bounced",
  "meeting",
  "won",
  "passed",
  "note",
  "snooze",
] as const;
export type EventType = (typeof EVENT_TYPES)[number];

export const PASS_REASONS = [
  "wrong_stage",
  "wrong_stack",
  "no_contact",
  "too_big",
  "not_relevant",
  "other",
] as const;

export const EVENT_FIELDS = [
  "id",
  "company",
  "type",
  "at",
  "channel",
  "subject",
  "to",
  "to_source_url",
  "thread_id",
  "note",
  "reason",
  "until",
] as const;

export type OutreachEvent = {
  id: string;
  company: string;
  type: EventType;
  at: string;
  channel?: string;
  subject?: string;
  to?: string;
  to_source_url?: string;
  thread_id?: string;
  note?: string;
  reason?: string;
  until?: string;
};

export type OutreachStatus =
  | "none"
  | "contacted"
  | "replied"
  | "bounced"
  | "meeting"
  | "won"
  | "passed";

export type OutreachState = {
  status: OutreachStatus;
  touches: number;
  last_contact: string;
  replied_at: string;
  next_due: string;
  overdue: boolean;
  snoozed: boolean;
  exhausted: boolean;
  last_to: string;
  last_subject: string;
  pass_reason: string;
};

const DAY = 86_400_000;
export const CADENCE_DAYS = [7, 7]; // wait after the 1st and 2nd touch
export const MAX_TOUCHES = 3;
export const REPLY_DAYS = 3;

/** Epoch ms of an ISO string; strings without a zone are UTC (as in the backend). */
export function parseTime(iso: string | undefined): number | null {
  if (!iso) return null;
  const zoned = /(Z|[+-]\d\d:?\d\d)$/.test(iso) ? iso : `${iso}Z`;
  const t = Date.parse(zoned);
  return Number.isNaN(t) ? null : t;
}

export function fmtTime(ms: number): string {
  return new Date(ms).toISOString().replace(/\.\d{3}Z$/, "+00:00");
}

export function isEvent(e: unknown): e is OutreachEvent {
  if (!e || typeof e !== "object") return false;
  const o = e as Record<string, unknown>;
  return (
    typeof o.id === "string" &&
    o.id !== "" &&
    typeof o.company === "string" &&
    o.company !== "" &&
    (EVENT_TYPES as readonly unknown[]).includes(o.type) &&
    typeof o.at === "string" &&
    parseTime(o.at) !== null
  );
}

export function foldOutreach(
  events: OutreachEvent[],
  nowMs: number,
): OutreachState {
  let status: OutreachStatus = "none";
  let touches = 0;
  let lastSent: number | null = null;
  let repliedAt: number | null = null;
  let lastTo = "";
  let lastSubject = "";
  let passReason = "";
  let snoozeUntil: number | null = null;

  const timed = events
    .map((e, i) => ({ t: parseTime(e.at), i, e }))
    .filter((x): x is { t: number; i: number; e: OutreachEvent } => x.t !== null)
    .sort((a, b) => a.t - b.t || a.i - b.i);

  for (const { t, e } of timed) {
    switch (e.type) {
      case "sent":
        touches += 1;
        lastSent = t;
        lastTo = e.to || lastTo;
        lastSubject = e.subject || lastSubject;
        if (status === "none" || status === "bounced" || status === "passed")
          status = "contacted";
        snoozeUntil = null;
        break;
      case "replied":
        repliedAt = t;
        if (status !== "meeting" && status !== "won") status = "replied";
        snoozeUntil = null;
        break;
      case "meeting":
        if (status !== "won") status = "meeting";
        break;
      case "won":
        status = "won";
        break;
      case "passed":
        status = "passed";
        passReason = e.reason ?? "";
        break;
      case "bounced":
        if (status === "none" || status === "contacted") status = "bounced";
        break;
      case "snooze":
        snoozeUntil = parseTime(e.until);
        break;
      default:
        break;
    }
  }

  let nextDue: number | null = null;
  let exhausted = false;
  if (status === "contacted" && lastSent !== null) {
    if (touches >= MAX_TOUCHES) exhausted = true;
    else
      nextDue =
        lastSent + CADENCE_DAYS[Math.min(touches, CADENCE_DAYS.length) - 1] * DAY;
  } else if (status === "replied") {
    const ref = Math.max(lastSent ?? -Infinity, repliedAt ?? -Infinity);
    nextDue = ref + REPLY_DAYS * DAY;
  }
  const snoozed =
    snoozeUntil !== null &&
    snoozeUntil > nowMs &&
    (status === "contacted" || status === "replied" || status === "none");
  if (snoozed && snoozeUntil !== null)
    nextDue = nextDue === null ? snoozeUntil : Math.max(nextDue, snoozeUntil);

  return {
    status,
    touches,
    last_contact: lastSent !== null ? fmtTime(lastSent) : "",
    replied_at: repliedAt !== null ? fmtTime(repliedAt) : "",
    next_due: nextDue !== null ? fmtTime(nextDue) : "",
    overdue: nextDue !== null && nextDue <= nowMs && !snoozed,
    snoozed,
    exhausted,
    last_to: lastTo,
    last_subject: lastSubject,
    pass_reason: status === "passed" ? passReason : "",
  };
}

/** Whole days from now until an ISO time (negative when past). */
export function daysUntil(iso: string, nowMs: number): number | null {
  const t = parseTime(iso);
  return t === null ? null : Math.round((t - nowMs) / DAY);
}

/** "due today", "due in 3d", "2d overdue" */
export function dueLabel(iso: string, nowMs: number): string {
  const d = daysUntil(iso, nowMs);
  if (d === null) return "";
  if (d === 0) return "due today";
  return d > 0 ? `due in ${d}d` : `${-d}d overdue`;
}
