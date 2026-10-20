import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ScoreBadge } from "./score-badge";

describe("ScoreBadge", () => {
  it("renders nothing without a score", () => {
    const { container } = render(<ScoreBadge />);
    expect(container).toBeEmptyDOMElement();
  });
  it("shows a zero score (falsy but real)", () => {
    render(<ScoreBadge score={0} />);
    expect(screen.getByText("0")).toBeInTheDocument();
  });
  it.each([
    [100, "bg-emerald-300"],
    [75, "bg-emerald-300"],
    [74, "bg-amber-200"],
    [50, "bg-amber-200"],
    [49, "bg-rose-200"],
  ])("score %i is in tier %s", (score, cls) => {
    const { container } = render(<ScoreBadge score={score} />);
    expect(container.firstElementChild?.className).toContain(cls);
  });
});
