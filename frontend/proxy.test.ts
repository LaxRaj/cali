import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import { authorized, proxy } from "./proxy";

const basic = (u: string, p: string) => `Basic ${btoa(`${u}:${p}`)}`;
const req = (auth?: string) =>
  new NextRequest("https://cali.example/", auth ? { headers: { authorization: auth } } : undefined);

afterEach(() => vi.unstubAllEnvs());

describe("authorized", () => {
  it("accepts only the exact user and password", () => {
    expect(authorized(basic("cali", "s3cret:x"), "cali", "s3cret:x")).toBe(true); // ':' inside the password is fine
    expect(authorized(basic("cali", "wrong"), "cali", "s3cret:x")).toBe(false);
    expect(authorized(basic("admin", "s3cret:x"), "cali", "s3cret:x")).toBe(false);
    expect(authorized(null, "cali", "p")).toBe(false);
    expect(authorized("Bearer abc", "cali", "p")).toBe(false);
    expect(authorized("Basic !!!not-base64", "cali", "p")).toBe(false);
  });
});

describe("proxy", () => {
  it("does nothing when no password is configured (local dev, tests, build)", () => {
    vi.stubEnv("CALI_DASHBOARD_PASSWORD", "");
    expect(proxy(req()).status).toBe(200);
  });
  it("asks for credentials when a password is set", () => {
    vi.stubEnv("CALI_DASHBOARD_PASSWORD", "pw");
    const res = proxy(req());
    expect(res.status).toBe(401);
    expect(res.headers.get("www-authenticate")).toContain("Basic");
    expect(proxy(req(basic("cali", "nope"))).status).toBe(401);
  });
  it("lets the right credentials through, with a configurable user", () => {
    vi.stubEnv("CALI_DASHBOARD_PASSWORD", "pw");
    expect(proxy(req(basic("cali", "pw"))).status).toBe(200);
    vi.stubEnv("CALI_DASHBOARD_USER", "lakshya");
    expect(proxy(req(basic("cali", "pw"))).status).toBe(401);
    expect(proxy(req(basic("lakshya", "pw"))).status).toBe(200);
  });
});
