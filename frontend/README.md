# cali dashboard

A static Next.js (App Router) dashboard over the scout's committed JSON (`../backend/data`, or `demo-data/` with
`CALI_DEMO=1`). It has no API or database: pages are rebuilt from the files on every build.

```bash
npm ci
npm run dev        # real data (prints a warning when the checkout is behind origin/main)
npm run dev:demo   # fictional data with every panel populated
npm run verify     # next typegen, tsc, eslint, vitest, check:data, next build
```

| Route | What it shows |
|---|---|
| `/` | Health header. Stats: tokens on the newest run's UTC day, pass rate (quota runs excluded). Funnel, run calendar (quota = amber), token burn, sources, decision engine, action queue, outreach funnel, watchlist, enrichment backlog, most connected. |
| `/queue` | Every lead's next action: contact now, review, follow up, enrich, watch, skip. URL filters, intent-aware drafted email, CSV, keyboard triage (`?`). |
| `/startups` | Explorer: normalised stage chips, tech, qualified / email / connection toggles, search across every field, CSV, keyboard (`?`). |
| `/startups/[slug]` | Full card: contacts with their source pages, email draft, try-it links, site tech, signals, qualification, change timeline, similar companies, evidence trackbacks. |
| `/runs`, `/runs/[id]` | By-day tokens, including tokens per valid startup. Filterable run log with CSV/JSON export. Per-run diff, quality, tokens per key and model, quota hits, stages, rejections. |
| `/network` | Find or focus on a node (1–2 hops), filter by node and link type, "N of M shown", investors that back several startups. |

Every number comes from a pure function in `lib/metrics.ts`. `npm run check:data` recomputes the same numbers from
the raw files independently. See `.claude/skills/dashboard-logic-check` for the definitions these tests encode.
