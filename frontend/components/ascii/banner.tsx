import { Art } from "./art";

/** Overview hero: a small engraved Vitruvian beside a large serif title. */
export function Banner() {
  return (
    <div className="flex items-center gap-6">
      <Art
        name="vitruvian"
        className="hidden !text-[6px] !leading-[1.05] opacity-80 md:block"
      />
      <h1 className="serif text-6xl leading-[0.95] sm:text-7xl">
        Every lead,
        <br />
        <span className="italic text-rose-600 dark:text-rose-400">
          in one place.
        </span>
      </h1>
    </div>
  );
}
