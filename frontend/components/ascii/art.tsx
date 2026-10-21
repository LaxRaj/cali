// Renaissance instruments, engraved in monospace. Keys keep their old names so call sites don't change:
// computer -> astrolabe, floppy -> codex, radio -> armillary sphere.
const PIECES = {
  vitruvian: String.raw`     +---------------------------------------+
     |             .............             |
     |   \\    .....    .-.    .....    //   |
     |     \\\\.        ( )        .////     |
     |    ...  \\\\     '-'     ////  ...    |
     |   ..        \\\\  |  ////        ..   |
     | ...             \\|//             ... |
     |===================+===================|
     |.                  |                  .|
     |.                  |                  .|
     |                   |                   |
     |                   o                   |
     |                 // \\                 |
     |               // | | \\               |
     |'            //   | |   \\            '|
     |'          //     | |     \\          '|
     | '       //       | |       \\       ' |
     | '''   //         | |         \\   ''' |
     |   ''//           | |           \\''   |
     |    /''           | |           ''\    |
     +---------------------------------------+
               '''''           '''''
                   '''''''''''''`,
  computer: String.raw`       _.-"""""-._
     .'  .  |  .  '.
    /  .    |    .  \
   |  .--.  |  .--.  |
   |-(--*---O---*--)-|
   |  '--'  |  '--'  |
    \  '    |    '  /
     '.  '  |  '  .'
       '-._____.-'
        [ nova ]`,
  floppy: String.raw`   .-"""""""-.-"""""""-.
  / ~~~~~~~  | ~~~~~~~  \
 /  ~~~~~    |  ~~~~~~   \
/   ~~~~~~~  |  ~~~~      \
|   ~~~       |  ~~~~~~~   |
'-.____________|___________.-'
     CODEX  ·  LIBER I`,
  radio: String.raw`       .-"""-.
     .' _.-._ '.
    / .'  |  '. \
   | |----+----| |
    \ '.  |  .' /
     '. '-.-' .'
       '-.|.-'
        _|_|_
       (_____)
   · armilla signa ·`,
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
      className={`ascii select-none text-[11px] leading-tight text-zinc-600 dark:text-zinc-400 ${className}`}
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
  art?: Exclude<keyof typeof PIECES, "vitruvian">;
  title: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-4 py-8 text-center">
      <Art name={art} />
      <p className="serif text-2xl">
        {title}
      </p>
      {children && (
        <p className="max-w-md text-xs leading-relaxed text-zinc-600 dark:text-zinc-400">
          {children}
        </p>
      )}
    </div>
  );
}
