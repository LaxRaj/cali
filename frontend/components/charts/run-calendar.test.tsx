import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { RunSummary } from "@/lib/data";
import { RunCalendar } from "./run-calendar";

const run = (id: string, passed: boolean, over: Partial<RunSummary> = {}): RunSummary => ({
  run_id: id,
  started_at: `2026-10-${id.slice(6, 8)}T06:00:00+00:00`,
  duration_s: 1,
  passed,
  funnel: { candidates: 1, selected: 1, crawled: 1, extracted: 1, relevant: 1, valid: 3 },
  tokens: 1,
  sources: {},
  failures: [],
  ...over,
});

describe("RunCalendar", () => {
  it("says so when empty", () => {
    render(<RunCalendar runs={[]} />);
    expect(screen.getByText("no runs yet")).toBeInTheDocument();
  });
  it("renders one link per run, to that run's page", () => {
    render(<RunCalendar runs={[run("20261019T060000Z", true), run("20261020T060000Z", false)]} />);
    const links = screen.getAllByRole("link");
    expect(links.map((l) => l.getAttribute("href"))).toEqual([
      "/runs/20261019T060000Z",
      "/runs/20261020T060000Z",
    ]);
  });
  it("colours passed green and failed red", () => {
    render(<RunCalendar runs={[run("20261019T060000Z", true), run("20261020T060000Z", false)]} />);
    const [ok, bad] = screen.getAllByRole("link");
    expect(ok.className).toContain("bg-emerald");
    expect(bad.className).toContain("bg-rose");
  });
  it("tells screen readers the date and outcome", () => {
    render(<RunCalendar runs={[run("20261020T060000Z", true)]} />);
    expect(screen.getByText("Oct 20: passed")).toBeInTheDocument();
  });
});
