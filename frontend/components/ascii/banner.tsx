const ART = ` ██████╗ █████╗ ██╗     ██╗
██╔════╝██╔══██╗██║     ██║
██║     ███████║██║     ██║
██║     ██╔══██║██║     ██║
╚██████╗██║  ██║███████╗██║
 ╚═════╝╚═╝  ╚═╝╚══════╝╚═╝`;

export function Banner() {
  return (
    <pre
      aria-hidden
      className="glow ascii select-none text-[11px] leading-[1.1] text-emerald-700 sm:text-sm dark:text-emerald-400"
    >
      {ART}
    </pre>
  );
}
