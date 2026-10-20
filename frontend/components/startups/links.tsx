import type { Person } from "@/lib/data";

const PLATFORMS = [
  { key: "linkedin", label: "in" },
  { key: "twitter", label: "x" },
  { key: "github", label: "gh" },
  { key: "homepage", label: "web" },
] as const;

/** Small pastel chips linking to a person's public profiles. Renders nothing when there are none. */
export function PersonLinks({ person }: { person: Person }) {
  const links = PLATFORMS.filter((p) => person[p.key]);
  if (links.length === 0) return null;
  return (
    <span className="inline-flex gap-1">
      {links.map((p) => (
        <a
          key={p.key}
          href={person[p.key]}
          target="_blank"
          rel="noreferrer"
          aria-label={`${person.name} on ${p.key}`}
          title={`${p.key}${person.link_source ? ` — found on ${person.link_source}` : ""}`}
          className="border border-zinc-900 bg-sky-200 px-1 text-[10px] font-semibold uppercase leading-4 hover:bg-sky-300 focus-visible:outline-2 focus-visible:outline-emerald-500 dark:border-sky-400/60 dark:bg-sky-950 dark:text-sky-200"
        >
          {p.label}
        </a>
      ))}
    </span>
  );
}
