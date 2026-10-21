import { Art } from "./art";

const ART = ` ██████╗ █████╗ ██╗     ██╗
██╔════╝██╔══██╗██║     ██║
██║     ███████║██║     ██║
██║     ██╔══██║██║     ██║
╚██████╗██║  ██║███████╗██║
 ╚═════╝╚═╝  ╚═╝╚══════╝╚═╝`;

/** Hero: the Vitruvian scout beside a gilt CALI wordmark and a Latin legend. */
export function Banner() {
  return (
    <div className="flex items-center gap-6">
      <Art
        name="vitruvian"
        className="hidden text-[7px] leading-[1.05] opacity-90 md:block lg:text-[8px]"
      />
      <div>
        <pre
          aria-hidden
          className="ascii gilt select-none text-[11px] leading-[1.1] sm:text-sm"
        >
          {ART}
        </pre>
        <p
          aria-hidden
          className="mt-2 font-fell text-lg italic tracking-wide text-emerald-800 dark:text-emerald-300/90"
        >
          Scrutator novarum societatum
          <span className="ml-2 font-hud text-[10px] not-italic uppercase tracking-[0.3em] opacity-70">
            · codex futurum
          </span>
        </p>
      </div>
    </div>
  );
}
