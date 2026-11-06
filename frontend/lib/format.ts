export function fmtDuration(s: number): string {
  if (s < 60) return `${s.toFixed(s < 10 ? 1 : 0)}s`;
  return `${Math.floor(s / 60)}m ${Math.round(s % 60)}s`;
}

export function fmtTokens(n: number): string {
  if (n < 1000) return String(n);
  const k = Math.round(n / 100) / 10; // round first so 99,999 reads "100k", not "100.0k"
  return `${k.toFixed(k >= 100 ? 0 : 1)}k`;
}

export function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

export function fmtDateTime(iso: string): string {
  return `${new Date(iso).toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" })} UTC`;
}

/** "invested_in" -> "invested in", "contact_now" -> "contact now" (every underscore, not just the first). */
export function humanize(s: string): string {
  return (s ?? "").replaceAll("_", " ");
}

export const STAGES = [
  "pre-seed",
  "seed",
  "Series A",
  "Series B",
  "Series C+",
  "YC",
  "angel",
  "bridge",
] as const;
export const UNKNOWN_STAGE = "unknown";

/**
 * One spelling per funding stage ("pre‑Seed", "Pre-seed" -> "pre-seed"; "Series A2" -> "Series A"), mirroring
 * backend/entities.normalize_stage so profiles exported before the backend normalised them still group correctly.
 * Empty -> "unknown"; anything else unrecognised is kept as written.
 */
export function normalizeStage(raw: string | undefined | null): string {
  const s = (raw ?? "")
    .replace(/[‐-—]/g, "-")
    .replace(/\s+/g, " ")
    .trim();
  const low = s.toLowerCase();
  if (!low) return UNKNOWN_STAGE;
  if (/pre[- ]?seed/.test(low)) return "pre-seed";
  if (/\bseries [c-z]\b|\bseries [c-z]\d|growth|late[- ]stage|\bipo\b|public/.test(low))
    return "Series C+";
  if (/\bseries b/.test(low)) return "Series B";
  if (/\bseries a/.test(low)) return "Series A";
  if (low.includes("seed")) return "seed";
  if (/\byc\b|y ?combinator/.test(low)) return "YC";
  if (low.includes("angel")) return "angel";
  if (low.includes("bridge")) return "bridge";
  return s;
}

/** RFC 4180 CSV: quote every field, double inner quotes, CRLF rows. */
export function toCsv(
  header: string[],
  rows: (string | number | boolean | null | undefined)[][],
): string {
  const cell = (v: string | number | boolean | null | undefined) =>
    `"${String(v ?? "").replaceAll('"', '""')}"`;
  return [header, ...rows].map((r) => r.map(cell).join(",")).join("\r\n");
}

/** ASCII bar of `width` cells: ████░░░░ */
export function asciiBar(value: number, max: number, width = 20): string {
  const filled = max > 0 ? Math.round((Math.min(value, max) / max) * width) : 0;
  return "█".repeat(filled) + "░".repeat(width - filled);
}
