import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Led } from "./led";

describe("Led", () => {
  it("exposes its meaning to screen readers, not the dot", () => {
    const { container } = render(<Led state="fail" label="failed" />);
    expect(screen.getByText("failed")).toHaveClass("sr-only");
    expect(container.querySelector("[aria-hidden]")).not.toBeNull();
  });
  it.each([
    ["ok", "bg-emerald-400"],
    ["fail", "bg-rose-500"],
    ["warn", "bg-amber-400"],
    ["idle", "bg-zinc-400"],
  ] as const)("%s uses %s", (state, cls) => {
    const { container } = render(<Led state={state} label={state} />);
    expect(container.querySelector("[aria-hidden]")?.className).toContain(cls);
  });
});
