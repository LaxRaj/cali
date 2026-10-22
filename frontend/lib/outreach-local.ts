import { EVENT_FIELDS, isEvent } from "./outreach";

const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]", "::1"]);

function hostname(hostOrUrl: string | null): string | null {
  if (!hostOrUrl) return null;
  try {
    return new URL(hostOrUrl.includes("://") ? hostOrUrl : `http://${hostOrUrl}`).hostname;
  } catch {
    return null;
  }
}

/**
 * Whether the dashboard may append to backend/data/outreach.jsonl: only when you started it locally on purpose
 * (CALI_LOCAL=1), never in demo mode, and only for same-origin requests from localhost (blocks other sites' forms).
 */
export function localWriteAllowed(
  env: Record<string, string | undefined>,
  host: string | null,
  origin: string | null,
): boolean {
  if (env.CALI_LOCAL !== "1" || env.CALI_DEMO === "1") return false;
  const h = hostname(host);
  const o = hostname(origin);
  return h !== null && LOCAL_HOSTS.has(h) && o === h;
}

/** One JSONL line for a valid event (only known fields), or null. */
export function eventLine(raw: unknown): string | null {
  if (!isEvent(raw)) return null;
  const src = raw as Record<string, unknown>;
  const out: Record<string, unknown> = {};
  for (const f of EVENT_FIELDS) {
    const v = src[f];
    if (typeof v === "string" && v !== "") out[f] = v;
  }
  return JSON.stringify(out);
}
