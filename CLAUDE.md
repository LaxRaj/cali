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
