import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AsciiBar } from "./ascii-bar";

describe("AsciiBar", () => {
  it("draws the proportional bar and the value", () => {
    render(<AsciiBar label="hn" value={5} max={10} width={10} />);
    const bar = screen.getByRole("img");
    expect(bar).toHaveTextContent("█████░░░░░");
    expect(bar).toHaveAccessibleName("hn: 5 of 10");
    expect(screen.getByText("5")).toBeInTheDocument();
  });
  it("shows `display` instead of the raw value, in the label too", () => {
    render(<AsciiBar label="yc" value={50} max={100} display="3/6 · cap 4" />);
    expect(screen.getByText("3/6 · cap 4")).toBeInTheDocument();
    expect(screen.getByRole("img")).toHaveAccessibleName("yc: 3/6 · cap 4 of 100");
  });
  it("does not overflow when value exceeds max", () => {
    render(<AsciiBar label="x" value={999} max={10} width={6} />);
    expect(screen.getByRole("img")).toHaveTextContent("██████");
  });
});
