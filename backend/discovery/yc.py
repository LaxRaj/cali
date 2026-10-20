"""Recent Y Combinator launch posts."""

import re

import httpx

from discovery import Candidate

LISTING = "https://www.ycombinator.com/launches"
_LINK = re.compile(r"/launches/([A-Za-z0-9]+)-([a-z0-9-]+)")


def parse_listing(html: str, limit: int = 12) -> list[Candidate]:
    seen, out = set(), []
    for m in _LINK.finditer(html):
        path = m.group(0)
        if path in seen:
            continue
        seen.add(path)
        out.append(
            Candidate(
                url=f"https://www.ycombinator.com{path}",
                title=m.group(2).replace("-", " "),
                snippet="Y Combinator launch post",
                source="yc",
            )
        )
    return out[:limit]


def fetch(client: httpx.Client | None = None) -> list[Candidate]:
    client = client or httpx.Client(timeout=20, follow_redirects=True)
    try:
        r = client.get(LISTING)
        r.raise_for_status()
        return parse_listing(r.text)
    except httpx.HTTPError:
        return []
