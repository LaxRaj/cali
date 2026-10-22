"""Hacker News launch recency via the free Algolia API: how recently (and how loudly) did they launch?"""

from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from gtm.score import age_days, band

API = "https://hn.algolia.com/api/v1/search"
LAUNCH_TAGS = ("Show HN", "Launch HN")


def _domain(url: str) -> str:
    return urlparse(url if "//" in url else f"https://{url}").netloc.lower().removeprefix("www.")


def parse_launch(hits: list[dict], domain: str, name: str, now: datetime) -> list[dict]:
    """The company's own Show/Launch HN posts -> one `hn_launch` check for the most recent one."""
    mine = []
    for h in hits:
        title = h.get("title") or ""
        if not title.startswith(LAUNCH_TAGS):
            continue
        host = _domain(h.get("url") or "")
        by_url = bool(host) and (host == domain or host.endswith("." + domain))
        by_name = bool(name) and name.lower() in title.lower()
        if by_url or by_name:
            mine.append((h, by_url))
    if not mine:
        return []
    h, by_url = max(mine, key=lambda m: m[0].get("created_at_i", 0))
    days = age_days(h.get("created_at") or "", now)
    points, comments = h.get("points") or 0, h.get("num_comments") or 0
    when = f", {days}d ago" if days is not None else ""
    return [{
        "name": "hn_launch", "kind": "hn", "age_days": days, "band": band(days),
        "value": f"{h['title'][:80]} ({points} pts, {comments} comments{when})",
        "evidence_url": f"https://news.ycombinator.com/item?id={h.get('objectID', '')}",
        "observed_at": h.get("created_at") or "",
        "strength": 1.0 if by_url else 0.6,  # a name-only title match is lower confidence
        "points": points, "comments": comments,
    }]


def hn_check(website: str, name: str, now: datetime | None = None, client: httpx.Client | None = None) -> list[dict]:
    """One Algolia call; never fatal."""
    now = now or datetime.now(timezone.utc)
    domain = _domain(website)
    if not domain:
        return []
    client = client or httpx.Client(timeout=10)
    try:
        r = client.get(API, params={"query": domain, "restrictSearchableAttributes": "url", "tags": "story", "hitsPerPage": 20})
        r.raise_for_status()
        return parse_launch(r.json().get("hits", []), domain, name, now)
    except Exception:
        return []
