import Link from "next/link";
import type { Profile } from "@/lib/data";
import { fmtDate } from "@/lib/format";
import { CopyPitchButton } from "./copy-pitch-button";
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
          <a
            href={p.source_url}
            target="_blank"
            rel="noreferrer"
            className="text-xs text-zinc-500 underline-offset-2 hover:underline"
          >
            {safeHost(p.source_url)} ↗ · {fmtDate(p.discovered_at)}
          </a>
        </div>
        {p.funding_stage && (
          <span
            className={`shrink-0 border-2 border-zinc-900 px-2 py-0.5 text-[11px] font-semibold uppercase ${tone.panel} ${tone.border}`}
          >
            {p.funding_stage}
          </span>
        )}
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

        {full && p.people.length > 0 && (
          <section aria-label="People">
            <h4 className="mb-1 text-[10px] font-semibold uppercase tracking-widest text-zinc-600 dark:text-zinc-400">
              people
            </h4>
            <ul className="space-y-1">
              {p.people.map((x) => (
                <li key={x.name}>
                  <span className="font-semibold">{x.name}</span>{" "}
                  <span className="text-zinc-500">· {x.role}</span>
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
          <p className="text-xs text-zinc-500">
            {p.people.length} {p.people.length === 1 ? "person" : "people"} ·{" "}
            {p.edges.length}{" "}
            {p.edges.length === 1 ? "connection" : "connections"}
          </p>
        )}
      </div>
    </article>
  );
}

function safeHost(url: string) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}
