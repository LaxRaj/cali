import { describe, expect, it } from "vitest";
import { asciiBar, fmtDate, fmtDateTime, fmtDuration, fmtTokens } from "./format";

describe("fmtTokens", () => {
  it("prints small counts as-is", () => {
    expect(fmtTokens(0)).toBe("0");
    expect(fmtTokens(999)).toBe("999");
  });
  it("uses one decimal below 100k and none above", () => {
    expect(fmtTokens(1000)).toBe("1.0k");
    expect(fmtTokens(47012)).toBe("47.0k");
    expect(fmtTokens(100_000)).toBe("100k");
    expect(fmtTokens(275_414)).toBe("275k");
  });
  it("rounds before choosing decimals, so 99,999 is '100k' and never '100.0k'", () => {
    expect(fmtTokens(99_999)).toBe("100k");
    expect(fmtTokens(99_949)).toBe("99.9k");
    expect(fmtTokens(999_999)).toBe("1000k");
  });
});

describe("fmtDuration", () => {
  it("seconds, with a decimal under 10s", () => {
    expect(fmtDuration(4.26)).toBe("4.3s");
    expect(fmtDuration(42)).toBe("42s");
  });
  it("minutes and seconds", () => {
    expect(fmtDuration(310.5)).toBe("5m 11s");
    expect(fmtDuration(60)).toBe("1m 0s");
  });
});

describe("dates are UTC", () => {
  it("fmtDate", () => {
    expect(fmtDate("2026-10-20T23:59:00+00:00")).toBe("Oct 20");
  });
  it("fmtDateTime labels the zone", () => {
    expect(fmtDateTime("2026-10-20T21:24:03+00:00")).toBe("Oct 20, 2026, 9:24 PM UTC");
  });
});

describe("asciiBar", () => {
  it("fills proportionally", () => {
    expect(asciiBar(5, 10, 10)).toBe("█████░░░░░");
  });
  it("is empty when max is 0 (no NaN width)", () => {
    expect(asciiBar(3, 0, 4)).toBe("░░░░");
  });
  it("clamps a value above max", () => {
    expect(asciiBar(500, 100, 4)).toBe("████");
  });
  it("always has `width` cells", () => {
    for (const v of [0, 1, 33, 100]) expect(asciiBar(v, 100, 20)).toHaveLength(20);
  });
});
