import Link from "next/link";
import { Banner } from "@/components/ascii/banner";
import { Empty } from "@/components/ascii/art";
import { AsciiBar } from "@/components/charts/ascii-bar";
import { Funnel } from "@/components/charts/funnel";
import { RunCalendar } from "@/components/charts/run-calendar";
import { Sparkline } from "@/components/charts/sparkline";
import { DailyTokenMeter } from "@/components/runs/daily-token-meter";
import { FreshnessIndicator } from "@/components/runs/freshness-indicator";
import { QuotaBanner } from "@/components/runs/quota-banner";
import { Led } from "@/components/ui/led";
import { Panel } from "@/components/ui/panel";
import { RetroLink } from "@/components/ui/retro-button";
import { Stat } from "@/components/ui/stat";
import { StartupCard } from "@/components/startup-card";
import {
  readEnrichLastRun,
  readGraph,
  readIndex,
  readOutcomes,
  readOutreachSummary,
  readProfiles,
  readRun,
} from "@/lib/data";
import { fmtDate, fmtDateTime, fmtDuration, fmtTokens } from "@/lib/format";
import {
  dailyBudget,
  dailyTokens,
  dailyTotals,
  dayKey,
  latestFindings,
  latestRun,
  outreachFunnel,
  passRate as computePassRate,
  runState,
  runsOnDay,
  sortedRuns,
} from "@/lib/metrics";

export default function OverviewPage() {
  const runs = readIndex();
  const profiles = readProfiles();
  const graph = readGraph();
  const latest = latestRun(runs);
  const state = latest ? runState(latest) : undefined;
  const detail = latest ? readRun(latest.run_id) : null;
  const recent = sortedRuns(runs).slice(-30); // the index order is not trusted: sort by run_id first
  const outcomes = readOutcomes();
  const funnel = outreachFunnel(profiles, outcomes);
  const summary = readOutreachSummary();
  const enrich = readEnrichLastRun();
  const watched = profiles.filter((p) => (p.watch?.length ?? 0) > 0);
  const slugByName = new Map(profiles.map((p) => [p.company_name.trim().toLowerCase(), p.slug]));
  const rate = computePassRate(runs, 30);
  // "Today" is the UTC day of the newest run (the Groq quota resets at 00:00 UTC): every run of it counts.
  const today = latest ? dayKey(latest.started_at) : "";
  const todayRuns = runsOnDay(runs, today);
  const todayTokens = dailyTokens(runs, today);
  const budget = dailyBudget(runs, today);
  const days = dailyTotals(runs).slice(-14);
  const people = graph.nodes.filter((n) => n.type === "person").length;
  const topNodes = graph.nodes.slice(0, 6);
  const scored = profiles.filter((p) => p.score !== undefined);
  const avgScore = scored.length
    ? Math.round(scored.reduce((t, p) => t + (p.score ?? 0), 0) / scored.length)
    : 0;
  const pct = (n: number) =>
    profiles.length ? Math.round((n / profiles.length) * 100) : 0;
  const completeness = [
    ["website", profiles.filter((p) => p.website).length],
    [
      "email",
      profiles.filter((p) => (p.contact?.emails?.length ?? 0) > 0).length,
    ],
    [
      "phone",
      profiles.filter((p) => (p.contact?.phones?.length ?? 0) > 0).length,
    ],
    ["people", profiles.filter((p) => p.people.length > 0).length],
    [
      "profiles",
      profiles.filter((p) =>
        p.people.some((x) => x.linkedin || x.twitter || x.github),
      ).length,
    ],
    [
      "investors",
      profiles.filter((p) =>
        p.edges.some((e) => e.rel === "invested_in" || e.rel === "backed_by"),
      ).length,
    ],
  ] as const;
  const dec = detail?.decisions;
  const queue = [...profiles]
    .filter((p) => p.decision && p.decision.action === "contact_now")
    .sort((a, b) => (b.decision?.priority ?? 0) - (a.decision?.priority ?? 0))
    .slice(0, 3);
  const stats = detail?.feedback?.source_stats ?? {};
  const caps = detail?.feedback?.caps ?? {};
  const srcMax = Math.max(...Object.values(latest?.sources ?? { x: 1 }), 1);

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <Banner />
          <p className="cursor mt-4 text-xs text-zinc-600 dark:text-zinc-400">
            connection &amp; builder dashboard — every process, in one place
          </p>
        </div>
        {latest ? (
          <div className="flex items-center gap-2 border border-zinc-900/20 px-3 py-1.5 text-xs dark:border-zinc-100/20">
            <Led
              state={
                state === "passed" ? "ok" : state === "quota" ? "warn" : "fail"
              }
              label={state ?? "unknown"}
            />
            <span>
              SYSTEM{" "}
              {state === "passed"
                ? "NOMINAL"
                : state === "quota"
                  ? "QUOTA REACHED"
                  : "LAST RUN FAILED"}{" "}
              · {fmtDateTime(latest.started_at)}
            </span>
            <FreshnessIndicator latestAt={latest.started_at} />
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
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
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
              value={rate.pct === null ? "—" : `${rate.pct}%`}
              sub={`last ${recent.length} runs${rate.skipped ? ` · ${rate.skipped} quota-limited, not counted` : ""}`}
              tone="amber"
            />
            <Stat
              label="Avg lead score"
              value={avgScore}
              sub={`${profiles.filter((p) => (p.score ?? 0) >= 75).length} leads ready (75+)`}
              tone="violet"
            />
            <Stat
              label="Tokens today"
              value={fmtTokens(todayTokens)}
              sub={`${todayRuns.length} runs on ${fmtDate(`${today}T00:00:00Z`)} UTC · ${Math.round((todayTokens / budget) * 100)}% of ${fmtTokens(budget)}`}
              tone={todayTokens / budget > 0.8 ? "rose" : "emerald"}
            />
          </div>

          <QuotaBanner state={state} />

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
                <span className="text-emerald-600 dark:text-emerald-400">■</span> passed ·{" "}
                <span className="text-rose-600 dark:text-rose-400">■×</span> failed gates ·{" "}
                <span className="text-amber-600 dark:text-amber-400">■q</span> stopped at the Groq
                quota (not a failure) · click a square for details
              </p>
            </Panel>
            <Panel
              title="Token burn"
              tone="amber"
              right={<span>budget {fmtTokens(budget)}/day</span>}
            >
              <DailyTokenMeter runs={todayRuns} budget={budget} />
              <div className="mt-3 text-amber-700 dark:text-amber-300">
                <Sparkline
                  values={days.map((d) => d.tokens)}
                  reference={budget}
                  max={Math.max(budget, ...days.map((d) => d.budget), ...days.map((d) => d.tokens))}
                  label="Total tokens used per day (UTC), with the daily budget as a dashed line"
                />
                <p className="text-[11px] text-zinc-600 dark:text-zinc-400">
                  last {days.length} days · all runs of a day added together
                </p>
              </div>
            </Panel>

            <Panel
              title="Sources"
              tone="rose"
              right={
                <span>
                  candidates, latest run{state === "quota" && " (partial)"}
                </span>
              }
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
              title="Decision engine"
              tone="sky"
              right={<span>{dec?.provider ?? "-"} provider</span>}
            >
              {dec ? (
                <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                  <dt className="text-zinc-600 dark:text-zinc-400">
                    decisions
                  </dt>
                  <dd className="text-right tabular-nums">{dec.calls}</dd>
                  <dt className="text-zinc-600 dark:text-zinc-400">
                    avg latency
                  </dt>
                  <dd className="text-right tabular-nums">
                    {dec.avg_latency_ms} ms
                  </dd>
                  <dt className="text-zinc-600 dark:text-zinc-400">
                    pages gated (skipped)
                  </dt>
                  <dd className="text-right tabular-nums">{dec.gated_pages}</dd>
                  <dt className="text-zinc-600 dark:text-zinc-400">
                    LLM tokens saved (est.)
                  </dt>
                  <dd className="text-right tabular-nums">
                    {fmtTokens(dec.tokens_saved_est)}
                  </dd>
                  <dt className="text-zinc-600 dark:text-zinc-400">
                    fallbacks to local
                  </dt>
                  <dd className="text-right tabular-nums">{dec.fallbacks}</dd>
                </dl>
              ) : (
                <p className="text-xs text-zinc-500">
                  no decision stats for this run
                </p>
              )}
            </Panel>
            <Panel
              title="Action queue"
              tone="rose"
              right={
                <Link href="/queue" className="underline">
                  all →
                </Link>
              }
            >
              {queue.length ? (
                <ul className="space-y-2">
                  {queue.map((p) => (
                    <li key={p.slug}>
                      <Link
                        href={`/startups/${p.slug}`}
                        className="font-semibold underline underline-offset-2 hover:no-underline"
                      >
                        {p.company_name}
                      </Link>{" "}
                      <span className="text-[11px] uppercase text-rose-700 dark:text-rose-300">
                        {p.decision?.urgency}
                      </span>
                      <p className="text-xs text-zinc-600 dark:text-zinc-400">
                        {p.decision?.next_step}
                      </p>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-zinc-500">
                  nothing to contact right now
                </p>
              )}
            </Panel>
            <Panel
              title="Hit rate by source"
              tone="amber"
              right={<span>valid ÷ crawled · crawl cap</span>}
            >
              {Object.keys(stats).length ? (
                <div className="space-y-1">
                  {Object.entries(stats).map(([src, st]) => (
                    <AsciiBar
                      key={src}
                      label={src}
                      value={Math.round(st.yield * 100)}
                      max={100}
                      width={16}
                      display={`${st.accepted}/${st.crawled} · cap ${caps[src] ?? "-"}`}
                      className="text-amber-700 dark:text-amber-300"
                    />
                  ))}
                </div>
              ) : (
                <p className="text-xs text-zinc-500">
                  builds up after a few runs
                </p>
              )}
              <p className="mt-2 text-xs text-zinc-600 dark:text-zinc-400">
                Sources that pay off get more of the next run&apos;s crawl
                budget.
              </p>
            </Panel>
            <Panel
              title="Lead completeness"
              tone="violet"
              right={<span>{profiles.length} leads</span>}
            >
              <div className="space-y-1">
                {completeness.map(([label, n]) => (
                  <AsciiBar
                    key={label}
                    label={label}
                    value={pct(n)}
                    max={100}
                    width={16}
                    display={`${pct(n)}%`}
                    className="text-violet-700 dark:text-violet-300"
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
                  {topNodes.map((n) => {
                    const slug = n.type === "startup" ? slugByName.get(n.id) : undefined;
                    return (
                    <li key={n.id} className="flex justify-between gap-3">
                      <span className="truncate">
                        <span aria-hidden>
                          {n.type === "startup"
                            ? "■"
                            : n.type === "person"
                              ? "●"
                              : "◆"}{" "}
                        </span>
                        {slug ? (
                          <Link href={`/startups/${slug}`} className="underline underline-offset-2 hover:no-underline">
                            {n.label}
                          </Link>
                        ) : (
                          <Link href={`/network?focus=${encodeURIComponent(n.id)}`} className="hover:underline">
                            {n.label}
                          </Link>
                        )}
                      </span>
                      <span className="tabular-nums">{n.degree}</span>
                    </li>
                    );
                  })}
                </ul>
              ) : (
                <p className="text-xs text-zinc-500">no connections yet</p>
              )}
            </Panel>

            <Panel
              title="Outreach funnel"
              tone="emerald"
              right={
                summary ? (
                  <span>
                    {summary.send_enabled ? "sending on" : "drafts only"}
                    {summary.paused ? " · PAUSED" : ""}
                  </span>
                ) : (
                  <span>from outcomes.json</span>
                )
              }
            >
              <div className="space-y-1">
                {funnel.steps.map((s) => (
                  <AsciiBar
                    key={s.stage}
                    label={s.stage}
                    value={s.count}
                    max={Math.max(1, ...funnel.steps.map((x) => x.count))}
                    width={16}
                    display={`${s.count}${s.conversion === null ? "" : ` · ${s.conversion}%`}`}
                    className="text-emerald-700 dark:text-emerald-300"
                  />
                ))}
              </div>
              <p className="mt-2 text-xs text-zinc-600 dark:text-zinc-400">
                {funnel.passed} passed ·{" "}
                {summary
                  ? `${Math.round(summary.reply_rate * 100)}% reply rate · ${Math.round(summary.bounce_rate * 100)}% bounced${
                      Object.keys(summary.reply_intents).length
                        ? ` · ${Object.entries(summary.reply_intents)
                            .map(([k, v]) => `${k.replaceAll("_", " ")} ${v}`)
                            .join(", ")}`
                        : ""
                    }`
                  : "run outreach.py summary on the sending machine for reply and bounce rates"}
              </p>
            </Panel>
            <Panel
              title="Watchlist"
              tone="violet"
              right={<span>data/watchlist.json</span>}
            >
              {watched.length ? (
                <ul className="space-y-1">
                  {watched.slice(0, 6).map((p) => (
                    <li key={p.slug} className="flex justify-between gap-3">
                      <Link href={`/startups/${p.slug}`} className="truncate underline underline-offset-2 hover:no-underline">
                        {p.company_name}
                      </Link>
                      <span className="shrink-0 text-xs text-zinc-600 dark:text-zinc-400">
                        {p.watch?.join(", ")}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-zinc-500">
                  nothing matches yet: add companies or keywords to backend/data/watchlist.json
                </p>
              )}
            </Panel>
            <Panel
              title="Enrichment backlog"
              tone="amber"
              right={<span>{enrich ? fmtDateTime(enrich.started_at) : "not run yet"}</span>}
            >
              {enrich ? (
                <>
                  <p className="text-xs">
                    {enrich.startups.length} startup{enrich.startups.length === 1 ? "" : "s"} retried ·{" "}
                    {enrich.startups.filter((s) => s.status === "ok").length} reached ·{" "}
                    {enrich.startups.reduce((t, s) => t + (s.emails ?? 0), 0)} emails ·{" "}
                    {fmtTokens(enrich.tokens ?? 0)} tokens
                    {enrich.quota_exhausted ? " · stopped at the quota" : ""}
                  </p>
                  <ul className="mt-2 space-y-0.5 text-xs">
                    {enrich.startups.slice(0, 5).map((s) => (
                      <li key={s.company} className="flex justify-between gap-3">
                        <span className="truncate">
                          {slugByName.get(s.company.trim().toLowerCase()) ? (
                            <Link href={`/startups/${slugByName.get(s.company.trim().toLowerCase())}`} className="underline underline-offset-2">
                              {s.company}
                            </Link>
                          ) : (
                            s.company
                          )}
                        </span>
                        <span className="text-zinc-600 dark:text-zinc-400">
                          {s.status.replaceAll("_", " ")} · {s.score}
                        </span>
                      </li>
                    ))}
                  </ul>
                </>
              ) : (
                <p className="text-xs text-zinc-500">
                  the daily enrich job writes enrich_last_run.json after its first run
                </p>
              )}
            </Panel>
          </div>

          <section aria-label="Latest findings" className="space-y-3">
            <div className="flex items-end justify-between">
              <h2 className="font-display text-3xl">
                Latest findings
              </h2>
              <RetroLink href="/startups" tone="emerald">
                All startups →
              </RetroLink>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              {latestFindings(profiles, 4).map((p) => (
                <StartupCard key={p.slug} p={p} />
              ))}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
