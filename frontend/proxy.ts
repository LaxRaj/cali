import { NextResponse, type NextRequest } from "next/server";

// Password gate for the hosted dashboard (HTTP Basic auth, free on Vercel Hobby).
// Off unless CALI_DASHBOARD_PASSWORD is set, so local dev, tests and the build are unaffected.
// User: CALI_DASHBOARD_USER (default "cali").

function safeEqual(a: string, b: string): boolean {
  // constant time over the longer input: no early exit that leaks how much matched
  let diff = a.length ^ b.length;
  for (let i = 0; i < Math.max(a.length, b.length); i++) {
    diff |= (a.charCodeAt(i) || 0) ^ (b.charCodeAt(i) || 0);
  }
  return diff === 0;
}

export function authorized(header: string | null, user: string, password: string): boolean {
  if (!header?.startsWith("Basic ")) return false;
  let decoded: string;
  try {
    decoded = atob(header.slice(6).trim());
  } catch {
    return false;
  }
  const i = decoded.indexOf(":");
  if (i < 0) return false;
  // evaluate both comparisons (no short-circuit) so timing does not reveal which one failed
  const okUser = safeEqual(decoded.slice(0, i), user);
  const okPass = safeEqual(decoded.slice(i + 1), password);
  return okUser && okPass;
}

export function proxy(request: NextRequest) {
  const password = process.env.CALI_DASHBOARD_PASSWORD;
  if (!password) return NextResponse.next();
  const user = process.env.CALI_DASHBOARD_USER || "cali";
  if (authorized(request.headers.get("authorization"), user, password)) return NextResponse.next();
  return new NextResponse("Authentication required", {
    status: 401,
    headers: { "WWW-Authenticate": 'Basic realm="cali", charset="UTF-8"', "Cache-Control": "no-store" },
  });
}

export const config = {
  // everything except Next's static assets and the favicon
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
