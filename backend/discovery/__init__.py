import re
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlparse


@dataclass
class Candidate:
    url: str
    title: str
    snippet: str
    source: str  # hn | rss | yc | web
    published_at: str = ""
    content: str = ""  # page text already in hand (e.g. Launch HN posts); skips the crawl


_TRACKING = {"fbclid", "gclid", "ref", "source"}


def normalize_url(url: str) -> str:
    """Canonical form used for dedupe and the seen-URL table."""
    p = urlparse(url.strip())
    host = re.sub(r"^www\.", "", p.netloc.lower())
    query = urlencode(
        [(k, v) for k, v in parse_qsl(p.query) if not k.startswith("utm_") and k not in _TRACKING]
    )
    path = p.path.rstrip("/")
    return f"{host}{path}" + (f"?{query}" if query else "")
