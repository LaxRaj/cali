import Link from "next/link";
import { notFound } from "next/navigation";
import { AsciiBar } from "@/components/charts/ascii-bar";
import { Funnel } from "@/components/charts/funnel";
import { StageTimeline } from "@/components/charts/stage-timeline";
import { Led } from "@/components/ui/led";
import { Panel } from "@/components/ui/panel";
import { Stat } from "@/components/ui/stat";
import { readIndex, readRun } from "@/lib/data";
import { fmtDateTime, fmtDuration, fmtTokens } from "@/lib/format";
import { dailyBudget, dailyTokens, dayKey, runState } from "@/lib/metrics";

export function generateStaticParams() {
  const runs = readIndex();
  return runs.length ? runs.map((r) => ({ id: r.run_id })) : [{ id: "none" }];
}

export default async function RunPage({ params }: PageProps<"/runs/[id]">) {
  const { id } = await params;
  const run = readRun(id);
  if (!run) notFound();
  const state = runState(run);
  const index = readIndex();
  const day = dayKey(run.started_at);
  const budget = dailyBudget(index, day);
  const dayTotal = dailyTokens(index, day);
  const maxSrc = Math.max(
    ...Object.values(run.source_health).map((s) => s.candidates),
    1,
  );

  return (
    <div className="space-y-6">
      <p className="text-xs">
        <Link href="/runs" className="underline">
          ← runs
        </Link>
      </p>
      <header className="flex flex-wrap items-center gap-3">
        <Led
          state={state === "passed" ? "ok" : state === "quota" ? "warn" : "fail"}
          label={state}
        />
        <h1 className="glow font-display text-4xl uppercase tracking-wider">
          Run {run.run_id}
        </h1>
        <span className="text-xs text-zinc-600 dark:text-zinc-400">
          {fmtDateTime(run.started_at)}
        </span>
      </header>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat
          label="Result"
          value={state === "passed" ? "PASS" : state === "quota" ? "QUOTA" : "FAIL"}
          tone={state === "passed" ? "emerald" : state === "quota" ? "amber" : "rose"}
        />
        <Stat label="Duration" value={fmtDuration(run.duration_s)} tone="sky" />
        <Stat
          label="Tokens"
          value={fmtTokens(run.tokens)}
          sub={`${run.usage.calls ?? 0} LLM calls · day total ${fmtTokens(dayTotal)} (${Math.round((dayTotal / budget) * 100)}% of ${fmtTokens(budget)})`}
          tone="amber"
        />
        <Stat
          label="Valid startups"
          value={run.funnel.valid}
          sub={`${run.accepted.reduce((s, a) => s + a.people, 0)} people`}
          tone="violet"
        />
      </div>

      {run.failures.length > 0 && (
        <Panel title="Quality gates failed" tone="rose">
          <ul className="list-disc space-y-1 pl-5">
            {run.failures.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
        </Panel>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Stage timeline" tone="sky">
          <StageTimeline stages={run.stages} />
        </Panel>
        <Panel title="Funnel" tone="emerald">
          <Funnel funnel={run.funnel} />
        </Panel>
        <Panel title="Source health" tone="rose">
          <ul className="space-y-1.5">
            {Object.entries(run.source_health).map(([name, s]) => (
              <li key={name}>
                <AsciiBar
                  label={name}
                  value={s.candidates}
                  max={maxSrc}
                  width={18}
                  display={`${s.candidates} · ${s.seconds}s`}
                  className="text-rose-700 dark:text-rose-300"
                />
                {s.error && (
                  <p className="pl-[4.5rem] text-xs text-rose-700 dark:text-rose-300">
                    ⚠ {s.error}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </Panel>
        <Panel title="Planner output" tone="violet">
          <p className="mb-1 text-[11px] uppercase tracking-widest text-zinc-600 dark:text-zinc-400">
            web queries
          </p>
          <ul className="mb-3 space-y-0.5">
            {(run.plan.web_queries ?? []).map((q) => (
              <li key={q}>› {q}</li>
            ))}
          </ul>
          <p className="mb-1 text-[11px] uppercase tracking-widest text-zinc-600 dark:text-zinc-400">
            hacker news keywords
          </p>
          <p>{(run.plan.hn_keywords ?? []).join(" · ") || "—"}</p>
        </Panel>
      </div>

      {run.feedback?.source_stats &&
        Object.keys(run.feedback.source_stats).length > 0 && (
          <Panel
            title="Crawl budget feedback"
            tone="amber"
            right={<span>yield over the last runs → this run&apos;s caps</span>}
          >
            <div className="space-y-1">
              {Object.entries(run.feedback.source_stats).map(([src, st]) => (
                <AsciiBar
                  key={src}
                  label={src}
                  value={Math.round(st.yield * 100)}
                  max={100}
                  width={16}
                  display={`${st.accepted}/${st.crawled} valid · avg score ${st.avg_score} · cap ${run.feedback?.caps?.[src] ?? "-"}`}
                  className="text-amber-700 dark:text-amber-300"
                />
              ))}
            </div>
          </Panel>
        )}

      {run.decisions && (
        <Panel
          title="Decision engine"
          tone="sky"
          right={<span>{run.decisions.provider}</span>}
        >
          <p className="text-xs">
            {run.decisions.calls} decisions at {run.decisions.avg_latency_ms} ms
            each · {run.decisions.gated_pages} page
            {run.decisions.gated_pages === 1 ? "" : "s"} skipped before
            extraction (~{fmtTokens(run.decisions.tokens_saved_est)} LLM tokens
            saved)
            {run.decisions.fallbacks > 0 &&
              ` · ${run.decisions.fallbacks} fell back to the local decider`}
            {run.decisions.jev_input_tokens > 0 &&
              ` · Jev input tokens: ${run.decisions.jev_input_tokens}`}
          </p>
        </Panel>
      )}

      <Panel title={`Accepted (${run.accepted.length})`} tone="emerald">
        {run.accepted.length === 0 ? (
          <p className="text-xs text-zinc-500">
            nothing was accepted in this run
          </p>
        ) : (
          <ul className="space-y-1">
            {run.accepted.map((a) => (
              <li
                key={a.url}
                className="space-y-0.5 border-b border-zinc-900/15 pb-1 dark:border-emerald-400/15"
              >
                <div className="flex flex-wrap justify-between gap-2">
                  <span>
                    <span className="font-semibold">{a.company}</span>{" "}
                    <span className="text-zinc-500">via {a.source}</span>
                  </span>
                  <span className="text-xs text-zinc-600 dark:text-zinc-400">
                    {a.score !== undefined && (
                      <span className="font-semibold">score {a.score} · </span>
                    )}
                    {a.people} {a.people === 1 ? "person" : "people"} ·{" "}
                    {a.edges} {a.edges === 1 ? "connection" : "connections"}
                    {a.emails !== undefined &&
                      ` · ${a.emails} email · ${a.phones ?? 0} phone`}
                  </span>
                </div>
                {a.gaps && a.gaps.length > 0 && (
                  <p className="text-xs text-amber-700 dark:text-amber-300">
                    missing: {a.gaps.join(", ")}
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <Panel title={`Rejected (${run.rejections.length})`} tone="amber">
        {run.rejections.length === 0 ? (
          <p className="text-xs text-zinc-500">no rejections</p>
        ) : (
          <ul className="space-y-1 text-xs">
            {run.rejections.map((r, i) => (
              <li key={i} className="flex flex-wrap justify-between gap-2">
                <a
                  href={r.url}
                  target="_blank"
                  rel="noreferrer"
                  className="max-w-[28rem] truncate underline"
                >
                  {r.url}
                </a>
                <span>
                  [{r.source}] {r.reasons.join(", ")}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <Panel title={`Error log (${run.errors.length})`} tone="rose">
        {run.errors.length === 0 ? (
          <p className="text-xs text-zinc-500">no errors</p>
        ) : (
          <pre className="max-h-72 overflow-auto whitespace-pre-wrap bg-white/70 p-2 text-xs dark:bg-black/60">
            {run.errors.join("\n")}
          </pre>
        )}
      </Panel>
    </div>
  );
}
