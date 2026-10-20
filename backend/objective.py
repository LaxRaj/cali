import os

"""The scout's goal. Everything downstream (planner, triage, extractor) reads this."""

OBJECTIVE = """Find early-stage tech startups (pre-seed to Series A, recently launched or funded),
the people behind them (founders, key engineers, investors, advisors) and the connections
between them (who founded / works at / invested in / advises what). Prioritise startups whose
product depends on search, retrieval, RAG, data-heavy web apps or developer tooling, where a
freelance engineer using Next.js and vector semantic search could remove a bottleneck.
Ignore generic how-to articles, listicles, big-tech news and market reports."""

RECENCY_DAYS = 14
HN_MIN_POINTS = 5
N_WEB_QUERIES = 5
MAX_CRAWLS = 12  # per run; ~4k Groq tokens each keeps us inside the 200k tokens/day free tier
PER_SOURCE_CAP = 5  # keep one source from crowding out the others

# Quality gates evaluated before anything is written (see quality.evaluate_run)
MIN_VALID_STARTUPS = 3
MIN_VALIDITY_RATE = 0.5  # of pages the LLM called relevant, share passing validation
MIN_SOURCES = 2  # distinct discovery sources among valid startups

# Triage floor (0-10, local decider). In our logs every valid startup scored >= 7.7 while 4 of 10 rejected pages
# scored 5.6-6.9, so crawling + extracting anything below ~6.5 mostly buys rejections. CALI_MIN_TRIAGE overrides.
MIN_TRIAGE = float(os.environ.get("CALI_MIN_TRIAGE", "6.5"))
