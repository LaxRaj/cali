const PIECES = {
  computer: `  .----------.
  | > cali_ |
  |  ______  |
  '----------'
   _|______|_
  /__________\\`,
  floppy: `  .-----------.
  | [=]   ___ |
  |      |   ||
  |  ___ |___||
  | |___|     |
  '-----------'`,
  radio: `     \\|/
      |
     /|\\
    / | \\
   /__|__\\
  [ ))) (((]`,
} as const;

/** Decorative ASCII art for empty states and headers. Always hidden from assistive tech. */
export function Art({
  name,
  className = "",
}: {
  name: keyof typeof PIECES;
  className?: string;
}) {
  return (
    <pre
      aria-hidden
      className={`ascii select-none text-[11px] leading-tight text-emerald-700 dark:text-emerald-400 ${className}`}
    >
      {PIECES[name]}
    </pre>
  );
}

export function Empty({
  art = "computer",
  title,
  children,
}: {
  art?: keyof typeof PIECES;
  title: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-3 py-8 text-center">
      <Art name={art} />
      <p className="font-display text-2xl uppercase tracking-wider">{title}</p>
      {children && (
        <p className="max-w-md text-xs text-zinc-600 dark:text-zinc-400">
          {children}
        </p>
      )}
    </div>
  );
}
