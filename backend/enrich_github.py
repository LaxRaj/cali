"""Public GitHub profile fields people published about themselves: blog/website, X handle, location.

Only for people whose GitHub profile we already found on the company's own pages (see enrich.py). We deliberately
do NOT collect the profile's e-mail address. Uses GITHUB_TOKEN when present (5000 req/h in Actions) else the
unauthenticated 60 req/h. Never fatal.
"""

import os
import re
from urllib.parse import urlparse

import httpx

from models import Person

API = "https://api.github.com/users/"


def login_of(url: str) -> str:
    segs = [s for s in urlparse(url).path.split("/") if s]
    return segs[0] if len(segs) == 1 else ""


def _site(value: str) -> str:
    v = (value or "").strip()
    if not v:
        return ""
    v = v if re.match(r"https?://", v, re.I) else f"https://{v}"
    return v if "." in urlparse(v).netloc else ""


def enrich_people_github(people: list[Person], client: httpx.Client | None = None, budget: list[int] | None = None) -> list[Person]:
    """Fill missing homepage / twitter from each person's public GitHub profile (budgeted, failure-tolerant)."""
    token = os.environ.get("GITHUB_TOKEN", "")
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "cali-scout"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    client = client or httpx.Client(timeout=10, headers=headers)
    out = []
    for p in people:
        login = login_of(p.github) if p.github else ""
        if not login or (p.homepage and p.twitter) or (budget is not None and budget[0] <= 0):
            out.append(p)
            continue
        if budget is not None:
            budget[0] -= 1
        try:
            r = client.get(API + login)
            r.raise_for_status()
            data = r.json()
        except (httpx.HTTPError, ValueError):
            out.append(p)
            continue
        upd = {}
        if not p.homepage and _site(data.get("blog", "")):
            upd["homepage"] = _site(data["blog"])
        if not p.twitter and re.fullmatch(r"[A-Za-z0-9_]{1,15}", data.get("twitter_username") or ""):
            upd["twitter"] = f"https://x.com/{data['twitter_username']}"
        if upd and not p.link_source:
            upd["link_source"] = "github profile"
        out.append(p.model_copy(update=upd) if upd else p)
    return out
