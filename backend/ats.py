"""Open roles from a company's own public job board. Zero tokens: documented public JSON endpoints, no login.

Greenhouse, Lever and Ashby expose each company's published postings as JSON; schema.org JobPosting markup on the
company's own pages is read too. Only titles, posting URLs and dates are kept.
"""

import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

BOARD_HOSTS = {
    "boards.greenhouse.io": "greenhouse", "job-boards.greenhouse.io": "greenhouse",
    "jobs.lever.co": "lever", "jobs.ashbyhq.com": "ashby",
}
_SLUG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{1,60}$")


def detect_board(urls: list[str]) -> tuple[str, str] | None:
    """(provider, board token) from any link that points at a known job board."""
    for u in urls:
        p = urlparse(u)
        provider = BOARD_HOSTS.get(p.netloc.lower())
        parts = [x for x in p.path.split("/") if x]
        if provider and parts and _SLUG.match(parts[0]) and parts[0] not in ("embed", "jobs"):
            return provider, parts[0]
    return None


def parse_jobs(provider: str, data) -> list[dict]:
    """-> [{title, url, posted_at}] from a board's JSON payload."""
    out = []
    if provider == "greenhouse":
        for j in (data or {}).get("jobs", []):
            out.append({"title": j.get("title", ""), "url": j.get("absolute_url", ""), "posted_at": j.get("updated_at", "")})
    elif provider == "lever":
        for j in data if isinstance(data, list) else []:
            ts = j.get("createdAt")
            posted = datetime.fromtimestamp(ts / 1000, timezone.utc).isoformat() if isinstance(ts, (int, float)) else ""
            out.append({"title": j.get("text", ""), "url": j.get("hostedUrl", ""), "posted_at": posted})
    elif provider == "ashby":
        for j in (data or {}).get("jobs", []):
            out.append({"title": j.get("title", ""), "url": j.get("jobUrl", ""), "posted_at": j.get("publishedAt", "")})
    return [j for j in out if j["title"]]


def endpoint(provider: str, token: str) -> str:
    return {
        "greenhouse": f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs",
        "lever": f"https://api.lever.co/v0/postings/{token}?mode=json",
        "ashby": f"https://api.ashbyhq.com/posting-api/job-board/{token}",
    }[provider]


def fetch_jobs(provider: str, token: str, client: httpx.Client | None = None) -> list[dict]:
    client = client or httpx.Client(timeout=15, headers={"User-Agent": "cali-scout (public job boards)"})
    try:
        r = client.get(endpoint(provider, token))
        r.raise_for_status()
        return parse_jobs(provider, r.json())
    except (httpx.HTTPError, ValueError):
        return []


def jsonld_jobs(jsonld: list[dict], page_url: str) -> list[dict]:
    """schema.org JobPosting objects declared on the company's own pages."""
    out = []
    for o in jsonld:
        t = o.get("@type")
        if t == "JobPosting" or (isinstance(t, list) and "JobPosting" in t):
            if isinstance(o.get("title"), str):
                out.append({"title": o["title"], "url": o.get("url") or page_url, "posted_at": o.get("datePosted") or ""})
    return out
