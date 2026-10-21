// Each tone is an ink: emerald=forest, sky=blue, amber=ochre, rose=vermilion, violet=plum
// (see the palette remap in globals.css). Full class strings so Tailwind can see them.
export type Tone = "emerald" | "sky" | "amber" | "rose" | "violet";

export const TONES: Record<
  Tone,
  {
    panel: string;
    border: string;
    text: string;
    solid: string;
    ring: string;
    /** Sets --accent for .plate / .btn (darker on paper, lighter on charcoal). */
    accent: string;
  }
> = {
  emerald: {
    panel: "bg-emerald-100/70 dark:bg-emerald-950/55",
    border: "dark:border-emerald-400/60 dark:shadow-emerald-400/30",
    text: "text-emerald-800 dark:text-emerald-300",
    solid: "bg-emerald-300 dark:bg-emerald-400",
    ring: "focus-visible:outline-emerald-500",
    accent:
      "[--accent:var(--color-emerald-700)] dark:[--accent:var(--color-emerald-400)]",
  },
  sky: {
    panel: "bg-sky-100/70 dark:bg-sky-950/55",
    border: "dark:border-sky-400/60 dark:shadow-sky-400/30",
    text: "text-sky-800 dark:text-sky-300",
    solid: "bg-sky-300 dark:bg-sky-400",
    ring: "focus-visible:outline-sky-500",
    accent:
      "[--accent:var(--color-sky-700)] dark:[--accent:var(--color-sky-400)]",
  },
  amber: {
    panel: "bg-amber-100/70 dark:bg-amber-950/55",
    border: "dark:border-amber-400/60 dark:shadow-amber-400/30",
    text: "text-amber-800 dark:text-amber-300",
    solid: "bg-amber-300 dark:bg-amber-400",
    ring: "focus-visible:outline-amber-500",
    accent:
      "[--accent:var(--color-amber-700)] dark:[--accent:var(--color-amber-400)]",
  },
  rose: {
    panel: "bg-rose-100/70 dark:bg-rose-950/55",
    border: "dark:border-rose-400/60 dark:shadow-rose-400/30",
    text: "text-rose-800 dark:text-rose-300",
    solid: "bg-rose-300 dark:bg-rose-400",
    ring: "focus-visible:outline-rose-500",
    accent:
      "[--accent:var(--color-rose-700)] dark:[--accent:var(--color-rose-400)]",
  },
  violet: {
    panel: "bg-violet-100/70 dark:bg-violet-950/55",
    border: "dark:border-violet-400/60 dark:shadow-violet-400/30",
    text: "text-violet-800 dark:text-violet-300",
    solid: "bg-violet-300 dark:bg-violet-400",
    ring: "focus-visible:outline-violet-500",
    accent:
      "[--accent:var(--color-violet-700)] dark:[--accent:var(--color-violet-400)]",
  },
};
