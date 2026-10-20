import type { RunStatus } from "@/lib/data";

/** Shown when the newest run stopped on Groq's daily token limit. Only then; otherwise nothing. */
export function QuotaBanner({ state }: { state: RunStatus | undefined }) {
  if (state !== "quota") return null;
  return (
    <p
      role="status"
      className="border-2 border-amber-500 bg-amber-100 px-3 py-2 text-xs text-amber-900 dark:bg-amber-950 dark:text-amber-200"
    >
      The latest run stopped at the Groq daily token limit, which resets at
      00:00 UTC. Quota-limited runs are not counted as failures in the pass
      rate.
    </p>
  );
}
