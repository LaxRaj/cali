"""Show HN posts via the free HN Algolia API."""

import time

import httpx

from discovery import Candidate
from objective import HN_MIN_POINTS, RECENCY_DAYS

API = "https://hn.algolia.com/api/v1/search_by_date"


def parse_hits(payload: dict) -> list[Candidate]:
    out = []
    for h in payload.get("hits", []):
        url = h.get("url") or ""
        if not url.startswith("http"):
            continue  # text-only posts have no landing page to crawl
        out.append(
            Candidate(
                url=url,
                title=h.get("title") or "",
                snippet=f"{h.get('points', 0)} points on Hacker News",
                source="hn",
                published_at=h.get("created_at") or "",
            )
        )
    return out


def fetch(keywords: list[str], client: httpx.Client | None = None) -> list[Candidate]:
    """One unfiltered Show HN sweep plus one query per planner keyword."""
    client = client or httpx.Client(timeout=20)
    since = int(time.time()) - RECENCY_DAYS * 86400
    out: list[Candidate] = []
    for q in [""] + keywords:
        params = {
            "tags": "show_hn",
            "numericFilters": f"created_at_i>{since},points>={HN_MIN_POINTS}",
            "hitsPerPage": 30,
        }
        if q:
            params["query"] = q
        try:
            r = client.get(API, params=params)
            r.raise_for_status()
            out += parse_hits(r.json())
        except httpx.HTTPError:
            continue
    return out
