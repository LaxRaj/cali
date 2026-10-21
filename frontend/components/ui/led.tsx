export type LedState = "ok" | "fail" | "warn" | "idle";

// A faceted jewel in a gold bezel (the gloss is .gem in globals.css). Under the remapped palette
// emerald = gilt gold, so "ok" is a glowing gold stone, "fail" cinnabar, "warn" copper.
const LED: Record<LedState, string> = {
  ok: "bg-emerald-400 shadow-[0_0_10px] shadow-emerald-400 motion-safe:animate-pulse",
  fail: "bg-rose-500 shadow-[0_0_10px] shadow-rose-500",
  warn: "bg-amber-400 shadow-[0_0_10px] shadow-amber-400",
  idle: "bg-zinc-400 dark:bg-zinc-600",
};

export function Led({ state, label }: { state: LedState; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        aria-hidden
        className={`gem inline-block h-3 w-3 rotate-45 border border-emerald-500 ${LED[state]}`}
      />
      <span className="sr-only">{label}</span>
    </span>
  );
}
