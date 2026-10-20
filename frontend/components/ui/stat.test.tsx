import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Stat } from "./stat";

describe("Stat", () => {
  it("shows label, value and sub text", () => {
    render(<Stat label="Tokens today" value="275k" sub="9 runs" />);
    expect(screen.getByText("Tokens today")).toBeInTheDocument();
    expect(screen.getByText("275k")).toBeInTheDocument();
    expect(screen.getByText("9 runs")).toBeInTheDocument();
  });
  it("omits the sub line when none is given", () => {
    const { container } = render(<Stat label="A" value={3} />);
    expect(container.firstElementChild?.children).toHaveLength(2); // label + value only
  });
  it("renders numeric zero", () => {
    render(<Stat label="Startups" value={0} />);
    expect(screen.getByText("0")).toBeInTheDocument();
  });
});
