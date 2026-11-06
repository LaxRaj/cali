import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Profile } from "@/lib/data";
import { filterProfiles, StartupExplorer, startupsCsv } from "./startup-explorer";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

function p(slug: string, over: Partial<Profile> = {}): Profile {
  return {
    slug,
    company_name: slug,
    core_product: "",
    tech_stack: [],
    likely_bottleneck: "",
    value_prop_pitch: "",
    is_relevant: true,
    source_url: "https://x.io",
    discovered_at: "2026-11-01T00:00:00+00:00",
    people: [],
    edges: [],
    ...over,
  } as Profile;
}

const PS = [
  p("Acme", { funding_stage: "pre‑Seed", score: 80, hq: "Berlin", qualified: true }),
  p("Beta", { funding_stage: "Pre-seed", score: 60, signals: [{ type: "hiring", source: "hn", url: "", roles: ["Founding Engineer"], role_kinds: [], posted_at: "", seen_at: "" }] }),
  p("Gamma", { funding_stage: "", score: 70 }),
];

beforeEach(() => window.history.replaceState(null, "", "/startups"));

describe("filterProfiles", () => {
  it("groups spelling variants of a stage and has an 'unknown' bucket", () => {
    expect(filterProfiles(PS, { stage: "pre-seed" }).map((x) => x.slug)).toEqual(["Acme", "Beta"]);
    expect(filterProfiles(PS, { stage: "unknown" }).map((x) => x.slug)).toEqual(["Gamma"]);
  });
  it("searches hq and hiring roles, every word must match", () => {
    expect(filterProfiles(PS, { q: "berlin" }).map((x) => x.slug)).toEqual(["Acme"]);
    expect(filterProfiles(PS, { q: "founding engineer" }).map((x) => x.slug)).toEqual(["Beta"]);
    expect(filterProfiles(PS, { q: "berlin founding" })).toEqual([]);
  });
  it("sorts by score by default and filters qualified", () => {
    expect(filterProfiles(PS, {}).map((x) => x.slug)).toEqual(["Acme", "Gamma", "Beta"]);
    expect(filterProfiles(PS, { qualified: true }).map((x) => x.slug)).toEqual(["Acme"]);
  });
});

describe("StartupExplorer", () => {
  it("shows one chip per normalised stage with counts, and keeps the filter in the URL", () => {
    render(<StartupExplorer profiles={PS} />);
    const chip = screen.getByRole("button", { name: "pre-seed 2" });
    expect(screen.getByRole("button", { name: "unknown 1" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Pre-seed/ })).toBeNull();
    fireEvent.click(chip);
    expect(window.location.search).toBe("?stage=pre-seed");
    expect(screen.getByText(/2 of 3 startups/)).toBeInTheDocument();
  });
  it("reads filters from the URL on load", () => {
    window.history.replaceState(null, "", "/startups?q=berlin");
    render(<StartupExplorer profiles={PS} />);
    expect(screen.getByText(/1 of 3 startups/)).toBeInTheDocument();
  });
});

describe("startupsCsv", () => {
  it("writes the normalised stage", () => {
    expect(startupsCsv([PS[0]])).toContain('"Acme","80","yes","pre-seed","Berlin"');
  });
});
