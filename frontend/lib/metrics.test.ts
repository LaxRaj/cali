import { describe, expect, it } from "vitest";
import type { Profile, RunSummary } from "./data";
import {
  dailyBudget,
  dailyTokens,
  dailyTotals,
  dataFreshness,
  dayKey,
  historyStartsAtRecordCutoff,
  latestFindings,
  latestRun,
  passRate,
  runState,
  runsOnDay,
  topFindings,
} from "./metrics";

const funnel = {
  candidates: 300,
  selected: 12,
  crawled: 12,
  extracted: 12,
  relevant: 8,
  valid: 7,
};

function run(
  id: string,
  tokens: number,
  over: Partial<RunSummary> = {},
): RunSummary {
  const date = `${id.slice(0, 4)}-${id.slice(4, 6)}-${id.slice(6, 8)}`;
  const time = `${id.slice(9, 11)}:${id.slice(11, 13)}:${id.slice(13, 15)}`;
  return {
    run_id: id,
    started_at: `${date}T${time}+00:00`,
    duration_s: 100,
    passed: true,
    funnel,
    tokens,
    sources: {},
    failures: [],
    ...over,
  };
}

const QUOTA_FAILURES = [
  "only 0 valid startups (< 3)",
  "validity rate 0% (< 50%)",
  "only 0 discovery sources produced valid startups (< 2)",
];

/** The nine runs recorded on 2026-10-20 (real token counts). Statuses as backfilled. */
const TODAY: RunSummary[] = [
  run("20261020T080338Z", 34956, { status: "passed" }),
  run("20261020T110815Z", 20779, {
    passed: false,
    status: "failed",
    failures: ["only 2 valid startups (< 3)"],
  }),
  run("20261020T172115Z", 47707, { status: "passed" }),
  run("20261020T181651Z", 857, {
    passed: false,
    status: "quota",
    failures: QUOTA_FAILURES,
  }),
  run("20261020T184141Z", 0, {
    passed: false,
    status: "quota",
    failures: QUOTA_FAILURES,
  }),
  run("20261020T193545Z", 2862, {
    passed: false,
    status: "quota",
    failures: QUOTA_FAILURES,
  }),
  run("20261020T194209Z", 75557, { status: "passed" }),
  run("20261020T203526Z", 45684, { status: "passed" }),
  run("20261020T212403Z", 47012, { status: "passed" }),
];

describe("dayKey", () => {
  it("uses the UTC date, not the local one", () => {
    expect(dayKey("2026-10-20T23:59:59+00:00")).toBe("2026-10-20");
    expect(dayKey("2026-10-21T00:00:01+00:00")).toBe("2026-10-21");
    // 23:30 at UTC-5 is 04:30 UTC the next day
    expect(dayKey("2026-10-20T23:30:00-05:00")).toBe("2026-10-21");
  });
});

describe("dailyTokens", () => {
  it("adds up every run of the day, not just the latest (the reported bug)", () => {
    expect(dailyTokens(TODAY, "2026-10-20")).toBe(275414);
    expect(dailyTokens(TODAY, "2026-10-20")).not.toBe(TODAY.at(-1)!.tokens);
  });

  it("only counts runs on that UTC day", () => {
    const runs = [
      run("20261019T235959Z", 100),
      run("20261020T000001Z", 7),
      run("20261020T120000Z", 3),
    ];
    expect(dailyTokens(runs, "2026-10-20")).toBe(10);
    expect(dailyTokens(runs, "2026-10-19")).toBe(100);
    expect(runsOnDay(runs, "2026-10-20")).toHaveLength(2);
  });

  it("is 0 for no runs or an unknown day", () => {
    expect(dailyTokens([], "2026-10-20")).toBe(0);
    expect(dailyTokens(TODAY, "2026-01-01")).toBe(0);
  });
});

describe("dailyBudget", () => {
  it("falls back to the single-key free tier when runs don't carry a budget", () => {
    expect(dailyBudget(TODAY, "2026-10-20")).toBe(200_000);
  });

  it("uses the largest recorded budget of the day (two keys = 400k)", () => {
    const runs = [
      run("20261020T080000Z", 1, { token_budget: 200_000 }),
      run("20261020T090000Z", 1, { token_budget: 400_000 }),
    ];
    expect(dailyBudget(runs, "2026-10-20")).toBe(400_000);
  });

  it("ignores a zero/unknown budget", () => {
    expect(
      dailyBudget([run("20261020T080000Z", 1, { token_budget: 0 })], "2026-10-20"),
    ).toBe(200_000);
  });
});

describe("runState", () => {
  it("trusts the recorded status", () => {
    expect(runState(run("20261020T080000Z", 1, { status: "quota", passed: false }))).toBe("quota");
    expect(runState(run("20261020T080000Z", 1, { status: "failed", passed: false }))).toBe("failed");
  });

  it("derives it for older runs: passed -> passed", () => {
    expect(runState(run("20261020T080000Z", 1))).toBe("passed");
  });

  it("derives quota for older runs that did no work because the quota was spent", () => {
    expect(
      runState(run("20261020T080000Z", 857, { passed: false, failures: QUOTA_FAILURES })),
    ).toBe("quota");
  });

  it("does not mistake a real low-yield failure for quota", () => {
    expect(
      runState(
        run("20261020T080000Z", 20779, {
          passed: false,
          failures: ["only 2 valid startups (< 3)"],
        }),
      ),
    ).toBe("failed");
    // zero valid but lots of tokens spent: the pipeline really ran
    expect(
      runState(run("20261020T080000Z", 90_000, { passed: false, failures: QUOTA_FAILURES })),
    ).toBe("failed");
  });
});

describe("passRate", () => {
  it("excludes quota-skipped runs from the rate and reports them", () => {
    const r = passRate(TODAY);
    expect(r).toEqual({ pct: 83, passed: 5, failed: 1, skipped: 3 });
  });

  it("is null when nothing counts", () => {
    expect(passRate([]).pct).toBeNull();
    expect(passRate([TODAY[3]]).pct).toBeNull();
    expect(passRate([TODAY[3]]).skipped).toBe(1);
  });

  it("only looks at the last `window` runs", () => {
    const r = passRate(TODAY, 2);
    expect(r).toEqual({ pct: 100, passed: 2, failed: 0, skipped: 0 });
  });

  it("windows by run id even when the index is out of order", () => {
    const shuffled = [...TODAY].reverse();
    expect(passRate(shuffled, 2)).toEqual(passRate(TODAY, 2));
  });
});

describe("latestRun", () => {
  it("picks the greatest run id regardless of position", () => {
    expect(latestRun([...TODAY].reverse())?.run_id).toBe("20261020T212403Z");
  });
  it("is undefined for an empty index", () => {
    expect(latestRun([])).toBeUndefined();
  });
});

describe("dailyTotals", () => {
  const runs = [
    ...TODAY,
    run("20261019T060000Z", 90_000, { status: "passed", token_budget: 400_000 }),
  ];

  it("groups by UTC day, oldest first", () => {
    const t = dailyTotals(runs);
    expect(t.map((d) => d.day)).toEqual(["2026-10-19", "2026-10-20"]);
  });

  it("totals tokens, budget and run states per day", () => {
    const [, today] = dailyTotals(runs);
    expect(today).toMatchObject({
      tokens: 275414,
      budget: 200_000,
      runs: 9,
      passed: 5,
      failed: 1,
      quota: 3,
    });
  });

  it("each day's total equals dailyTokens", () => {
    for (const d of dailyTotals(runs)) {
      expect(d.tokens).toBe(dailyTokens(runs, d.day));
    }
  });

  it("is empty for no runs", () => {
    expect(dailyTotals([])).toEqual([]);
  });
});

function profile(slug: string, score: number, discovered: string): Profile {
  return {
    slug,
    company_name: slug,
    score,
    discovered_at: discovered,
  } as Profile;
}

describe("findings", () => {
  const ps = [
    profile("a", 90, "2026-10-20T20:36:00+00:00"),
    profile("b", 70, "2026-10-20T21:24:00+00:00"),
    profile("c", 95, "2026-10-20T08:04:00+00:00"),
  ];
  it("latestFindings sorts by discovery time, newest first", () => {
    expect(latestFindings(ps, 2).map((p) => p.slug)).toEqual(["b", "a"]);
  });
  it("topFindings sorts by score", () => {
    expect(topFindings(ps, 2).map((p) => p.slug)).toEqual(["c", "a"]);
  });
  it("does not mutate its input", () => {
    const copy = [...ps];
    latestFindings(ps, 3);
    topFindings(ps, 3);
    expect(ps).toEqual(copy);
  });
});

describe("dataFreshness", () => {
  const latest = run("20261020T212403Z", 1);
  it("reports age in hours", () => {
    const f = dataFreshness(latest, new Date("2026-10-21T00:24:03Z"));
    expect(f.ageHours).toBeCloseTo(3, 5);
    expect(f.stale).toBe(false);
  });
  it("is stale after 26h (daily cron plus slack)", () => {
    expect(dataFreshness(latest, new Date("2026-10-21T23:24:03Z")).stale).toBe(false);
    expect(dataFreshness(latest, new Date("2026-10-22T00:00:00Z")).stale).toBe(true);
  });
  it("is stale when there is no run at all", () => {
    expect(dataFreshness(undefined, new Date()).stale).toBe(true);
  });
});

describe("historyStartsAtRecordCutoff", () => {
  it("is true when the oldest indexed run is the first one ever recorded", () => {
    expect(historyStartsAtRecordCutoff(TODAY)).toBe(true);
  });
  it("is false when the index reaches back before run records existed (demo data)", () => {
    const older = run("20260921T060000Z", 1);
    expect(historyStartsAtRecordCutoff([older, ...TODAY])).toBe(false);
  });
  it("is false for an empty index", () => {
    expect(historyStartsAtRecordCutoff([])).toBe(false);
  });
  it("does not depend on array order", () => {
    expect(historyStartsAtRecordCutoff([...TODAY].reverse())).toBe(true);
  });
});
