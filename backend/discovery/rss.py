"""Funding / launch news from startup-media RSS feeds."""

import re

import feedparser

from discovery import Candidate

FEEDS = [
    "https://techcrunch.com/category/startups/feed/",
    "https://techcrunch.com/category/venture/feed/",
    "https://news.crunchbase.com/sections/venture/feed/",
    "https://www.finsmes.com/feed",  # small-round announcements: named founders and investors
    "https://www.eu-startups.com/feed/",
    "https://tech.eu/feed",
    "https://techfundingnews.com/feed/",
    "https://www.sifted.eu/feed",
    "https://www.betakit.com/feed/",
]
FUNDING = re.compile(
    r"\b(raises?|raised|seed|pre-seed|series a|funding|backed|launche?s?|debuts?|emerges?|stealth)\b", re.I
)


# Not early-stage startup news: unicorns, mega-rounds, market roundups.
NOISE = re.compile(
    r"unicorn|\$\s?\d+(\.\d+)?\s?(b|bn|billion)\b|\bIPO\b|\bQ[1-4]\b|funding (report|trends|roundup|jumps|drops|falls)|"
    r"startup funding (jumps|drops|falls|rises)|weekly|week in|market (report|size)",
    re.I,
)


def parse_feed(parsed, keywords: list[str] | None = None) -> list[Candidate]:
    out = []
    for e in parsed.entries:
        text = f"{e.get('title', '')} {e.get('summary', '')}"
        if not FUNDING.search(text) or NOISE.search(e.get("title", "")):
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
