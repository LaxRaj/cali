import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { RunSummary } from "@/lib/data";
import { DailyTokenMeter } from "./daily-token-meter";

const run = (id: string, tokens: number): RunSummary => ({
  run_id: id,
  started_at: `2026-10-20T${id.slice(9, 11)}:${id.slice(11, 13)}:00+00:00`,
  duration_s: 1,
  passed: true,
  funnel: { candidates: 1, selected: 1, crawled: 1, extracted: 1, relevant: 1, valid: 1 },
  tokens,
  sources: {},
  failures: [],
});

const RUNS = [run("20261020T080000Z", 50_000), run("20261020T120000Z", 30_000), run("20261020T210000Z", 0)];

describe("DailyTokenMeter", () => {
  it("shows the day's total against the budget", () => {
    render(<DailyTokenMeter runs={RUNS} budget={200_000} />);
    expect(screen.getByText("80.0k")).toBeInTheDocument();
    expect(screen.getByText(/of 200k/)).toBeInTheDocument();
    expect(screen.getByText(/40%/)).toBeInTheDocument();
  });

  it("draws one segment per run that used tokens, labelled with its time", () => {
    render(<DailyTokenMeter runs={RUNS} budget={200_000} />);
    const segs = screen.getAllByRole("img");
    expect(segs.map((s) => s.getAttribute("aria-label"))).toEqual([
      "08:00 UTC: 50.0k tokens",
      "12:00 UTC: 30.0k tokens",
    ]);
  });

  it("sizes segments by share of the budget", () => {
    render(<DailyTokenMeter runs={RUNS} budget={200_000} />);
    const [a, b] = screen.getAllByRole("img");
    expect(a).toHaveStyle({ width: "25%" });
    expect(b).toHaveStyle({ width: "15%" });
  });

  it("reports headroom and the UTC reset", () => {
    render(<DailyTokenMeter runs={RUNS} budget={200_000} />);
    expect(screen.getByText(/120k left/)).toBeInTheDocument();
    expect(screen.getByText(/resets 00:00 UTC/)).toBeInTheDocument();
  });

  it("flags going over budget instead of overflowing the bar", () => {
    const over = [run("20261020T080000Z", 275_414)];
    render(<DailyTokenMeter runs={over} budget={200_000} />);
    expect(screen.getByText(/138%/)).toBeInTheDocument();
    expect(screen.getByText(/over budget/i)).toBeInTheDocument();
    const widths = screen.getAllByRole("img").map((s) => parseFloat((s as HTMLElement).style.width));
    expect(widths.reduce((t, w) => t + w, 0)).toBeLessThanOrEqual(100.0001);
  });

  it("handles a day with no runs", () => {
    render(<DailyTokenMeter runs={[]} budget={200_000} />);
    expect(screen.getByText("0")).toBeInTheDocument();
    expect(screen.queryAllByRole("img")).toHaveLength(0);
    expect(document.body.textContent).not.toContain("NaN");
  });
});
