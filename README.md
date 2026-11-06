# cali

A zero-cost, self-hosted startup scout. Every day it finds early-stage tech startups, works out what is hard for
their engineering team right now, finds a way to reach them that *they published themselves*, drafts a specific
email, and (only if you switch it on) sends it behind strict safeguards. A static Next.js dashboard shows all of it.

No paid APIs. Groq's free tier, local MiniLM embeddings, LanceDB on disk, GitHub Actions for the schedule.

```
 discover ─▶ triage ─▶ crawl ─▶ extract ─▶ enrich ─▶ rate ─▶ quality gates ─▶ store ─▶ export ─▶ dashboard
 HN · YC ·   local     crawl4ai  Groq       own-site  0-100   validity,        lance    profiles  Next.js
 RSS · web · decider   robots ✓  (gpt-oss)  contacts  score   sources          + ledger graph     (static)
 SEC Form D                                 + people                                   digest
 HN hiring                                                         outreach ◀── decide ◀┘ (local)
```

## Quickstart

```bash
cd backend && uv sync
echo "GROQ_API_KEY=..." > .env.local            # free key from console.groq.com
uv run --env-file .env.local python pipeline.py  # one scout run -> backend/data/
uv run pytest -q                                 # offline tests

cd ../frontend && npm ci
npm run dev                                      # http://localhost:3000 (real data)
npm run dev:demo                                 # fictional demo data, every panel populated
npm run verify                                   # typegen, tsc, eslint, vitest, check:data, build
```

In CI the scout runs daily at 06:00 UTC (`.github/workflows/scout.yml`) and the enrichment backlog at 08:00 UTC
(`enrich.yml`). Both commit `backend/data`. Optional secrets and variables:

| name | what it does |
|---|---|
| `GROQ_API_KEY`, `GROQ_API_KEY_2` | free Groq keys; the second is used when the first hits its daily limit |
| `CALI_CONTACT_EMAIL` | turns on SEC Form D discovery (the SEC requires a contact in the User-Agent) |
| `DEPLOY_HOOK_URL` | POSTed after each data commit so the hosted dashboard rebuilds |
| `vars.CALI_DASHBOARD_URL` | used for links in the Monday digest issue |

Health alerts (no run in 26 h, or two days ending on the Groq quota) open one `cali-alert` issue, which is closed
again when the scout is healthy. Every Monday a `cali-digest` issue lists new strong leads, who to contact next,
watchlist hits, replies and scout health.

## Outreach (local only, opt-in)

```bash
cd backend
uv sync --extra gmail
uv run python outreach.py init        # who signs the emails (data/me.json, gitignored)
uv run python outreach.py doctor      # sender, Gmail token, SPF/DMARC, switches, send window, ramp
uv run python outreach.py queue       # draft emails for contact_now leads
uv run python outreach.py run --dry-run
CALI_OUTREACH_SEND=1 uv run python outreach.py run   # one vetted send per tick, from cron every ~20 min
uv run python outreach.py summary     # address-free numbers for the dashboard's outreach funnel
```

Safeguards, all enforced in code (see `CLAUDE.md`):
- **Who and what:** only company-published, sourced addresses on the company's own domain; a quality gate (score 70+,
  something specific to say, never a "needs a human" draft); plain-text lint; an opt-out line and List-Unsubscribe.
- **Pace:** a warm-up ramp; a Tue–Thu 09:00–16:00 window; random 4–15 minute gaps; one follow-up, then stop.
- **Stopping:** a suppression list and per-domain cooldown; a circuit breaker on bounces, complaints or unknown send
  results that holds until `outreach.py resume` (unresolved sends need `outreach.py resolve` first); `CALI_OUTREACH=0`
  turns everything off.

Replies are read back and sorted deterministically: interested, not now, referral, question, unsubscribe or
complaint. Out-of-office auto-replies don't count as replies. Results land in `outcomes.json`, which trains the
local decider's "lead" head.

## How it compares

| | cali | Clay / Apollo | Harmonic / Specter | Instantly / Smartlead |
|---|---|---|---|---|
| Cost | $0 | $149–$800+/mo | enterprise | $37–$400+/mo |
| Finds startups before the big databases (SEC Form D, HN hiring, launches) | ✓ | partly | ✓ | — |
| Says *what is hard for them* (engineering bottleneck, from their own pages) | ✓ | — | — | — |
| Contact data | only what the company published, with the source page | bought databases, guessed or "verified" emails | bought data | bring your own |
| Compliance in code (no guessing, no LinkedIn scraping, suppression, opt-out) | ✓ | your job | n/a | partly |
| Lookalikes, change timeline, watchlist, weekly digest | ✓ (local embeddings + evidence ledger) | ✓ | ✓ | — |
| Reply sorting and outreach funnel | ✓ (deterministic, local) | ✓ | — | ✓ (LLM) |
| Learns from *your* results | ✓ (decider trained on your outcomes) | generic scoring | generic scoring | — |
| Data stays on your machine / repo | ✓ | — | — | — |

Not possible within the zero-cost rules: bought contact databases, LinkedIn job-change signals, headcount and
traffic trends, shared warm-up networks.

## Layout

- `backend/`: Python pipeline.
  - `pipeline.py`, `enrich*.py`, `backfill.py`: discovery, enrichment and the backlog.
  - `decide/`: local decider and lead policy.
  - `outreach.py`, `gmail_sync.py`: sending and reading replies back.
  - `insights.py`: lookalikes, timeline, watchlist.
  - `techstack.py`, `digest.py`, `repair.py`.
- `frontend/`: Next.js App Router dashboard. It reads `backend/data/*.json` at build time.
- `CLAUDE.md`: the rules every change must follow.
