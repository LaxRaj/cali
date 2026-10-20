import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Stage } from "@/lib/data";
import { StageTimeline } from "./stage-timeline";

const stage = (name: string, offset_s: number, duration_s: number, status: Stage["status"] = "ok"): Stage => ({
  name,
  started_at: "2026-10-20T00:00:00+00:00",
  offset_s,
  duration_s,
  status,
  counts: {},
  notes: [],
});

describe("StageTimeline", () => {
  it("positions each bar by offset and width by duration, as a share of the whole run", () => {
    render(<StageTimeline stages={[stage("discover", 0, 25), stage("crawl", 25, 75)]} />);
    const [a, b] = screen.getAllByRole("img");
    expect(a).toHaveStyle({ left: "0%", width: "25%" });
    expect(b).toHaveStyle({ left: "25%", width: "75%" });
  });
  it("gives a failed stage a distinct label", () => {
    render(<StageTimeline stages={[stage("extract", 0, 5, "error")]} />);
    expect(screen.getByRole("img")).toHaveAccessibleName("extract took 5.0s and failed");
  });
  it("keeps a near-instant stage visible", () => {
    render(<StageTimeline stages={[stage("gates", 99.9, 0.1), stage("crawl", 0, 99.9)]} />);
    const widths = screen.getAllByRole("img").map((el) => parseFloat((el as HTMLElement).style.width));
    expect(Math.min(...widths)).toBeGreaterThanOrEqual(1);
  });
  it("renders nothing harmful for zero stages", () => {
    const { container } = render(<StageTimeline stages={[]} />);
    expect(container.querySelectorAll("li")).toHaveLength(0);
  });
});
