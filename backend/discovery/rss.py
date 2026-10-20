"""Funding / launch news from startup-media RSS feeds."""

import re

import feedparser

from discovery import Candidate

FEEDS = [
    "https://techcrunch.com/category/startups/feed/",
    "https://news.crunchbase.com/feed/",
]
FUNDING = re.compile(
    r"\b(raises?|raised|seed|pre-seed|series a|funding|backed|launche?s?|debuts?|emerges?|stealth)\b", re.I
)


def parse_feed(parsed, keywords: list[str] | None = None) -> list[Candidate]:
    out = []
    for e in parsed.entries:
        text = f"{e.get('title', '')} {e.get('summary', '')}"
        if not FUNDING.search(text):
            continue
        out.append(
            Candidate(
                url=e.get("link", ""),
                title=e.get("title", ""),
                snippet=re.sub(r"<[^>]+>", "", e.get("summary", ""))[:300],
                source="rss",
                published_at=e.get("published", ""),
            )
        )
    return [c for c in out if c.url.startswith("http")]


def fetch() -> list[Candidate]:
    out: list[Candidate] = []
    for url in FEEDS:
        try:
            out += parse_feed(feedparser.parse(url))
        except Exception:
            continue
    return out
