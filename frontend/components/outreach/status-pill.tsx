import { dueLabel, type OutreachState, type OutreachStatus } from "@/lib/outreach";

export const STATUS_LABEL: Record<OutreachStatus, string> = {
  none: "not contacted",
  contacted: "contacted",
  replied: "replied",
  meeting: "meeting",
  won: "won",
  passed: "passed",
  bounced: "bounced",
};

const STATUS_STYLE: Record<OutreachStatus, string> = {
  none: "border-dashed border-zinc-500 text-zinc-600 dark:text-zinc-400",
  contacted: "border-amber-600 bg-amber-200 text-zinc-900 dark:bg-amber-950 dark:text-amber-300",
  replied: "border-emerald-600 bg-emerald-200 text-zinc-900 dark:bg-emerald-950 dark:text-emerald-300",
  meeting: "border-sky-600 bg-sky-200 text-zinc-900 dark:bg-sky-950 dark:text-sky-300",
  won: "border-emerald-700 bg-emerald-400 text-zinc-900 dark:bg-emerald-400 dark:text-black",
  passed: "border-zinc-500 bg-zinc-200 text-zinc-700 dark:bg-zinc-900 dark:text-zinc-400",
  bounced: "border-rose-600 bg-rose-200 text-zinc-900 dark:bg-rose-950 dark:text-rose-300",
};

const OPEN: OutreachStatus[] = ["contacted", "replied"];

/** Where a lead stands in your outreach, plus when the next move is due (needs the clock, so it appears after mount). */
export function StatusPill({
  state,
  nowMs,
}: {
  state: OutreachState;
  nowMs: number | null;
}) {
  const showDue = OPEN.includes(state.status) && state.next_due && nowMs !== null;
  const due = showDue ? dueLabel(state.next_due, nowMs) : "";
  return (
    <span className="inline-flex flex-wrap items-center gap-1.5">
      <span
        className={`border-2 px-1.5 py-0.5 text-xs font-semibold uppercase leading-none ${STATUS_STYLE[state.status]}`}
      >
        {STATUS_LABEL[state.status]}
        {state.touches > 1 && ` · ${state.touches} touches`}
      </span>
      {due && (
        <span
          className={`px-1 text-xs font-semibold uppercase ${
            state.overdue
              ? "text-rose-700 dark:text-rose-300"
              : state.snoozed
                ? "text-sky-700 dark:text-sky-300"
                : "text-amber-700 dark:text-amber-300"
          }`}
        >
          {state.snoozed ? `snoozed · ${due}` : due}
        </span>
      )}
    </span>
  );
}
