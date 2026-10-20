export function fmtDuration(s: number): string {
  if (s < 60) return `${s.toFixed(s < 10 ? 1 : 0)}s`;
  return `${Math.floor(s / 60)}m ${Math.round(s % 60)}s`;
}

export function fmtTokens(n: number): string {
  return n >= 1000 ? `${(n / 1000).toFixed(n >= 100_000 ? 0 : 1)}k` : String(n);
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

/** ASCII bar of `width` cells: ████░░░░ */
export function asciiBar(value: number, max: number, width = 20): string {
  const filled = max > 0 ? Math.round((Math.min(value, max) / max) * width) : 0;
  return "█".repeat(filled) + "░".repeat(width - filled);
}
