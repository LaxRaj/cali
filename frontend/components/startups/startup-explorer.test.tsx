import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Profile } from "@/lib/data";
import { foldOutreach } from "@/lib/outreach";
import { resetOutreachStore } from "@/lib/outreach-store";
import { StartupExplorer } from "./startup-explorer";

const NOW = Date.now();
const iso = (daysAgo: number) => new Date(NOW - daysAgo * 86_400_000).toISOString().replace(/\.\d{3}Z$/, "+00:00");

function lead(name: string, over: Partial<Profile> = {}, sentDaysAgo?: number): Profile {
  const events = sentDaysAgo === undefined ? [] : [{ id: `${name}-s`, company: name, type: "sent" as const, at: iso(sentDaysAgo) }];
  return {
    slug: name.toLowerCase(),
    company_name: name,
    core_product: `${name} product`,
    likely_bottleneck: "",
    value_prop_pitch: "",
    tech_stack: ["Rust"],
    funding_stage: "seed",
    score: 70,
    discovered_at: iso(1),
    people: [],
    edges: [],
    decision: { action: "contact_now", urgency: "hot", priority: 50, reasons: [], next_step: `Email ${name}`, provider: "policy" },
    email_draft: { to: `hi@${name.toLowerCase()}.io`, to_source_url: "u", subject: "s", body: "b", mailto: "" },
    outreach: { ...foldOutreach(events, NOW), events },
    ...over,
  } as unknown as Profile;
}

const PROFILES = [lead("Fresh", { score: 90 }), lead("Overdue", { score: 60 }, 10), lead("NoMail", { score: 80, email_draft: undefined })];

beforeEach(() => {
  localStorage.clear();
  resetOutreachStore();
  window.history.replaceState(null, "", "/startups");
});

describe("StartupExplorer", () => {
  it("restores the view from the URL: outreach filter and table layout", () => {
    window.history.replaceState(null, "", "/startups?status=due&view=table");
    render(<StartupExplorer profiles={PROFILES} />);
    const table = screen.getByRole("table");
    expect(within(table).getByRole("link", { name: "Overdue" })).toBeInTheDocument();
    expect(within(table).queryByRole("link", { name: "Fresh" })).not.toBeInTheDocument();
    expect(screen.getByText("1 of 3 startups")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Due/ })).toHaveAttribute("aria-pressed", "true");
  });

  it("writes filter changes back to the URL and keeps clean views clean", () => {
    render(<StartupExplorer profiles={PROFILES} />);
    fireEvent.click(screen.getByRole("button", { name: "Rust" }));
    expect(window.location.search).toBe("?tag=Rust");
    fireEvent.click(screen.getByRole("button", { name: "name" }));
    expect(window.location.search).toBe("?tag=Rust&sort=name");
    fireEvent.click(screen.getByRole("button", { name: "Rust" }));
    fireEvent.click(screen.getByRole("button", { name: "priority" }));
    expect(window.location.search).toBe("");
  });

  it("sorts by priority by default and by score on request", () => {
    const hi = lead("Hi", { score: 10, decision: { ...PROFILES[0].decision!, priority: 99 } });
    const lo = lead("Lo", { score: 99, decision: { ...PROFILES[0].decision!, priority: 1 } });
    render(<StartupExplorer profiles={[lo, hi]} />);
    const order = () => screen.getAllByRole("link").map((l) => l.textContent).filter((t) => t === "Hi" || t === "Lo");
    expect(order()).toEqual(["Hi", "Lo"]);
    fireEvent.click(screen.getByRole("button", { name: "score" }));
    expect(order()).toEqual(["Lo", "Hi"]);
  });

  it("copies only published addresses and says how many leads had none", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    render(<StartupExplorer profiles={PROFILES} />);
    fireEvent.click(screen.getByRole("button", { name: "Copy emails" }));
    await waitFor(() => expect(writeText).toHaveBeenCalled());
    expect(writeText.mock.calls[0][0].split("\n").sort()).toEqual(["hi@fresh.io", "hi@overdue.io"]);
    expect(await screen.findByRole("status")).toHaveTextContent("Copied 2 published addresses (1 lead had none)");
  });
});
