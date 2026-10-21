"use client";

/** Old-style rocker toggle. Real button with role="switch" so it works with keyboard + screen readers. */
export function RockerSwitch({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  label: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className="group inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wide focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-500"
    >
      <span className="relative inline-block h-6 w-11 border border-zinc-900/25 bg-zinc-200 shadow-[inset_0_2px_0] shadow-zinc-400 dark:border-emerald-400/70 dark:bg-black dark:shadow-emerald-900">
        <span
          aria-hidden
          className={`absolute top-0 h-full w-1/2 border-x-2 border-zinc-900/25 transition-all dark:border-emerald-400/70 ${
            checked
              ? "left-1/2 bg-emerald-300 dark:bg-emerald-500"
              : "left-0 bg-rose-200 dark:bg-zinc-700"
          }`}
        />
      </span>
      <span aria-hidden>{checked ? "ON" : "OFF"}</span>
    </button>
  );
}
