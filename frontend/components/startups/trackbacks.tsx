import Link from "next/link";
import type { Trackback } from "@/lib/data";
import { fmtDate } from "@/lib/format";
import { groupFacts, trustLabel } from "@/lib/trackbacks";
import { Panel } from "@/components/ui/panel";

const TYPE_TITLE = {
  startup: "Company",
  person: "People",
  edge: "Connections",
  contact: "Contact",
} as const;

const TRUST_STYLE = {
  verified: "border-emerald-600 text-emerald-700 dark:text-emerald-300",
  matched: "border-amber-600 text-amber-700 dark:text-amber-300",
  inferred: "border-zinc-500 text-zinc-600 dark:text-zinc-400",
} as const;

function host(url: string): string {
  try {
    return new URL(url).host.replace(/^www\./, "");
  } catch {
    return url;
  }
}

/** Where every stored fact came from: each source page, the run that saw it, and when it first and last appeared. */
export function Trackbacks({ rows }: { rows: Trackback[] }) {
  const facts = groupFacts(rows);
  if (facts.length === 0) return null;
  return (
    <Panel title="Trackbacks" tone="violet">
      <div className="space-y-4">
        {(Object.keys(TYPE_TITLE) as (keyof typeof TYPE_TITLE)[]).map((type) => {
          const group = facts.filter((f) => f.type === type);
          if (group.length === 0) return null;
          return (
            <section key={type} aria-label={TYPE_TITLE[type]}>
              <h3 className="mb-1 text-[10px] font-semibold uppercase tracking-widest text-zinc-600 dark:text-zinc-400">
                {TYPE_TITLE[type]}
              </h3>
              <ul className="space-y-2">
                {group.map((f) => {
                  const trust = trustLabel(f.confidence);
                  return (
                    <li key={f.id} className="text-xs">
                      <span className="font-semibold">{f.label}</span>{" "}
                      <span
                        className={`border px-1 text-[10px] uppercase ${TRUST_STYLE[trust]}`}
                      >
                        {trust}
                      </span>
                      <span className="text-zinc-500">
                        {" "}
                        · first seen {fmtDate(f.firstSeen)}
                        {f.lastSeen !== f.firstSeen &&
                          `, last ${fmtDate(f.lastSeen)}`}
                      </span>
                      {f.evidence && (
                        <blockquote className="text-zinc-500">
                          “{f.evidence}”
                        </blockquote>
                      )}
                      <ul className="ml-3 mt-0.5 list-disc space-y-0.5">
                        {f.sources.map((s) => (
                          <li key={s.url}>
                            <a
                              href={s.url}
                              target="_blank"
                              rel="noreferrer"
                              className="underline-offset-2 hover:underline"
                            >
                              {host(s.url)}
                            </a>
                            {s.runId && !s.runId.startsWith("backfill") && (
                              <>
                                {" "}
                                <Link
                                  href={`/runs/${s.runId}`}
                                  className="text-zinc-500 underline-offset-2 hover:underline"
                                >
                                  run {s.runId}
                                </Link>
                              </>
                            )}
                            {s.seenCount > 1 && (
                              <span className="text-zinc-500">
                                {" "}
                                · seen {s.seenCount}×
                              </span>
                            )}
                          </li>
                        ))}
                      </ul>
                    </li>
                  );
                })}
              </ul>
            </section>
          );
        })}
      </div>
    </Panel>
  );
}
