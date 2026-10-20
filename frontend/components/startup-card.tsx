import Link from "next/link";
import type { Contact, Profile } from "@/lib/data";
import { fmtDate } from "@/lib/format";
import { CopyPitchButton } from "./copy-pitch-button";
import { PersonLinks } from "./startups/links";
import { ScoreBadge } from "./startups/score-badge";
import { TONES } from "./ui/tone";

const STAGE_TONE = {
  "pre-seed": "sky",
  seed: "emerald",
  "series a": "violet",
} as const;

export function StartupCard({
  p,
  full = false,
}: {
  p: Profile;
  full?: boolean;
}) {
  const stageKey = (
    p.funding_stage ?? ""
  ).toLowerCase() as keyof typeof STAGE_TONE;
  const tone = TONES[STAGE_TONE[stageKey] ?? "amber"];
  const contact = p.contact ?? {};
  const meta = [p.hq, p.funding_amount].filter(Boolean).join(" · ");

  return (
    <article className="border-2 border-zinc-900 bg-white shadow-[4px_4px_0_0] shadow-zinc-900 dark:border-emerald-400/60 dark:bg-black dark:shadow-emerald-400/30">
      <header className="flex items-start justify-between gap-3 border-b-2 border-zinc-900 px-3 py-2 dark:border-emerald-400/60">
        <div className="min-w-0">
          <h3 className="glow truncate font-display text-2xl leading-none">
            {full ? (
              p.company_name
            ) : (
              <Link
                href={`/startups/${p.slug}`}
                className="hover:underline focus-visible:outline-2 focus-visible:outline-emerald-500"
              >
                {p.company_name}
              </Link>
            )}
          </h3>
          <p className="mt-0.5 text-xs text-zinc-500">
            {p.website ? (
              <a
                href={p.website}
                target="_blank"
                rel="noreferrer"
                className="text-zinc-700 underline underline-offset-2 hover:no-underline dark:text-emerald-300"
              >
                {safeHost(p.website)} ↗
              </a>
            ) : (
              <span>no website yet</span>
            )}
            {meta && <span> · {meta}</span>}
          </p>
          <a
            href={p.source_url}
            target="_blank"
            rel="noreferrer"
            className="text-xs text-zinc-500 underline-offset-2 hover:underline"
          >
            via {safeHost(p.source_url)} · {fmtDate(p.discovered_at)}
          </a>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          <ScoreBadge score={p.score} />
          {p.funding_stage && (
            <span
              className={`border-2 border-zinc-900 px-2 py-0.5 text-[11px] font-semibold uppercase ${tone.panel} ${tone.border}`}
            >
              {p.funding_stage}
            </span>
          )}
        </div>
      </header>

      <div className="space-y-3 p-3">
        <p>{p.core_product}</p>
        {p.tech_stack.length > 0 && (
          <ul className="flex flex-wrap gap-1.5" aria-label="Tech stack">
            {p.tech_stack.map((t) => (
              <li
                key={t}
                className="border border-zinc-900 bg-sky-100 px-1.5 text-xs dark:border-sky-400/50 dark:bg-sky-950/50 dark:text-sky-200"
              >
                {t}
              </li>
            ))}
          </ul>
        )}
        {p.likely_bottleneck.trim() && (
          <p className="text-xs">
            <span className="font-semibold uppercase tracking-wide text-rose-700 dark:text-rose-300">
              bottleneck ›{" "}
            </span>
            {p.likely_bottleneck}
          </p>
        )}

        <ContactBlock contact={contact} full={full} />

        {p.value_prop_pitch.trim() && (
          <div className="border-l-4 border-emerald-500 bg-emerald-50 p-2 dark:bg-emerald-950/30">
            <div className="mb-1 flex items-center justify-between gap-2">
              <span className="text-[10px] font-semibold uppercase tracking-widest text-zinc-600 dark:text-zinc-400">
                pitch
              </span>
              <CopyPitchButton pitch={p.value_prop_pitch} />
            </div>
            <p>{p.value_prop_pitch}</p>
          </div>
        )}

        {p.gaps && p.gaps.length > 0 && (
          <p className="text-xs text-zinc-600 dark:text-zinc-400">
            <span className="font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-300">
              missing ›{" "}
            </span>
            {p.gaps.join(" · ")}
          </p>
        )}

        {full && p.people.length > 0 && (
          <section aria-label="People">
            <h4 className="mb-1 text-[10px] font-semibold uppercase tracking-widest text-zinc-600 dark:text-zinc-400">
              people
            </h4>
            <ul className="space-y-1.5">
              {p.people.map((x) => (
                <li key={x.name}>
                  <span className="font-semibold">{x.name}</span>{" "}
                  <span className="text-zinc-500">· {x.role}</span>{" "}
                  <PersonLinks person={x} />
                  <blockquote className="text-xs text-zinc-500">
                    “{x.evidence}”
                  </blockquote>
                </li>
              ))}
            </ul>
          </section>
        )}
        {full && p.edges.length > 0 && (
          <section aria-label="Connections">
            <h4 className="mb-1 text-[10px] font-semibold uppercase tracking-widest text-zinc-600 dark:text-zinc-400">
              connections
            </h4>
            <ul className="space-y-1">
              {p.edges.map((e, i) => (
                <li key={i}>
                  {e.src}{" "}
                  <span className="font-semibold text-violet-700 dark:text-violet-300">
                    {e.rel.replace("_", " ")}
                  </span>{" "}
                  {e.dst}
                  <blockquote className="text-xs text-zinc-500">
                    “{e.evidence}”
                  </blockquote>
                </li>
              ))}
            </ul>
          </section>
        )}
        {!full && (p.people.length > 0 || p.edges.length > 0) && (
          <p className="flex flex-wrap items-center gap-x-2 text-xs text-zinc-500">
            <span>
              {p.people.length} {p.people.length === 1 ? "person" : "people"} ·{" "}
              {p.edges.length}{" "}
              {p.edges.length === 1 ? "connection" : "connections"}
            </span>
            {p.people.slice(0, 3).map((x) => (
              <PersonLinks key={x.name} person={x} />
            ))}
          </p>
        )}
      </div>
    </article>
  );
}

/** Published contact details (first-party only); every value links to the page it was found on in `full` view. */
function ContactBlock({ contact, full }: { contact: Contact; full: boolean }) {
  const emails = contact.emails ?? [];
  const phones = contact.phones ?? [];
  const socials = Object.entries(contact.socials ?? {});
  if (
    !emails.length &&
    !phones.length &&
    !socials.length &&
    !contact.contact_page
  )
    return null;
  const shownEmails = full ? emails : emails.slice(0, 1);
  const shownPhones = full ? phones : phones.slice(0, 1);

  return (
    <section
      aria-label="Contact"
      className="space-y-1 border-2 border-dashed border-zinc-900/50 bg-violet-50 p-2 text-xs dark:border-violet-400/40 dark:bg-violet-950/30"
    >
      <h4 className="text-[10px] font-semibold uppercase tracking-widest text-zinc-600 dark:text-zinc-400">
        contact
      </h4>
      {shownEmails.map((e) => (
        <p key={e.value}>
          ✉{" "}
          <a
            href={`mailto:${e.value}`}
            className="underline underline-offset-2 hover:no-underline"
          >
            {e.value}
          </a>{" "}
          <span className="text-zinc-500">{e.kind}</span>
          {full && (
            <a
              href={e.source_url}
              target="_blank"
              rel="noreferrer"
              className="ml-1 text-zinc-500 underline"
            >
              source
            </a>
          )}
        </p>
      ))}
      {shownPhones.map((ph) => (
        <p key={ph.value}>
          ☎{" "}
          <a
            href={`tel:${ph.value}`}
            className="underline underline-offset-2 hover:no-underline"
          >
            {ph.value}
          </a>
          {full && (
            <a
              href={ph.source_url}
              target="_blank"
              rel="noreferrer"
              className="ml-1 text-zinc-500 underline"
            >
              source
            </a>
          )}
        </p>
      ))}
      {(socials.length > 0 || contact.contact_page) && (
        <p className="flex flex-wrap gap-x-3">
          {socials.map(([k, url]) => (
            <a
              key={k}
              href={url}
              target="_blank"
              rel="noreferrer"
              className="underline underline-offset-2 hover:no-underline"
            >
              {k} ↗
            </a>
          ))}
          {contact.contact_page && (
            <a
              href={contact.contact_page}
              target="_blank"
              rel="noreferrer"
              className="underline underline-offset-2 hover:no-underline"
            >
              contact page ↗
            </a>
          )}
        </p>
      )}
    </section>
  );
}

function safeHost(url: string) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}
