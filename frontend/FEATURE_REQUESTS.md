# Dashboard feature requests

Found while fixing the token and run-state logic. Ordered by priority. Each item lists the problem, a proposal, a rough effort and how to tell it is done. All stay within the zero-cost rule and static-JSON data model.

## P1

### 1. Redeploy after every scout commit
- **Problem:** the pages are built from the committed JSON. A deployed dashboard (and any local `next build`/`next start`) keeps showing the old run until someone rebuilds. This is how the "last run missing" report happened.
- **Proposal:** add a step at the end of `.github/workflows/scout.yml` that triggers the host's deploy hook (a secret URL) after "Commit results to main". For local use, `npm run verify` already warns when the checkout is behind `origin/main`.
- **Effort:** small (one workflow step, one secret).
- **Done when:** a scout run's commit is visible on the deployed dashboard within minutes, without manual action.

### 2. Per-key and per-model quota view
- **Problem:** the budget is now `200k × keys`, but the dashboard shows one number. Groq's limits are per model per account, and the 429 messages show used/limit exactly (for example "Limit 200000, Used 198484").
- **Proposal:** the backend records, per run, tokens by key and model and the last known used/limit from any 429. The overview shows one bar per key, and the quota banner says which key is spent.
- **Effort:** medium (backend telemetry plus one component).
- **Done when:** the overview shows which key is exhausted and when each resets.

## P2

### 3. Cost efficiency: tokens per valid startup
- **Problem:** tokens alone do not say whether spending is worthwhile. The 20:35 run used 45.7k for 7 valid startups; the 11:08 run used 20.8k for 2.
- **Proposal:** add "tokens per valid startup" to the by-day table and a trend line, plus a source-yield trend across days (the data is already in `feedback.source_stats`).
- **Effort:** small (derived from existing fields, via `lib/metrics.ts` with tests).
- **Done when:** the by-day table shows the ratio, and `check:data` recomputes it independently.

### 4. Run diff: what is new since the last run
- **Problem:** there is no way to see which startups a run added or whose score changed.
- **Proposal:** a "since previous run" panel and a diff section on `/runs/[id]` using each run's `accepted` list and the profiles' `discovered_at`.
- **Effort:** medium.
- **Done when:** a run page lists added/removed/rescored companies.

### 5. Alerts for stale data or repeated quota stops
- **Problem:** nobody is told when the scout stops producing data, or when two days in a row end on the quota.
- **Proposal:** a workflow step that opens (or comments on) a GitHub issue when the newest run is older than 26 h or when two consecutive days have only `quota` runs. No paid services.
- **Effort:** small to medium.
- **Done when:** a simulated stale index opens an issue exactly once.

## P3

### 6. Filters, search and export on the run log
- **Problem:** the run log is an unfiltered list that will grow past the 30-run window.
- **Proposal:** filter by state (passed / failed / quota) and day, and export the action queue and run log as CSV/JSON.
- **Effort:** small to medium (client component with tests).

### 7. Outcomes funnel on the overview
- **Problem:** outcomes recorded with `backend/outcomes.py` (contacted, replied, meeting, won) only drive the action queue; their conversion is not visible.
- **Proposal:** an overview panel using `outcomes.json`: counts per stage and stage-to-stage conversion, reusing the `Funnel` component.
- **Effort:** small.

### 8. Component gallery page with fixture data
- **Problem:** states like "quota reached", "stale", "over budget" only appear when the real data happens to be in that state, so they are rarely reviewed visually.
- **Proposal:** a `/dev/components` page (excluded from production builds) that renders each component in every state from the test fixtures.
- **Effort:** small.
