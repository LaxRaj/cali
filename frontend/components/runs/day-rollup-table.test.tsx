import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { DayTotal } from "@/lib/metrics";
import { DayRollupTable } from "./day-rollup-table";

const days: DayTotal[] = [
  { day: "2026-10-19", tokens: 90_000, budget: 400_000, runs: 1, passed: 1, failed: 0, quota: 0 },
  { day: "2026-10-20", tokens: 275_414, budget: 200_000, runs: 9, passed: 5, failed: 1, quota: 3 },
];

describe("DayRollupTable", () => {
  it("lists the newest day first", () => {
    render(<DayRollupTable days={days} />);
    const rows = screen.getAllByRole("row").slice(1);
    expect(within(rows[0]).getByText("Oct 20")).toBeInTheDocument();
    expect(within(rows[1]).getByText("Oct 19")).toBeInTheDocument();
  });

  it("shows run counts by state and the day's token total with its share of budget", () => {
    render(<DayRollupTable days={days} />);
    const row = screen.getAllByRole("row")[1];
    expect(row).toHaveTextContent("9");
    expect(row).toHaveTextContent("5 pass");
    expect(row).toHaveTextContent("1 fail");
    expect(row).toHaveTextContent("3 quota");
    expect(row).toHaveTextContent("275k");
    expect(row).toHaveTextContent("138%");
  });

  it("omits zero-count states", () => {
    render(<DayRollupTable days={days} />);
    expect(screen.getAllByRole("row")[2]).not.toHaveTextContent("fail");
    expect(screen.getAllByRole("row")[2]).not.toHaveTextContent("quota");
  });

  it("shows an empty state", () => {
    render(<DayRollupTable days={[]} />);
    expect(screen.getByText(/no runs/i)).toBeInTheDocument();
  });
});
