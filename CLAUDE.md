# Superagent Architecture Constraints

## WHAT
We are building a headless startup scouting pipeline and a Next.js triage dashboard. 
The backend is 100% Python. The frontend is Next.js (App Router). 

## WHY
To identify high-signal tech startups and their engineering bottlenecks at zero cost, bypassing paid APIs.

## HOW (Strict Technical Rules)
- **Zero Cost Rule:** NEVER use paid APIs (No OpenAI, No Proxycurl, No Apify). 
- **Python Backend:** Use `uv` for dependency management. Use `crawl4ai` for scraping, `duckduckgo-search` for search, `SentenceTransformers` (`all-MiniLM-L6-v2`) for local embeddings, and `lancedb` for embedded vector storage.
- **LLM Engine:** Use `groq` (Llama 3.1 70B) for inference.
- **Next.js Frontend:** App Router, Tailwind CSS, shadcn/ui. Read data strictly from static JSON or local `.lance` files (no live database queries).
- **Verification:** Before claiming a task is done, you MUST run tests or the build command. If tests fail, fix the underlying code, do not modify the tests to pass.
- **Enrichment policy (contacts & profiles):** Enrich only with what a company or person has *published themselves* on pages we may crawl (respect robots.txt), or a public profile URL whose handle matches the person's name. NEVER guess/permute or "verify" email addresses, never collect personal phone numbers from third parties, never scrape LinkedIn or anything behind a login, never use paid enrichment APIs/connectors. Store the source URL with every contact/profile value. Enrichment code is deterministic (see `backend/enrich.py`); disable with `CALI_ENRICH=0`.
- **Outreach policy (`backend/outreach.py`, `backend/gmail_sync.py`):** Email only (never LinkedIn or any login-gated site). The owner approved **autonomous sending on 2026-10-20**, but only behind these safeguards, all enforced in `outreach.py` and never to be weakened without the owner's say-so: sending needs `CALI_OUTREACH_SEND=1` (otherwise drafts only); recipient must be a company-published, sourced address (see enrichment policy); warm-up ramp (3/day, +2/day, capped), Tue-Thu 09:00-16:00 local window, random 4-15 min gaps, one send per tick; plain-text lint and a quality gate (score >= 70, something specific to say) before every send; opt-out line and List-Unsubscribe; one follow-up (same thread) then stop; suppression list and per-domain cooldown; circuit breaker that pauses on bounces/complaints/send errors until `outreach.py resume`; `CALI_OUTREACH=0` kill switch. Gmail access is local-only (token in `~/.config/cali`, optional `gmail` extra); never run it in CI. No paid outreach tools (Apollo, Clay, HeyReach, GetLeads, ...).
- **Decision layer (`backend/decide/`):** Judgements (triage, page gating, lead action) go through a System One-shaped provider (choice / score / yes-no, like TypeSafe's Jev). The default provider is **local and free** (MiniLM embeddings + a head learned from our own outcomes). **Jev is a paid, opt-in backend**: it is used only if `CALI_DECIDER` is `jev`/`auto` AND `TYPESAFE_API_KEY` is set, and it always falls back to local. Never enable it by default or in CI without the owner's explicit approval. Record real outcomes with `backend/outcomes.py`; they train the decider and drive the action queue.
- **Public-data sources:** SEC Form D (`CALI_CONTACT_EMAIL` required for the SEC User-Agent), HN "Who is hiring", and GitHub public profile fields (homepage/X only, never emails).

