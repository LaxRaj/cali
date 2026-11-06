import Link from "next/link";
import type { Profile } from "@/lib/data";
import { fmtDate, humanize } from "@/lib/format";

const H = "mb-1 text-[10px] font-semibold uppercase tracking-widest text-zinc-600 dark:text-zinc-400";

/** Qualification axes from backend/rating.py (0-1 each): why a lead is or is not worth pursuing yet. */
export function Axes({ axes }: { axes?: Record<string, number> }) {
  const entries = Object.entries(axes ?? {});
  if (!entries.length) return null;
  return (
    <section aria-label="Qualification">
      <h4 className={H}>qualification</h4>
      <ul className="grid grid-cols-2 gap-x-4 gap-y-0.5 text-xs sm:grid-cols-3">
        {entries.map(([k, v]) => (
          <li key={k} className="flex justify-between gap-2">
            <span>{humanize(k)}</span>
            <span className="tabular-nums">{Math.round((Number(v) || 0) * 100)}%</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function Signals({ signals }: { signals?: Profile["signals"] }) {
  if (!signals?.length) return null;
  return (
    <section aria-label="Signals">
      <h4 className={H}>signals</h4>
      <ul className="space-y-0.5 text-xs">
        {signals.map((s, i) => (
          <li key={`${s.type}-${i}`}>
            <span className="font-semibold uppercase text-emerald-700 dark:text-emerald-300">{humanize(s.type)}</span>{" "}
            {s.roles?.length ? s.roles.slice(0, 4).join(", ") : ""}{" "}
            <a href={s.url} target="_blank" rel="noreferrer" className="text-zinc-600 underline dark:text-zinc-400">
              {humanize(s.source)}
              {s.posted_at || s.seen_at ? ` · ${fmtDate(s.posted_at || s.seen_at)}` : ""}
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function ProductAccess({ contact }: { contact?: Profile["contact"] }) {
  const links = contact?.product_access ?? [];
  const tech = contact?.site_tech ?? [];
  if (!links.length && !tech.length) return null;
  return (
    <section aria-label="Product and site">
      {links.length > 0 && (
        <>
          <h4 className={H}>try it first</h4>
          <p className="flex flex-wrap gap-x-3 text-xs">
            {links.map((l) => (
              <a key={l.url} href={l.url} target="_blank" rel="noreferrer" className="underline underline-offset-2">
                {l.label} ↗
              </a>
            ))}
          </p>
        </>
      )}
      {tech.length > 0 && (
        <>
          <h4 className={`${H} mt-2`}>site built with</h4>
          <ul className="flex flex-wrap gap-1.5" aria-label="Website technology">
            {tech.map((t) => (
              <li key={t.name} title={t.category} className="border border-dashed border-zinc-900/30 px-1.5 text-xs dark:border-zinc-100/30">
                {t.name}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

export function SimilarStrip({ similar }: { similar?: Profile["similar"] }) {
  if (!similar?.length) return null;
  return (
    <section aria-label="Similar companies">
      <h4 className={H}>similar companies</h4>
      <ul className="flex flex-wrap gap-2 text-xs">
        {similar.map((s) => (
          <li key={s.slug}>
            <Link href={`/startups/${s.slug}`} className="border border-zinc-900/25 px-1.5 py-0.5 hover:bg-sky-100 dark:border-sky-400/50 dark:hover:bg-sky-950">
              {s.company_name} <span className="text-zinc-600 dark:text-zinc-400">{Math.round(s.similarity * 100)}%</span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

const KIND_LABEL: Record<string, string> = {
  discovered: "found",
  learned: "learned",
  hiring: "hiring",
  funding: "funding",
  launch: "launch",
  seeking_freelancer: "wants help",
};

/** What we learned about the company, when, and from which page (newest first). */
export function Timeline({ events }: { events?: Profile["timeline"] }) {
  if (!events?.length) return null;
  return (
    <section aria-label="Timeline">
      <h4 className={H}>timeline</h4>
      <ol className="space-y-1.5 border-l-2 border-zinc-900/25 pl-3 text-xs dark:border-zinc-100/25">
        {events.map((e, i) => (
          <li key={`${e.at}-${i}`}>
            <span className="tabular-nums text-zinc-600 dark:text-zinc-400">{fmtDate(e.at)}</span>{" "}
            <span className="font-semibold uppercase">{KIND_LABEL[e.kind] ?? humanize(e.kind)}</span>
            {e.items.length > 0 && (
              <span>
                {" "}
                · {e.items.slice(0, 3).join(" · ")}
                {e.count > 3 ? ` · +${e.count - 3} more` : ""}
              </span>
            )}
            {e.source_urls[0] && (
              <a href={e.source_urls[0]} target="_blank" rel="noreferrer" className="ml-1 text-zinc-600 underline dark:text-zinc-400">
                source
              </a>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}
