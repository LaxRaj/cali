export type LedState = "ok" | "fail" | "warn" | "idle";

const LED: Record<LedState, string> = {
  ok: "bg-emerald-400 shadow-[0_0_8px] shadow-emerald-400 motion-safe:animate-pulse",
  fail: "bg-rose-500 shadow-[0_0_8px] shadow-rose-500",
  warn: "bg-amber-400 shadow-[0_0_8px] shadow-amber-400",
  idle: "bg-zinc-400 dark:bg-zinc-600",
};

export function Led({ state, label }: { state: LedState; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        aria-hidden
        className={`inline-block h-2.5 w-2.5 rounded-full border border-zinc-900/60 ${LED[state]}`}
      />
      <span className="sr-only">{label}</span>
    </span>
  );
}
