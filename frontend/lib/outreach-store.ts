import { useMemo, useSyncExternalStore } from "react";
import type { Profile } from "./data";
import {
  type EventType,
  type OutreachEvent,
  type OutreachState,
  EVENT_FIELDS,
  foldOutreach,
  isEvent,
} from "./outreach";

/**
 * Events you log in the browser, kept in localStorage until you export them (`outreach.py import`) or, when the
 * dashboard runs locally with CALI_LOCAL=1, appended straight to backend/data/outreach.jsonl as well.
 * localStorage can be empty, blocked or throw, so every access is guarded and the UI works without it.
 */
const KEY = "cali.outreach.v1";
const EMPTY: OutreachEvent[] = [];
const NONE: OutreachState = foldOutreach([], 0);

let cached: { raw: string | null; events: OutreachEvent[] } = { raw: null, events: EMPTY };
let fallback: OutreachEvent[] | null = null; // used when localStorage refuses writes
const listeners = new Set<() => void>();

/** Forget cached reads and the in-memory fallback (used by tests and after clearing browser data). */
export function resetOutreachStore() {
  cached = { raw: null, events: EMPTY };
  fallback = null;
  listeners.forEach((l) => l());
}

function readRaw(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function getSnapshot(): OutreachEvent[] {
  const raw = readRaw();
  if (raw === null && fallback) return fallback;
  if (raw === cached.raw) return cached.events;
  let events = EMPTY;
  try {
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    if (Array.isArray(parsed)) events = parsed.filter(isEvent);
  } catch {
    events = EMPTY;
  }
  cached = { raw, events };
  return events;
}

export function subscribe(cb: () => void): () => void {
  listeners.add(cb);
  const onStorage = (e: StorageEvent) => {
    if (e.key === KEY || e.key === null) cb();
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(cb);
    window.removeEventListener("storage", onStorage);
  };
}

function write(events: OutreachEvent[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(events));
    fallback = null;
  } catch {
    fallback = events;
  }
  listeners.forEach((l) => l());
}

export function newEvent(
  company: string,
  type: EventType,
  fields: Partial<Omit<OutreachEvent, "id" | "company" | "type" | "at">> = {},
  at: Date = new Date(),
): OutreachEvent {
  const raw =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now()}${Math.random()}`;
  const extra = Object.fromEntries(
    Object.entries(fields).filter(([k, v]) => v && (EVENT_FIELDS as readonly string[]).includes(k)),
  );
  return {
    id: raw.replace(/[^a-z0-9]/gi, ""),
    company: company.trim(),
    type,
    at: at.toISOString().replace(/\.\d{3}Z$/, "+00:00"),
    ...extra,
  };
}

export function addEvent(event: OutreachEvent) {
  write([...getSnapshot().filter((e) => e.id !== event.id), event]);
}

export function removeEvent(id: string) {
  write(getSnapshot().filter((e) => e.id !== id));
}

/** Drop browser events the build already contains (after you imported, committed and redeployed). */
export function pruneSynced(bakedIds: Set<string>) {
  const mine = getSnapshot();
  const keep = mine.filter((e) => !bakedIds.has(e.id));
  if (keep.length !== mine.length) write(keep);
}

/** Log in the browser right away, then try the local backend log. Resolves to where it ended up. */
export async function logEvent(event: OutreachEvent): Promise<"local" | "browser"> {
  addEvent(event);
  try {
    const res = await fetch("/api/outreach", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(event),
    });
    return res.ok ? "local" : "browser";
  } catch {
    return "browser";
  }
}

export function mergeEvents(baked: OutreachEvent[], overlay: OutreachEvent[]): OutreachEvent[] {
  const seen = new Set<string>();
  return [...baked, ...overlay]
    .filter((e) => (seen.has(e.id) ? false : (seen.add(e.id), true)))
    .sort((a, b) => (a.at < b.at ? -1 : a.at > b.at ? 1 : 0));
}

export function exportJson(events: OutreachEvent[], now: Date = new Date()): string {
  return JSON.stringify({ version: 1, exported_at: now.toISOString(), events }, null, 2);
}

export function parseImport(text: string): { events: OutreachEvent[]; skipped: number } {
  try {
    const raw: unknown = JSON.parse(text);
    const list: unknown[] = Array.isArray(raw)
      ? raw
      : raw && typeof raw === "object" && Array.isArray((raw as { events?: unknown }).events)
        ? (raw as { events: unknown[] }).events
        : [];
    const events = list.filter(isEvent);
    return { events, skipped: list.length - events.length };
  } catch {
    return { events: [], skipped: 0 };
  }
}

export type LeadOutreach = { events: OutreachEvent[]; state: OutreachState };

const key = (name: string) => name.trim().toLowerCase();

/** Outreach per lead (by slug): build-time log merged with browser events, folded at `nowMs` (null = use the build-time state). */
export function buildOutreach(
  profiles: Profile[],
  overlay: OutreachEvent[],
  nowMs: number | null,
): Map<string, LeadOutreach> {
  const mine = new Map<string, OutreachEvent[]>();
  for (const e of overlay) mine.set(key(e.company), [...(mine.get(key(e.company)) ?? []), e]);
  const out = new Map<string, LeadOutreach>();
  for (const p of profiles) {
    const baked = p.outreach?.events ?? [];
    const extra = mine.get(key(p.company_name)) ?? [];
    if (extra.length === 0 && nowMs === null) {
      const { events: _events, ...state } = p.outreach ?? { events: [], ...NONE };
      void _events;
      out.set(p.slug, { events: baked, state });
      continue;
    }
    const events = mergeEvents(baked, extra);
    out.set(p.slug, { events, state: foldOutreach(events, nowMs ?? Date.now()) });
  }
  return out;
}

export function useOutreachEvents(): OutreachEvent[] {
  return useSyncExternalStore(subscribe, getSnapshot, () => EMPTY);
}

const noopSubscribe = () => () => {};
/** Current time rounded to the minute, or null on the server and during hydration (so markup matches). */
export function useNowMs(): number | null {
  return useSyncExternalStore(
    noopSubscribe,
    () => Math.floor(Date.now() / 60_000) * 60_000,
    () => null,
  );
}

export function useOutreach(profiles: Profile[]): Map<string, LeadOutreach> {
  const overlay = useOutreachEvents();
  const now = useNowMs();
  return useMemo(() => buildOutreach(profiles, overlay, now), [profiles, overlay, now]);
}
