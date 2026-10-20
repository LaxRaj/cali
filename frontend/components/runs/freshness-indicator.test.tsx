import { act, render, screen } from "@testing-library/react";
import { renderToString } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { FreshnessIndicator } from "./freshness-indicator";

const AT = "2026-10-20T21:24:03+00:00";

describe("FreshnessIndicator", () => {
  it("shows the age of the latest run", () => {
    render(<FreshnessIndicator latestAt={AT} now={new Date("2026-10-21T00:24:03Z")} />);
    expect(screen.getByText(/3 h ago/)).toBeInTheDocument();
    expect(screen.queryByText(/stale/i)).toBeNull();
  });

  it("uses minutes when under an hour", () => {
    render(<FreshnessIndicator latestAt={AT} now={new Date("2026-10-20T21:54:03Z")} />);
    expect(screen.getByText(/30 min ago/)).toBeInTheDocument();
  });

  it("warns when the data is older than the daily cadence allows", () => {
    render(<FreshnessIndicator latestAt={AT} now={new Date("2026-10-22T09:24:03Z")} />);
    expect(screen.getByText(/stale/i)).toBeInTheDocument();
    expect(screen.getByText(/36 h ago/)).toBeInTheDocument();
  });

  it("says there is no data when there is no run", () => {
    render(<FreshnessIndicator latestAt={undefined} now={new Date()} />);
    expect(screen.getByText(/no runs/i)).toBeInTheDocument();
  });

  it("on the server render (no clock yet) shows the absolute time, never a wrong age", () => {
    const html = renderToString(<FreshnessIndicator latestAt={AT} />);
    expect(html).toContain("Oct 20, 2026, 9:24 PM UTC");
    expect(html).not.toContain("ago");
  });

  it("works out the age in the browser once mounted", () => {
    vi.useFakeTimers({ now: new Date("2026-10-21T00:24:03Z") });
    render(<FreshnessIndicator latestAt={AT} />);
    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(screen.getByText(/3 h ago/)).toBeInTheDocument();
    vi.useRealTimers();
  });
});
