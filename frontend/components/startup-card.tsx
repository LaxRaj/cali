import type { Finding } from "@/lib/brief";
import { CopyPitchButton } from "./copy-pitch-button";

function hostname(url: string) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

export function StartupCard({ f }: { f: Finding }) {
  const name = f.company_name.trim() || "Unnamed";
  return (
    <article
      className={`rounded-xl border p-5 border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900/60 ${
        f.is_relevant ? "" : "opacity-60"
      }`}
    >
      <header className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h2 className="truncate text-lg font-semibold text-zinc-900 dark:text-zinc-50">
            {name}
          </h2>
          <a
            href={f.source_url}
            target="_blank"
            rel="noreferrer"
            className="text-xs text-zinc-500 underline-offset-2 hover:underline dark:text-zinc-500"
          >
            {hostname(f.source_url)} ↗
          </a>
        </div>
        <span
          className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium ${
            f.is_relevant
              ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-400"
              : "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400"
          }`}
        >
          {f.is_relevant ? "Relevant" : "Skip"}
        </span>
      </header>

      {f.tech_stack.length > 0 && (
        <ul className="mt-4 flex flex-wrap gap-1.5" aria-label="Tech stack">
          {f.tech_stack.map((t) => (
            <li
              key={t}
              className="rounded-md bg-zinc-100 px-2 py-0.5 font-mono text-xs text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300"
            >
              {t}
            </li>
          ))}
        </ul>
      )}

      {f.people && f.people.length > 0 && (
        <section className="mt-4" aria-label="People">
          <h3 className="text-xs font-medium uppercase tracking-wide text-zinc-500">
            People
          </h3>
          <ul className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-sm text-zinc-700 dark:text-zinc-300">
            {f.people.map((p) => (
              <li key={`${p.name}|${p.org}`}>
                <span className="font-medium text-zinc-900 dark:text-zinc-100">
                  {p.name}
                </span>
                {p.role && <span className="text-zinc-500"> · {p.role}</span>}
              </li>
            ))}
          </ul>
        </section>
      )}

      {f.edges && f.edges.length > 0 && (
        <section className="mt-4" aria-label="Connections">
          <h3 className="text-xs font-medium uppercase tracking-wide text-zinc-500">
            Connections
          </h3>
          <ul className="mt-1.5 space-y-1 text-sm text-zinc-700 dark:text-zinc-300">
            {f.edges.map((e) => (
              <li key={`${e.src}|${e.rel}|${e.dst}`} title={e.evidence}>
                {e.src}{" "}
                <span className="font-mono text-xs text-emerald-600 dark:text-emerald-400">
                  {e.rel.replace("_", " ")}
                </span>{" "}
                {e.dst}
              </li>
            ))}
          </ul>
        </section>
      )}

      <dl className="mt-4 space-y-4 text-sm">
        {f.likely_bottleneck.trim() && (
          <div>
            <dt className="text-xs font-medium uppercase tracking-wide text-zinc-500">
              Likely bottleneck
            </dt>
            <dd className="mt-1 text-zinc-700 dark:text-zinc-300">
              {f.likely_bottleneck}
            </dd>
          </div>
        )}
        {f.value_prop_pitch.trim() && (
          <div>
            <div className="flex items-center justify-between gap-4">
              <dt className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                Pitch
              </dt>
              <CopyPitchButton pitch={f.value_prop_pitch} />
            </div>
            <dd className="mt-2 rounded-lg border-l-2 border-emerald-500 bg-zinc-50 p-3 text-zinc-800 dark:bg-zinc-950/60 dark:text-zinc-200">
              {f.value_prop_pitch}
            </dd>
          </div>
        )}
      </dl>
    </article>
  );
}
