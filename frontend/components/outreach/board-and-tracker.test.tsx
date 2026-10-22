import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Profile } from "@/lib/data";
import { foldOutreach, type OutreachEvent } from "@/lib/outreach";
import { addEvent, newEvent, resetOutreachStore } from "@/lib/outreach-store";
import { OutreachBoard } from "./outreach-board";
import { Tracker } from "./tracker";

const NOW = Date.now();
const iso = (daysAgo: number) => new Date(NOW - daysAgo * 86_400_000).toISOString().replace(/\.\d{3}Z$/, "+00:00");

function lead(name: string, events: OutreachEvent[] = [], over: Partial<Profile> = {}): Profile {
  const state = foldOutreach(events, NOW);
  return {
    slug: name.toLowerCase(),
    company_name: name,
    core_product: `${name} product`,
    value_prop_pitch: "Pitch.",
    score: 80,
    people: [],
    decision: { action: "contact_now", urgency: "hot", priority: 70, reasons: [], next_step: `Email ${name}`, provider: "policy" },
    email_draft: { to: `hi@${name.toLowerCase()}.io`, to_source_url: "u", subject: `${name}: hello`, body: "Body", mailto: "mailto:x" },
    outreach: { ...state, events },
    ...over,
  } as unknown as Profile;
}
const sent = (name: string, daysAgo: number, id: string): OutreachEvent => ({ id, company: name, type: "sent", at: iso(daysAgo), subject: `${name}: hello` });

beforeEach(() => {
  localStorage.clear();
  resetOutreachStore();
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));
});

const PROFILES = () => [
  lead("Fresh"),
  lead("Overdue", [sent("Overdue", 10, "o1")]),
  lead("Waiting", [sent("Waiting", 2, "w1")]),
  lead("Replied", [sent("Replied", 8, "r1"), { id: "r2", company: "Replied", type: "replied", at: iso(7) }]),
];

describe("OutreachBoard", () => {
  it("counts what is due and puts the most overdue lead first in Do today", () => {
    render(<OutreachBoard profiles={PROFILES()} />);
    const stat = (label: string) => screen.getByText(label).parentElement!;
    expect(stat("Due now")).toHaveTextContent("2"); // Overdue + Replied (unanswered)
    expect(stat("Ready to contact")).toHaveTextContent("1");
    expect(stat("Waiting on them")).toHaveTextContent("1");
    expect(stat("Reply rate")).toHaveTextContent("33%"); // 1 replied of 3 contacted (Fresh is not contacted)
  });

  it("lists due leads before fresh ones, most overdue first", () => {
    render(<OutreachBoard profiles={PROFILES()} />);
    const panel = screen.getByRole("heading", { name: /Do today/ }).closest("section")!;
    const names = within(panel)
      .getAllByRole("link")
      .map((l) => l.textContent)
      .filter((t) => ["Fresh", "Overdue", "Replied", "Waiting"].includes(t ?? ""));
    // Replied: their reply (7 days ago) was due an answer 4 days ago; Overdue: follow-up due 3 days ago; Fresh: not contacted.
    expect(names).toEqual(["Replied", "Overdue", "Fresh"]);
  });

  it("updates as soon as you log a send", async () => {
    render(<OutreachBoard profiles={[lead("Fresh")]} />);
    expect(screen.getByText("Ready to contact").parentElement).toHaveTextContent("1");
    fireEvent.click(screen.getByRole("button", { name: "Mark sent" }));
    await waitFor(() => expect(screen.getByText("Waiting on them").parentElement).toHaveTextContent("1"));
    expect(screen.getByText("Ready to contact").parentElement).toHaveTextContent("0");
  });
});

describe("Tracker", () => {
  it("explains an empty tracker", () => {
    render(<Tracker profiles={[lead("Fresh")]} />);
    expect(screen.getByText("No outreach yet")).toBeInTheDocument();
  });

  it("puts leads in their stage columns and shows recent activity", () => {
    render(<Tracker profiles={PROFILES()} />);
    expect(screen.getByRole("heading", { name: /Contacted · 2/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Replied · 1/ })).toBeInTheDocument();
    const feed = screen.getByRole("heading", { name: /Recent activity/ }).closest("section")!;
    expect(within(feed).getAllByRole("listitem")[0]).toHaveTextContent("Waiting"); // newest event first
  });

  it("counts events logged in the browser and offers to export them", async () => {
    render(<Tracker profiles={[lead("Fresh")]} />);
    expect(screen.getByRole("button", { name: "Export events" })).toBeDisabled();
    addEvent(newEvent("Fresh", "sent"));
    await waitFor(() => expect(screen.getByRole("button", { name: "Export events" })).toBeEnabled());
    expect(screen.getByText(/saved in this browser only/)).toHaveTextContent("1 event");
  });
});
