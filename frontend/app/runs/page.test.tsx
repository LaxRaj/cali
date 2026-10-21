import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { RunSummary } from "@/lib/data";

const state = vi.hoisted(() => ({ runs: [] as RunSummary[] }));

vi.mock("@/lib/data", async (orig) => ({
  ...(await orig<typeof import("@/lib/data")>()),
  readIndex: () => state.runs,
}));

import RunsPage from "./page";

const funnel = { candidates: 300, selected: 12, crawled: 12, extracted: 10, relevant: 8, valid: 7 };

function run(id: string, over: Partial<RunSummary> = {}): RunSummary {
  return {
    run_id: id,
    started_at: `${id.slice(0, 4)}-${id.slice(4, 6)}-${id.slice(6, 8)}T${id.slice(9, 11)}:${id.slice(11, 13)}:00+00:00`,
    duration_s: 60,
    passed: true,
    status: "passed",
    funnel,
    tokens: 1000,
    sources: {},
    failures: [],
    ...over,
  };
}

beforeEach(() => {
  state.runs = [run("20261020T080338Z"), run("20261020T212403Z")];
});

describe("Runs page", () => {
  it("shows the time of each run, not just the date", () => {
    render(<RunsPage />);
    expect(screen.getByText("Oct 20, 2026, 9:24 PM UTC")).toBeInTheDocument();
    expect(screen.getByText("Oct 20, 2026, 8:03 AM UTC")).toBeInTheDocument();
  });

  it("shows a skipped, quota-limited run with a QUOTA badge", () => {
    state.runs.push(
      run("20261021T060000Z", { passed: false, status: "quota", tokens: 0, failures: ["skipped: Groq daily quota already spent"] }),
    );
    render(<RunsPage />);
    expect(screen.getByText("QUOTA")).toBeInTheDocument();
  });

  it("says run records start at the cutoff when the history begins there", () => {
    render(<RunsPage />);
    expect(screen.getByText(/Run records start Oct 20, 2026, 3:15 AM UTC/)).toBeInTheDocument();
  });

  it("omits that note when the index reaches back further (demo data)", () => {
    state.runs = [run("20260921T060000Z"), ...state.runs];
    render(<RunsPage />);
    expect(screen.queryByText(/Run records start/)).toBeNull();
  });
});
