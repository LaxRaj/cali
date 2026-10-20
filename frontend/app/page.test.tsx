import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Profile, RunSummary } from "@/lib/data";

const state = vi.hoisted(() => ({
  runs: [] as RunSummary[],
  profiles: [] as Profile[],
}));

vi.mock("@/lib/data", async (orig) => ({
  ...(await orig<typeof import("@/lib/data")>()),
  readIndex: () => state.runs,
  readProfiles: () => state.profiles,
  readGraph: () => ({ nodes: [], edges: [] }),
  readRun: () => null,
}));

import OverviewPage from "./page";

const funnel = { candidates: 300, selected: 12, crawled: 12, extracted: 10, relevant: 8, valid: 7 };
const QUOTA = ["only 0 valid startups (< 3)", "validity rate 0% (< 50%)", "only 0 discovery sources produced valid startups (< 2)"];

function run(id: string, tokens: number, over: Partial<RunSummary> = {}): RunSummary {
  return {
    run_id: id,
    started_at: `2026-10-20T${id.slice(9, 11)}:${id.slice(11, 13)}:00+00:00`,
    duration_s: 60,
    passed: true,
    status: "passed",
    funnel,
    tokens,
    sources: { hn: 5 },
    failures: [],
    ...over,
  };
}

const quotaRun = (id: string, tokens: number) =>
  run(id, tokens, { passed: false, status: "quota", failures: QUOTA });

/** The real 2026-10-20 shape: 9 runs, 275,414 tokens, the last run only 47,012. */
const TODAY = [
  run("20261020T080338Z", 34956),
  run("20261020T110815Z", 20779, { passed: false, status: "failed", failures: ["only 2 valid startups (< 3)"] }),
  run("20261020T172115Z", 47707),
  quotaRun("20261020T181651Z", 857),
  quotaRun("20261020T184141Z", 0),
  quotaRun("20261020T193545Z", 2862),
  run("20261020T194209Z", 75557),
  run("20261020T203526Z", 45684),
  run("20261020T212403Z", 47012),
];

const stat = (label: string) => screen.getByText(label).parentElement as HTMLElement;

beforeEach(() => {
  state.runs = TODAY;
  state.profiles = [];
});

describe("Overview: Tokens today", () => {
  it("adds up every run of the day instead of showing the latest run's tokens (regression)", () => {
    render(<OverviewPage />);
    const card = stat("Tokens today");
    expect(within(card).getByText("275k")).toBeInTheDocument();
    expect(within(card).queryByText("47.0k")).toBeNull();
    expect(card).toHaveTextContent("9 runs");
  });

  it("measures against the day's budget, and says when it is exceeded", () => {
    render(<OverviewPage />);
    expect(stat("Tokens today")).toHaveTextContent("138% of 200k");
  });

  it("uses the recorded multi-key budget when runs carry one", () => {
    state.runs = TODAY.map((r) => ({ ...r, token_budget: 400_000 }));
    render(<OverviewPage />);
    expect(stat("Tokens today")).toHaveTextContent("69% of 400k");
  });

  it("only counts the day of the latest run", () => {
    state.runs = [{ ...run("20261019T060000Z", 90_000), started_at: "2026-10-19T06:00:00+00:00" }, ...TODAY];
    render(<OverviewPage />);
    expect(within(stat("Tokens today")).getByText("275k")).toBeInTheDocument();
  });
});

describe("Overview: run health", () => {
  it("leaves quota-limited runs out of the pass rate", () => {
    render(<OverviewPage />);
    const card = stat("Pass rate");
    expect(card).toHaveTextContent("83%"); // 5 passed of 6 counted
    expect(card).toHaveTextContent("3 quota-limited");
  });

  it("does not claim the system failed when the latest run only hit the quota", () => {
    state.runs = [...TODAY, quotaRun("20261020T220000Z", 0)];
    render(<OverviewPage />);
    expect(screen.queryByText(/LAST RUN FAILED/)).toBeNull();
    expect(screen.getByText(/QUOTA REACHED/)).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(/Groq daily token limit/);
  });

  it("does flag a genuine quality failure", () => {
    state.runs = [...TODAY, run("20261020T220000Z", 60_000, { passed: false, status: "failed", failures: ["only 2 valid startups (< 3)"] })];
    render(<OverviewPage />);
    expect(screen.getByText(/LAST RUN FAILED/)).toBeInTheDocument();
  });

  it("is nominal after a good run, with no quota banner", () => {
    render(<OverviewPage />);
    expect(screen.getByText(/SYSTEM NOMINAL/)).toBeInTheDocument();
    expect(screen.queryByRole("status")).toBeNull();
  });
});

describe("Overview: latest findings", () => {
  const p = (slug: string, score: number, at: string) =>
    ({
      slug,
      company_name: slug,
      core_product: "",
      likely_bottleneck: "",
      value_prop_pitch: "",
      source_url: `https://example.com/${slug}`,
      score,
      discovered_at: at,
      tech_stack: [],
      people: [],
      edges: [],
      is_relevant: true,
    }) satisfies Profile;

  it("shows the most recently discovered, not the highest scored", () => {
    state.profiles = [
      p("highscore-old", 99, "2026-10-20T08:00:00+00:00"),
      p("newest", 40, "2026-10-20T21:00:00+00:00"),
    ];
    render(<OverviewPage />);
    const section = screen.getByLabelText("Latest findings");
    const names = within(section).getAllByRole("heading", { level: 3 }).map((h) => h.textContent);
    expect(names[0]).toContain("newest");
  });
});

describe("Overview: empty", () => {
  it("renders the first-run state with no runs", () => {
    state.runs = [];
    render(<OverviewPage />);
    expect(screen.getByText("No runs yet")).toBeInTheDocument();
  });
});
