import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Sparkline } from "./sparkline";

describe("Sparkline", () => {
  it("says so when there is no data", () => {
    render(<Sparkline values={[]} label="x" />);
    expect(screen.getByText("no data")).toBeInTheDocument();
  });

  it("exposes its label and draws one point per value", () => {
    const { container } = render(<Sparkline values={[1, 2, 3]} label="Tokens per day" />);
    expect(screen.getByRole("img")).toHaveAccessibleName("Tokens per day");
    const pts = container.querySelector("polyline")!.getAttribute("points")!.split(" ");
    expect(pts).toHaveLength(3);
  });

  it("centres a single value instead of dividing by zero", () => {
    const { container } = render(<Sparkline values={[5]} label="x" width={100} />);
    const pts = container.querySelector("polyline")!.getAttribute("points")!;
    expect(pts).not.toContain("NaN");
    expect(pts.startsWith("50.0,")).toBe(true);
  });

  it("puts a larger value higher (smaller y) than a smaller one", () => {
    const { container } = render(<Sparkline values={[10, 100]} label="x" />);
    const [a, b] = container
      .querySelector("polyline")!
      .getAttribute("points")!
      .split(" ")
      .map((p) => Number(p.split(",")[1]));
    expect(b).toBeLessThan(a);
  });

  it("scales to the reference line so a value above budget is not clipped", () => {
    const { container } = render(<Sparkline values={[300]} reference={200} label="x" height={56} />);
    const y = Number(container.querySelector("line")!.getAttribute("y1"));
    const top = Number(container.querySelector("polyline")!.getAttribute("points")!.split(",")[1]);
    expect(top).toBeGreaterThanOrEqual(0);
    expect(y).toBeGreaterThan(top); // the 200 line sits below the 300 point
  });

  it("only draws the reference line when asked", () => {
    const { container } = render(<Sparkline values={[1, 2]} label="x" />);
    expect(container.querySelector("line")).toBeNull();
  });

  it("marks the latest point", () => {
    const { container } = render(<Sparkline values={[1, 2, 3]} label="x" />);
    expect(container.querySelectorAll("rect")).toHaveLength(1);
  });
});
