"use client";

import { useEffect, useState } from "react";
import { fmtDateTime } from "@/lib/format";
import { dataFreshness } from "@/lib/metrics";

/** How old the newest run is. Pages are built ahead of time, so the age is worked out in the browser
 *  (or from `now`, for tests); until then only the absolute time is shown, never a wrong age. */
export function FreshnessIndicator({
  latestAt,
  now,
}: {
  latestAt: string | undefined;
  now?: Date;
}) {
  const [clock, setClock] = useState<Date | undefined>(now);
  useEffect(() => {
    if (now) return;
    const t = setTimeout(() => setClock(new Date()), 0); // after mount, so the first paint matches the server's
    return () => clearTimeout(t);
  }, [now]);
  const at = now ?? clock;

  if (!latestAt)
    return <span className="text-xs text-zinc-600">no runs yet</span>;
  if (!at)
    return <span className="text-xs">{fmtDateTime(latestAt)}</span>;

  const { ageHours, stale } = dataFreshness({ started_at: latestAt }, at);
  const age =
    ageHours < 1
      ? `${Math.max(0, Math.round(ageHours * 60))} min ago`
      : `${Math.round(ageHours)} h ago`;
  return (
    <span
      className={`text-xs ${stale ? "font-semibold text-amber-700 dark:text-amber-300" : ""}`}
    >
      last run {age}
      {stale && " · stale"}
    </span>
  );
}
