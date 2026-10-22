import type { Profile } from "./data";
import type { OutreachState } from "./outreach";

export const CSV_COLUMNS = ["company", "score", "stage", "status", "next_due", "to", "to_source_url", "contacts", "website", "profile"] as const;

/** A spreadsheet would run a cell that starts with = + - @ as a formula, so those get a leading quote. */
function cell(v: string | number): string {
  const s = String(v ?? "");
  const safe = /^[=+\-@\t\r]/.test(s) ? `'${s}` : s;
  return /[",\n\r]/.test(safe) ? `"${safe.replace(/"/g, '""')}"` : safe;
}

/** Leads as CSV: only the published address (with the page it came from), never a guessed one. */
export function leadsToCsv(rows: { p: Profile; s: OutreachState }[], origin = ""): string {
  const lines = [CSV_COLUMNS.join(",")];
  for (const { p, s } of rows) {
    const leaders = p.people.filter((x) => /founder|ceo|cto|chief/i.test(x.role)).map((x) => x.name);
    lines.push(
      [
        p.company_name,
        p.score ?? "",
        p.funding_stage ?? "",
        s.status,
        s.next_due,
        p.email_draft?.to ?? "",
        p.email_draft?.to_source_url ?? "",
        leaders.join("; "),
        p.website ?? "",
        `${origin}/startups/${p.slug}`,
      ]
        .map(cell)
        .join(","),
    );
  }
  return lines.join("\n") + "\n";
}

/** Published addresses of the given leads, one per line, skipping leads without one. */
export function publishedEmails(rows: { p: Profile }[]): string[] {
  return rows.flatMap(({ p }) => (p.email_draft?.to ? [p.email_draft.to] : []));
}
