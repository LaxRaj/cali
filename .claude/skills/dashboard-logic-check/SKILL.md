---
name: dashboard-logic-check
description: Verify that the Next.js dashboard's numbers and logic are correct before showing them to the user. Use whenever you change anything under frontend/ (app, components, lib), change the run/profile JSON the backend writes, add or edit a dashboard metric, or are about to report dashboard numbers (tokens, pass rate, run counts, findings).
---

# Dashboard logic check

The dashboard reads committed JSON (`backend/data/`, or `frontend/demo-data/` with `CALI_DEMO=1`). It has shown wrong numbers before (for example, "Tokens today" was only the latest run's tokens, not the day's total). Do not show the user the dashboard, or numbers from it, until these steps pass.

## 1. Run the gate

```bash
cd frontend && npm run verify
```

This runs, in order: `next typegen`, `tsc --noEmit`, `eslint`, `vitest run`, `npm run check:data`, `next build`. Fix the code when something fails. Never edit a test, or loosen a check, to make it pass; a test encodes a definition (below), so if the definition itself is wrong, say so and ask.

`npm run check:data` alone is the quick data-only check (a second). It recomputes the headline numbers from the raw `runs/<id>.json` files without using `lib/metrics.ts`, then compares them with what the dashboard logic returns. A mismatch means one of the two is wrong.

## 2. Confirm the headline numbers by hand once

Run the independent check below on the raw data (not through the frontend code) and compare with the `Headline:` line from `check:data` and with the page:

```bash
python3 -c "
import json,collections
r=json.load(open('backend/data/runs_index.json'))['runs']
d=collections.defaultdict(int)
for x in r: d[x['started_at'][:10]]+=x['tokens']
print(dict(d))"
```

If a number on the page differs from the raw one, report the difference to the user instead of showing the page.

## 3. When you add or change a metric

1. Put the logic in `frontend/lib/metrics.ts` as a pure function (no I/O, no clock; pass `now` in). Pages and components only call it.
2. Write the test first in `lib/metrics.test.ts`, using the real shape of the data (several runs on one day, runs with a missing `status`, a day boundary).
3. If the metric is shown on the overview page, add or extend a case in `app/page.test.tsx` that asserts the rendered text.
4. If the metric can be derived from the raw files, add an independent recomputation to `scripts/check-dashboard.ts`.
5. Components get a colocated `*.test.tsx`: empty input, zero values (falsy but real), values above the max, and no `NaN` in the output.

## Definitions (the tests encode these)

- A **day** is a UTC calendar day. The Groq quota resets at 00:00 UTC.
- **Tokens today** is the sum of `tokens` over every run that started on the UTC day of the newest run. It is never the latest run alone. **Budget** is the largest `token_budget` recorded that day (200k per Groq key), falling back to 200k.
- A run is **passed**, **failed** (quality gates) or **quota** (stopped by the Groq daily limit). Quota runs are not failures: they are left out of the pass rate and shown amber, and never turn the header to "LAST RUN FAILED". Older runs without `status` are derived in `runState()`.
- The **latest run** is the greatest `run_id`, not the last array position.
- **Latest findings** are by `discovered_at` (newest first); "top" findings are by score.
- Data is **stale** after 26 hours (the scout runs daily). A checkout behind `origin/main` is a warning: newer runs may exist upstream, so `git pull` before judging.

## Hard rules for this repo

- Frontend reads static JSON only; no live DB, no paid APIs (see `CLAUDE.md`).
- Before saying a task is done you must have run the tests or the build; say which, and what the result was.
- Report check failures and warnings faithfully, including the ones you chose not to fix.
