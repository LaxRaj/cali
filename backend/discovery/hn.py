"""Show HN posts via the free HN Algolia API."""

import re
import time

import httpx
from bs4 import BeautifulSoup

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


def html_to_markdown(html: str) -> str:
    """HN post HTML -> plain text, keeping links as [text](url) so the extractor can see the company site."""
    soup = BeautifulSoup(html or "", "html.parser")
    for a in soup.find_all("a", href=True):
        a.replace_with(f"[{a.get_text(strip=True) or a['href']}]({a['href']})")
    for br in soup.find_all(["p", "br", "li"]):
        br.insert_before("\n")
    return re.sub(r"\n{3,}", "\n\n", soup.get_text()).strip()


def parse_launch(payload: dict) -> list[Candidate]:
    """Launch HN posts are YC startups announcing themselves. The post text is the content (no HN crawl:
    news.ycombinator.com rate-limits crawlers)."""
    out = []
    for h in payload.get("hits", []):
        title = h.get("title") or ""
        text = html_to_markdown(h.get("story_text") or "")
        if not title.startswith("Launch HN") or not text:
            continue
        out.append(
            Candidate(
                url=f"https://news.ycombinator.com/item?id={h['objectID']}",
                title=title,
                snippet=f"{h.get('points', 0)} points · Launch HN",
                source="launch_hn",
                published_at=h.get("created_at") or "",
                content=f"# {title}\n\n{text}",
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
    try:
        r = client.get(
            API,
            params={"query": "Launch HN", "tags": "story", "numericFilters": f"created_at_i>{since}", "hitsPerPage": 30},
        )
        r.raise_for_status()
        out += parse_launch(r.json())
    except httpx.HTTPError:
        pass
    return out
