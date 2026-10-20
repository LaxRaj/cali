import Link from "next/link";
import { Banner } from "@/components/ascii/banner";
import { Empty } from "@/components/ascii/art";
import { AsciiBar } from "@/components/charts/ascii-bar";
import { Funnel } from "@/components/charts/funnel";
import { RunCalendar } from "@/components/charts/run-calendar";
import { Sparkline } from "@/components/charts/sparkline";
import { Led } from "@/components/ui/led";
import { Panel } from "@/components/ui/panel";
import { RetroLink } from "@/components/ui/retro-button";
import { Stat } from "@/components/ui/stat";
import { StartupCard } from "@/components/startup-card";
import {
  readGraph,
  readIndex,
  readProfiles,
  readRun,
  TOKEN_BUDGET,
} from "@/lib/data";
import { fmtDateTime, fmtDuration, fmtTokens } from "@/lib/format";

export default function OverviewPage() {
  const runs = readIndex();
  const profiles = readProfiles();
  const graph = readGraph();
  const latest = runs.at(-1);
  const detail = latest ? readRun(latest.run_id) : null;
  const recent = runs.slice(-30);
  const passRate = recent.length
    ? Math.round((recent.filter((r) => r.passed).length / recent.length) * 100)
    : 0;
  const people = graph.nodes.filter((n) => n.type === "person").length;
  const topNodes = graph.nodes.slice(0, 6);
  const srcMax = Math.max(...Object.values(latest?.sources ?? { x: 1 }), 1);

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <Banner />
          <p className="cursor mt-2 text-xs text-zinc-600 dark:text-emerald-400/80">
            connection &amp; builder dashboard — every process, in one place
          </p>
        </div>
        {latest ? (
          <div className="flex items-center gap-2 border-2 border-zinc-900 bg-white px-3 py-1.5 text-xs dark:border-emerald-400/60 dark:bg-black">
            <Led
              state={latest.passed ? "ok" : "fail"}
              label={latest.passed ? "passed" : "failed"}
            />
            <span>
              SYSTEM {latest.passed ? "NOMINAL" : "LAST RUN FAILED"} ·{" "}
              {fmtDateTime(latest.started_at)}
            </span>
          </div>
        ) : null}
      </header>

      {!latest ? (
        <Panel title="No runs yet" tone="amber">
          <Empty art="radio" title="Waiting for the first signal">
            The scout hasn&apos;t produced any data yet. Trigger the{" "}
            <code>scout</code> workflow (or run <code>pipeline.py</code>{" "}
            locally); this page fills in on the next build. For a preview with
            fictional data run <code>npm run dev:demo</code>.
          </Empty>
        </Panel>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
            <Stat
              label="Startups"
              value={profiles.length}
              sub="in the store"
              tone="emerald"
            />
            <Stat
              label="People"
              value={people}
              sub="founders · investors"
              tone="sky"
            />
            <Stat
              label="Connections"
              value={graph.edges.length}
              sub="evidenced links"
              tone="violet"
            />
            <Stat
              label="Pass rate"
              value={`${passRate}%`}
              sub={`last ${recent.length} runs`}
              tone="amber"
            />
            <Stat
              label="Tokens today"
              value={fmtTokens(latest.tokens)}
              sub={`${Math.round((latest.tokens / TOKEN_BUDGET) * 100)}% of ${fmtTokens(TOKEN_BUDGET)} free tier`}
              tone={latest.tokens / TOKEN_BUDGET > 0.8 ? "rose" : "emerald"}
            />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Panel
              title="Pipeline funnel"
              tone="sky"
              right={
                <Link href={`/runs/${latest.run_id}`} className="underline">
                  latest run →
                </Link>
              }
            >
              <Funnel funnel={latest.funnel} />
            </Panel>
            <Panel
              title="Process log"
              tone="emerald"
              right={<span>{fmtDuration(latest.duration_s)} total</span>}
            >
              {detail ? (
                <ul className="space-y-1">
                  {detail.stages.map((s) => (
                    <li key={s.name} className="flex items-center gap-2">
                      <Led
                        state={s.status === "ok" ? "ok" : "fail"}
                        label={s.status}
                      />
                      <span className="w-20 uppercase">{s.name}</span>
                      <span className="flex-1 truncate text-xs text-zinc-600 dark:text-zinc-400">
                        {Object.entries(s.counts)
                          .map(([k, v]) => `${k}=${v}`)
                          .join("  ")}
                      </span>
                      <span className="tabular-nums">
                        {fmtDuration(s.duration_s)}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-zinc-500">
                  run detail not available
                </p>
              )}
              {latest.failures.length > 0 && (
                <p className="mt-2 border-l-4 border-rose-500 pl-2 text-xs text-rose-700 dark:text-rose-300">
                  {latest.failures.join(" · ")}
                </p>
              )}
            </Panel>

            <Panel
              title="Run history"
              tone="violet"
              right={<span>{recent.length} runs</span>}
            >
              <RunCalendar runs={recent} />
              <p className="mt-2 text-xs text-zinc-600 dark:text-zinc-400">
                ■ green passed · ■ red failed gates · click a square for details
              </p>
            </Panel>
            <Panel
              title="Token burn"
              tone="amber"
              right={<span>budget {fmtTokens(TOKEN_BUDGET)}/day</span>}
            >
              <div className="text-amber-700 dark:text-amber-300">
                <Sparkline
                  values={recent.map((r) => r.tokens)}
                  reference={TOKEN_BUDGET}
                  max={TOKEN_BUDGET}
                  label="Tokens used per run, with the daily free-tier budget as a dashed line"
                />
              </div>
            </Panel>

            <Panel
              title="Sources"
              tone="rose"
              right={<span>candidates, latest run</span>}
            >
              <div className="space-y-1">
                {Object.entries(latest.sources).map(([s, v]) => (
                  <AsciiBar
                    key={s}
                    label={s}
                    value={v}
                    max={srcMax}
                    width={22}
                    className="text-rose-700 dark:text-rose-300"
                  />
                ))}
              </div>
            </Panel>
            <Panel
              title="Most connected"
              tone="sky"
              right={
                <Link href="/network" className="underline">
                  network →
                </Link>
              }
            >
              {topNodes.length ? (
                <ul className="space-y-1">
                  {topNodes.map((n) => (
                    <li key={n.id} className="flex justify-between gap-3">
                      <span className="truncate">
                        <span aria-hidden>
                          {n.type === "startup"
                            ? "■"
                            : n.type === "person"
                              ? "●"
                              : "◆"}{" "}
                        </span>
                        {n.label}
                      </span>
                      <span className="tabular-nums">{n.degree}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-zinc-500">no connections yet</p>
              )}
            </Panel>
          </div>

          <section aria-label="Latest findings" className="space-y-3">
            <div className="flex items-end justify-between">
              <h2 className="glow font-display text-3xl uppercase tracking-wider">
                Latest findings
              </h2>
              <RetroLink href="/startups" tone="emerald">
                All startups →
              </RetroLink>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              {profiles.slice(0, 4).map((p) => (
                <StartupCard key={p.slug} p={p} />
              ))}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
