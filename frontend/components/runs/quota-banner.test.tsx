import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { QuotaBanner } from "./quota-banner";

describe("QuotaBanner", () => {
  it("renders nothing unless the latest run was quota-limited", () => {
    expect(render(<QuotaBanner state="passed" />).container).toBeEmptyDOMElement();
    expect(render(<QuotaBanner state="failed" />).container).toBeEmptyDOMElement();
    expect(render(<QuotaBanner state={undefined} />).container).toBeEmptyDOMElement();
  });

  it("explains it is the Groq limit, not bad data, and when it resets", () => {
    render(<QuotaBanner state="quota" />);
    expect(screen.getByRole("status")).toHaveTextContent(/Groq daily token limit/);
    expect(screen.getByRole("status")).toHaveTextContent(/00:00 UTC/);
    expect(screen.getByRole("status")).toHaveTextContent(/not counted as failures/i);
  });
});
