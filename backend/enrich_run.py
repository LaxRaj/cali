"""Standalone enrichment stage: drains the backlog of startups the scout could not enrich (runs after the scout).

    uv run python enrich_run.py [--data-dir DIR] [--limit 10]

Same first-party policy as enrich.py; retries are bounded by backfill.MAX_ATTEMPTS. Disable with CALI_ENRICH=0.
Writes data/enrich_last_run.json (not runs_index.json: the dashboard treats those as scout runs).
"""

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import llm
from backfill import backfill
from enrich_github import enrich_people_github
from memory import DB_DIR
from scraper import search_results

DEFAULT_LIMIT = 10  # each startup may cost one team-page LLM call (~1.5k Groq tokens)
MAX_GITHUB_LOOKUPS = 30
LAST_RUN = "enrich_last_run.json"


def search_fn(query: str) -> list[dict]:
    time.sleep(1)  # be gentle with the search engines
    return search_results(query, 5, attempts=1)


async def run(data_dir: Path, limit: int = DEFAULT_LIMIT, *, backfill_fn=backfill) -> dict:
    out = {"started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "skipped": "", "startups": []}
    if os.environ.get("CALI_ENRICH", "1") == "0":
        out["skipped"] = "CALI_ENRICH=0"
    elif llm.quota_blocked(data_dir):
        out["skipped"] = "groq quota exhausted"
    if out["skipped"]:
        print(f"enrich skipped: {out['skipped']}")
        return out
    gh_budget = [MAX_GITHUB_LOOKUPS]
    llm.reset_usage()
    out["startups"] = await backfill_fn(
        data_dir, limit=limit, search_fn=search_fn,
        github_fn=lambda people: enrich_people_github(people, budget=gh_budget),
    )
    out["tokens"] = llm.USAGE["total_tokens"]
    (data_dir / LAST_RUN).write_text(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=DB_DIR)
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    args = ap.parse_args()
    args.data_dir.mkdir(parents=True, exist_ok=True)
    res = asyncio.run(run(args.data_dir, args.limit))
    print(json.dumps({k: v for k, v in res.items() if k != "startups"} | {"enriched": len(res["startups"])}, indent=2))
    print(f"tokens used: {res.get('tokens', 0)}", file=sys.stderr)
