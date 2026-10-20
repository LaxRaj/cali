/** Lead score 0-100 as a chunky badge; colour tier = how ready the lead is for outreach. */
export function ScoreBadge({ score }: { score?: number }) {
  if (score === undefined) return null;
  const tier =
    score >= 75
      ? "bg-emerald-300 dark:bg-emerald-950 dark:text-emerald-300 dark:border-emerald-400/70"
      : score >= 50
        ? "bg-amber-200 dark:bg-amber-950 dark:text-amber-300 dark:border-amber-400/70"
        : "bg-rose-200 dark:bg-rose-950 dark:text-rose-300 dark:border-rose-400/70";
  return (
    <span
      title="Lead score: fit, identity, people, connections and contact details"
      className={`inline-flex items-baseline gap-0.5 border-2 border-zinc-900 px-1.5 font-display text-xl leading-6 ${tier}`}
    >
      {score}
      <span className="text-[10px] font-sans font-normal opacity-70">/100</span>
    </span>
  );
}
