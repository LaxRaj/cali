import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Funnel } from "./funnel";

const f = { candidates: 300, selected: 12, crawled: 12, extracted: 10, relevant: 8, valid: 7 };

describe("Funnel", () => {
  it("renders the six stages in order with their counts", () => {
    render(<Funnel funnel={f} />);
    const labels = screen.getAllByRole("img").map((el) => el.getAttribute("aria-label"));
    expect(labels).toEqual([
      "found: 300",
      "triaged: 12",
      "crawled: 12",
      "extracted: 10",
      "relevant: 8",
      "valid: 7",
    ]);
  });
  it("shows step-to-step conversion", () => {
    render(<Funnel funnel={f} />);
    expect(screen.getByText("4%")).toBeInTheDocument(); // 12 / 300
    expect(screen.getByText("88%")).toBeInTheDocument(); // 7 / 8
  });
  it("copes with an all-zero funnel (a quota-starved run)", () => {
    render(<Funnel funnel={{ candidates: 0, selected: 0, crawled: 0, extracted: 0, relevant: 0, valid: 0 }} />);
    expect(screen.getAllByRole("img")).toHaveLength(6);
    expect(document.body.textContent).not.toContain("NaN");
  });
});
