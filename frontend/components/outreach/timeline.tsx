import { fmtDateTime } from "@/lib/format";
import type { EventType, OutreachEvent } from "@/lib/outreach";

const GLYPH: Record<EventType, string> = {
  sent: "↗",
  replied: "↙",
  bounced: "✕",
  meeting: "◈",
  won: "★",
  passed: "⊘",
  note: "✎",
  snooze: "⏸",
};

const LABEL: Record<EventType, string> = {
  sent: "sent",
  replied: "they replied",
  bounced: "bounced",
  meeting: "meeting",
  won: "won",
  passed: "passed",
  note: "note",
  snooze: "snoozed",
};

/** Every touch on a lead, newest first, with the address used and the page it was published on. */
export function Timeline({ events }: { events: OutreachEvent[] }) {
  if (events.length === 0) {
    return (
      <p className="text-xs text-zinc-600 dark:text-zinc-400">
        Nothing logged yet. Log a send and it shows up here.
      </p>
    );
  }
  const newestFirst = [...events].sort((a, b) => (a.at < b.at ? 1 : a.at > b.at ? -1 : 0));
  return (
    <ol aria-label="Outreach timeline" className="space-y-1.5 text-xs">
      {newestFirst.map((e) => (
        <li key={e.id} className="flex gap-2">
          <span aria-hidden className="w-4 shrink-0 text-center font-display text-lg leading-none">
            {GLYPH[e.type]}
          </span>
          <div className="min-w-0">
            <span className="font-semibold uppercase">{LABEL[e.type]}</span>
            <span className="text-zinc-600 dark:text-zinc-400"> · {fmtDateTime(e.at)}</span>
            {e.subject && <p className="truncate">“{e.subject}”</p>}
            {e.to && (
              <p className="text-zinc-600 dark:text-zinc-400">
                to {e.to}
                {e.to_source_url && (
                  <>
                    {" "}
                    <a
                      href={e.to_source_url}
                      target="_blank"
                      rel="noreferrer"
                      className="underline-offset-2 hover:underline"
                    >
                      published here ↗
                    </a>
                  </>
                )}
              </p>
            )}
            {e.reason && <p className="text-zinc-600 dark:text-zinc-400">why: {e.reason.replace(/_/g, " ")}</p>}
            {e.until && <p className="text-zinc-600 dark:text-zinc-400">until {fmtDateTime(e.until)}</p>}
            {e.note && <p className="text-zinc-600 dark:text-zinc-400">{e.note}</p>}
          </div>
        </li>
      ))}
    </ol>
  );
}
