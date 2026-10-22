import type { OutreachState } from "./outreach";

export type OutreachFunnel = {
  leads: number;
  contacted: number;
  replied: number;
  meeting: number;
  won: number;
  passed: number;
  bounced: number;
  /** Open conversations that are overdue / not yet due. */
  due: number;
  waiting: number;
};

const ENGAGED = new Set(["replied", "meeting", "won"]);

/**
 * Counts for the outreach pipeline. Each stage includes everything after it (a lead that reached a meeting also
 * replied and was contacted, even if the send was never logged), so contacted >= replied >= meeting >= won.
 */
export function outreachFunnel(states: OutreachState[]): OutreachFunnel {
  const f: OutreachFunnel = { leads: states.length, contacted: 0, replied: 0, meeting: 0, won: 0, passed: 0, bounced: 0, due: 0, waiting: 0 };
  for (const s of states) {
    const replied = ENGAGED.has(s.status) || s.replied_at !== "";
    const meeting = s.status === "meeting" || s.status === "won";
    if (s.touches > 0 || replied) f.contacted += 1;
    if (replied) f.replied += 1;
    if (meeting) f.meeting += 1;
    if (s.status === "won") f.won += 1;
    if (s.status === "passed") f.passed += 1;
    if (s.status === "bounced") f.bounced += 1;
    if (s.status === "contacted" || s.status === "replied") {
      if (s.overdue) f.due += 1;
      else f.waiting += 1;
    }
  }
  return f;
}

/** Share of contacted leads that replied, 0-100, or null before anyone is contacted. */
export function replyRate(f: OutreachFunnel): number | null {
  return f.contacted > 0 ? Math.round((f.replied / f.contacted) * 100) : null;
}
