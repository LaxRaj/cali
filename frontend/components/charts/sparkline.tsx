/** Tiny SVG line chart. Inherits color from the parent text color. `reference` draws a dashed reference line. */
export function Sparkline({
  values,
  width = 240,
  height = 56,
  max,
  reference,
  label,
}: {
  values: number[];
  width?: number;
  height?: number;
  max?: number;
  reference?: number;
  label: string;
}) {
  if (values.length === 0)
    return <p className="text-xs text-zinc-500">no data</p>;
  const top = Math.max(max ?? 0, reference ?? 0, ...values, 1);
  const pad = 4;
  const x = (i: number) =>
    pad +
    (values.length === 1
      ? (width - 2 * pad) / 2
      : (i * (width - 2 * pad)) / (values.length - 1));
  const y = (v: number) => height - pad - (v / top) * (height - 2 * pad);
  const pts = values
    .map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`)
    .join(" ");
  const last = values.length - 1;
  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={label}
      className="h-14 w-full"
    >
      {reference !== undefined && (
        <line
          x1={pad}
          x2={width - pad}
          y1={y(reference)}
          y2={y(reference)}
          stroke="currentColor"
          strokeDasharray="3 3"
          opacity="0.35"
        />
      )}
      <polyline
        points={pts}
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinejoin="round"
      />
      <rect
        x={x(last) - 3}
        y={y(values[last]) - 3}
        width="6"
        height="6"
        fill="currentColor"
      />
    </svg>
  );
}
