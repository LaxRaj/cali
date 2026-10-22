import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Profile } from "@/lib/data";
import { foldOutreach, type OutreachEvent } from "@/lib/outreach";
import { getSnapshot, resetOutreachStore } from "@/lib/outreach-store";
import { StatusControl } from "./status-control";
import { StatusPill } from "./status-pill";
import { Timeline } from "./timeline";

const NOW = Date.parse("2026-10-20T09:00:00Z");
const ev = (id: string, type: OutreachEvent["type"], at: string, extra: Partial<OutreachEvent> = {}): OutreachEvent => ({
  id,
  company: "Acme",
  type,
  at,
  ...extra,
});

const profile = {
  slug: "acme",
  company_name: "Acme",
  email_draft: { to: "hi@acme.io", to_source_url: "https://acme.io/contact", subject: "Acme: a thought", body: "x", mailto: "" },
} as unknown as Profile;

beforeEach(() => {
  localStorage.clear();
  resetOutreachStore();
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));
});

describe("StatusPill", () => {
  it("shows the status, touches and an overdue label once the clock is known", () => {
    const state = foldOutreach([ev("a", "sent", "2026-10-01T09:00:00+00:00"), ev("b", "sent", "2026-10-02T09:00:00+00:00")], NOW);
    const { rerender } = render(<StatusPill state={state} nowMs={null} />);
    expect(screen.getByText(/contacted · 2 touches/)).toBeInTheDocument();
    expect(screen.queryByText(/overdue/)).not.toBeInTheDocument(); // no clock during hydration
    rerender(<StatusPill state={state} nowMs={NOW} />);
    expect(screen.getByText("11d overdue")).toBeInTheDocument(); // 2nd send on Oct 2 + 7 days = due Oct 9
  });

  it("shows nothing about due dates for closed leads", () => {
    const state = foldOutreach([ev("a", "sent", "2026-10-01T09:00:00+00:00"), ev("b", "passed", "2026-10-02T09:00:00+00:00")], NOW);
    render(<StatusPill state={state} nowMs={NOW} />);
    expect(screen.getByText("passed")).toBeInTheDocument();
    expect(screen.queryByText(/due|overdue/)).not.toBeInTheDocument();
  });
});

describe("StatusControl", () => {
  it("logs a send with the draft's subject and published address, and offers undo when only saved in the browser", async () => {
    render(<StatusControl profile={profile} state={foldOutreach([], NOW)} />);
    expect(screen.queryByRole("button", { name: "They replied" })).not.toBeInTheDocument(); // nothing sent yet
    fireEvent.click(screen.getByRole("button", { name: "I sent this" }));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("saved in this browser"));
    expect(getSnapshot()).toMatchObject([
      { company: "Acme", type: "sent", channel: "email", subject: "Acme: a thought", to: "hi@acme.io", to_source_url: "https://acme.io/contact" },
    ]);
    fireEvent.click(screen.getByRole("button", { name: "undo" }));
    expect(getSnapshot()).toEqual([]);
  });

  it("says so when the local backend log took the event", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true }));
    render(<StatusControl profile={profile} state={foldOutreach([], NOW)} />);
    fireEvent.click(screen.getByRole("button", { name: "I sent this" }));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("backend/data/outreach.jsonl"));
    expect(screen.queryByRole("button", { name: "undo" })).not.toBeInTheDocument();
  });

  it("offers follow-ups, replies and a pass reason after a send", async () => {
    const state = foldOutreach([ev("a", "sent", "2026-10-01T09:00:00+00:00")], NOW);
    render(<StatusControl profile={profile} state={state} />);
    expect(screen.getByRole("button", { name: "Sent a follow-up" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Pass" }));
    fireEvent.click(screen.getByRole("button", { name: "wrong stage" }));
    await waitFor(() => expect(getSnapshot()).toMatchObject([{ type: "passed", reason: "wrong_stage" }]));
  });

  it("snoozes for a number of days", async () => {
    render(<StatusControl profile={profile} state={foldOutreach([ev("a", "sent", "2026-10-01T09:00:00+00:00")], NOW)} />);
    fireEvent.click(screen.getByRole("button", { name: "Snooze" }));
    fireEvent.click(screen.getByRole("button", { name: "7 days" }));
    await waitFor(() => expect(getSnapshot()[0]).toMatchObject({ type: "snooze" }));
    expect(getSnapshot()[0].until).toMatch(/\+00:00$/);
  });

  it("only offers Won after a meeting and nothing to close a won lead", () => {
    const meeting = foldOutreach([ev("a", "sent", "2026-10-01T09:00:00+00:00"), ev("b", "meeting", "2026-10-03T09:00:00+00:00")], NOW);
    const { unmount } = render(<StatusControl profile={profile} state={meeting} />);
    expect(screen.getByRole("button", { name: "Won" })).toBeInTheDocument();
    unmount();
    const won = foldOutreach([ev("a", "won", "2026-10-03T09:00:00+00:00")], NOW);
    render(<StatusControl profile={profile} state={won} />);
    expect(screen.queryByRole("button", { name: "Pass" })).not.toBeInTheDocument();
  });
});

describe("Timeline", () => {
  it("lists events newest first with the published source of the address", () => {
    render(
      <Timeline
        events={[
          ev("a", "sent", "2026-10-01T09:00:00+00:00", { subject: "Hi", to: "hi@acme.io", to_source_url: "https://acme.io/contact" }),
          ev("b", "replied", "2026-10-03T09:00:00+00:00"),
        ]}
      />,
    );
    const items = screen.getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("they replied");
    expect(items[1]).toHaveTextContent("“Hi”");
    expect(screen.getByRole("link", { name: /published here/ })).toHaveAttribute("href", "https://acme.io/contact");
  });

  it("explains an empty history", () => {
    render(<Timeline events={[]} />);
    expect(screen.getByText(/Nothing logged yet/)).toBeInTheDocument();
  });
});
