import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Profile } from "@/lib/data";
import { QueueView, queueCsv } from "./queue-view";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

function lead(slug: string, action: string, priority: number, over: Partial<Profile> = {}): Profile {
  return {
    slug,
    company_name: slug.toUpperCase(),
    core_product: "Search",
    tech_stack: [],
    likely_bottleneck: "",
    value_prop_pitch: "Pitch.",
    is_relevant: true,
    source_url: "https://x",
    discovered_at: "2026-11-01T00:00:00+00:00",
    people: [],
    edges: [],
    decision: { action, urgency: "hot", priority, reasons: ["r"], next_step: `next ${slug}`, provider: "policy" },
    email_draft: { to: `hi@${slug}.io`, to_source_url: `https://${slug}.io`, subject: "s", body: `body ${slug}`, mailto: `mailto:hi@${slug}.io` },
    ...over,
  } as Profile;
}

const PROFILES = [
  lead("a", "contact_now", 50),
  lead("b", "contact_now", 90, { email_draft: { to: "", to_source_url: "", subject: "s", body: "b", mailto: "", needs_human: true, needs_human_reason: "nothing concrete" } }),
  lead("c", "review", 70),
  { ...lead("d", "watch", 10), decision: undefined } as Profile,
];

beforeEach(() => {
  window.history.replaceState(null, "", "/queue");
  push.mockReset();
});

describe("QueueView", () => {
  it("defaults to Contact now, ranked by priority, and counts match the list", () => {
    render(<QueueView profiles={PROFILES} />);
    const items = screen.getAllByRole("listitem").filter((li) => li.hasAttribute("data-row"));
    expect(items.map((li) => within(li).getByRole("link", { name: /^[A-Z]$/ }).textContent)).toEqual(["B", "A"]);
    expect(screen.getByRole("button", { name: /Contact now 2/ })).toBeInTheDocument();
    // the undecided profile is neither counted nor listed
    expect(screen.getByRole("button", { name: /All 3/ })).toBeInTheDocument();
  });

  it("has an explicit All filter and a Review filter, kept in the URL", () => {
    render(<QueueView profiles={PROFILES} />);
    fireEvent.click(screen.getByRole("button", { name: /Review 1/ }));
    expect(window.location.search).toBe("?action=review");
    expect(screen.getByText(/next c/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /All 3/ }));
    expect(screen.getByText("3 leads", { exact: false })).toBeInTheDocument();
  });

  it("uses the intent-aware drafted email and flags drafts that need a human", () => {
    render(<QueueView profiles={PROFILES} />);
    expect(screen.getByText("needs a human")).toBeInTheDocument();
    const email = screen.getByRole("link", { name: /✉ Email/ });
    expect(email.getAttribute("href")).toBe("mailto:hi@a.io");
  });

  it("j moves to the first lead and o opens it", () => {
    render(<QueueView profiles={PROFILES} />);
    fireEvent.keyDown(document, { key: "j" });
    fireEvent.keyDown(document, { key: "o" });
    expect(push).toHaveBeenCalledWith("/startups/b");
  });

  it("? opens the shortcut help", () => {
    render(<QueueView profiles={PROFILES} />);
    fireEvent.keyDown(document, { key: "?" });
    expect(screen.getByRole("dialog", { name: "Keyboard shortcuts" })).toBeInTheDocument();
  });

  it("exports the shown rows as CSV with the sourced address", () => {
    const csv = queueCsv([PROFILES[0]]);
    expect(csv.split("\r\n")[0]).toContain('"email","email_source"');
    expect(csv).toContain('"hi@a.io","https://a.io"');
  });
});
