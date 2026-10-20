import { asciiBar } from "@/lib/format";

/** `label ████████░░░░ value` — a bar drawn with block characters. */
export function AsciiBar({
  label,
  value,
  max,
  width = 24,
  display,
  className = "text-emerald-700 dark:text-emerald-400",
}: {
  label: string;
  value: number;
  max: number;
  width?: number;
  display?: string;
  className?: string;
}) {
  return (
    <div className="flex items-center gap-2 whitespace-pre">
      <span className="w-24 shrink-0 truncate uppercase">{label}</span>
      <span
        role="img"
        aria-label={`${label}: ${display ?? value} of ${max}`}
        className={`${className} tracking-tighter`}
      >
        {asciiBar(value, max, width)}
      </span>
      <span className="tabular-nums">{display ?? value}</span>
    </div>
  );
}
