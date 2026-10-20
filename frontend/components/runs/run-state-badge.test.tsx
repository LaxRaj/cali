import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RunStateBadge } from "./run-state-badge";

describe("RunStateBadge", () => {
  it.each([
    ["passed", "PASS"],
    ["failed", "FAIL"],
    ["quota", "QUOTA"],
  ] as const)("%s reads %s", (state, text) => {
    render(<RunStateBadge state={state} />);
    expect(screen.getByText(text)).toBeInTheDocument();
  });

  it("colours quota amber, not red: it is not a quality failure", () => {
    const { container } = render(<RunStateBadge state="quota" />);
    expect(container.querySelector("[aria-hidden]")?.className).toContain("amber");
    expect(container.querySelector("[aria-hidden]")?.className).not.toContain("rose");
  });

  it("colours failed red and passed green", () => {
    expect(render(<RunStateBadge state="failed" />).container.querySelector("[aria-hidden]")?.className).toContain("rose");
    expect(render(<RunStateBadge state="passed" />).container.querySelector("[aria-hidden]")?.className).toContain("emerald");
  });
});
