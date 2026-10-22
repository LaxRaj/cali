import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Profile } from "@/lib/data";
import { resetOutreachStore } from "@/lib/outreach-store";
import { QueueView } from "./queue-view";

const NOW = Date.now();
const iso = (daysAgo: number) => new Date(NOW - daysAgo * 86_400_000).toISOString().replace(/\.\d{3}Z$/, "+00:00");

function lead(name: string, over: Partial<Profile> = {}): Profile {
  return {
    slug: name.toLowerCase(),
    company_name: name,
    core_product: `${name} product`,
    value_prop_pitch: "We cut review time.",
    score: 80,
    people: [{ name: `${name} Founder`, role: "CEO", org: name, evidence: "" }],
    decision: { action: "contact_now", urgency: "hot", priority: 70, reasons: [], next_step: `Email ${name}`, provider: "policy" },
    email_draft: { to: `hi@${name.toLowerCase()}.io`, to_source_url: "u", subject: `${name}: a thought`, body: "Body", mailto: `mailto:hi@${name.toLowerCase()}.io` },
    ...over,
  } as unknown as Profile;
}

const chased = lead("Chased", {
  outreach: {
    status: "contacted", touches: 1, last_contact: iso(9), replied_at: "", next_due: iso(2), overdue: true, snoozed: false, exhausted: false, last_to: "hi@chased.io", last_subject: "Chased: a thought", pass_reason: "",
    events: [{ id: "c1", company: "Chased", type: "sent", at: iso(9), subject: "Chased: a thought", to: "hi@chased.io" }],
  },
});

beforeEach(() => {
  localStorage.clear();
  resetOutreachStore();
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));
});

describe("QueueView", () => {
  it("opens on the Due bucket when follow-ups are waiting, ahead of fresh leads", () => {
    render(<QueueView profiles={[lead("Fresh"), chased]} />);
    const due = screen.getByRole("button", { name: /^Due/ });
    expect(due).toHaveAttribute("aria-pressed", "true");
    expect(due).toHaveTextContent("1");
    expect(screen.getByRole("link", { name: "Chased" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Fresh" })).not.toBeInTheDocument();
    expect(screen.getByText(/Follow up \(touch 2\)/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Write follow-up/ }).getAttribute("href")).toContain("Re%3A%20Chased%3A%20a%20thought");
  });

  it("opens on Contact now when nothing is due and offers a way in for leads without an email", () => {
    const noEmail = lead("NoEmail", {
      email_draft: undefined,
      people: [{ name: "Ada L", role: "CEO", org: "NoEmail", evidence: "", linkedin: "https://linkedin.com/in/ada" }],
    });
    render(<QueueView profiles={[lead("Fresh"), noEmail]} />);
    expect(screen.getByRole("button", { name: /^Contact now/ })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("link", { name: /Ada L \(LinkedIn\)/ })).toHaveAttribute("href", "https://linkedin.com/in/ada");
    expect(screen.getByRole("link", { name: /Open email/ })).toBeInTheDocument();
  });

  it("moves a lead to Waiting as soon as you mark it sent", async () => {
    render(<QueueView profiles={[lead("Fresh")]} />);
    fireEvent.click(screen.getByRole("button", { name: "Mark sent" }));
    await waitFor(() => expect(screen.getByRole("button", { name: /^Waiting/ })).toHaveTextContent("1"));
    expect(screen.getByRole("button", { name: /^Contact now/ })).toHaveTextContent("0");
    fireEvent.click(screen.getByRole("button", { name: /^Waiting/ }));
    expect(screen.getByText(/Waiting on their reply/)).toBeInTheDocument();
  });

  it("filters the bucket by search and explains an empty bucket", () => {
    render(<QueueView profiles={[lead("Fresh"), lead("Other")]} />);
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "oth" } });
    const list = screen.getByRole("list");
    expect(within(list).getAllByRole("listitem")).toHaveLength(1);
    expect(screen.getByRole("link", { name: "Other" })).toBeInTheDocument();
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "zzz" } });
    expect(screen.getByText(/Nothing matches that search/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /^Done/ }));
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "" } });
    expect(screen.getByText(/No meetings, wins or passes/)).toBeInTheDocument();
  });
});
