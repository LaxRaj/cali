import { describe, expect, it } from "vitest";
import { DEFAULT_STATE, parseExplorerState, serializeExplorerState } from "./explorer-url";

describe("explorer URL state", () => {
  it("a default view has an empty query string and parses back to the defaults", () => {
    expect(serializeExplorerState(DEFAULT_STATE)).toBe("");
    expect(parseExplorerState("")).toEqual(DEFAULT_STATE);
  });

  it("round-trips every filter", () => {
    const s = { query: "vector db", stage: "seed", tag: "Rust", status: "due" as const, linkedOnly: true, emailOnly: true, sort: "name" as const, view: "table" as const };
    expect(parseExplorerState(serializeExplorerState(s))).toEqual(s);
  });

  it("ignores unknown or malformed values instead of breaking the page", () => {
    const got = parseExplorerState("status=nonsense&sort=random&view=3d&linked=yes&stage=");
    expect(got).toEqual(DEFAULT_STATE);
  });
});
