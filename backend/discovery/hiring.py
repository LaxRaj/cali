"""HN 'Who is hiring?' posts: companies actively hiring engineers, often with a published jobs/contact address.

The monthly thread is created by the `whoishiring` account. Each top-level comment is one company's post whose
first line is usually `Company | Role | Location | ... | url`. The post text is the content (no crawl); any email
in it is one the company itself published.
"""

import re
import time

import httpx
from bs4 import BeautifulSoup

from discovery import Candidate
from discovery.hn import html_to_markdown

API = "https://hn.algolia.com/api/v1"
MAX_POSTS = 120
ENGINEERING = re.compile(r"engineer|developer|backend|full.?stack|frontend|machine learning|\bml\b|\bai\b|data|search|infra|cto|founding", re.I)


# Big, established employers are not early-stage leads: corporate career sites and enterprise boilerplate.
BIG_COMPANY = re.compile(
    r"fortune 500|publicly traded|\bnasdaq\b|\bnyse\b|\b\d{1,3},\d{3}\+?\s+employees|global leader|"
    r"equal opportunity employer|\bover \d{2,3} years\b",
    re.I,
)
CORPORATE_HOST = re.compile(r"^(careers|jobs|talent)\.[a-z0-9-]+\.(com|org|net)$", re.I)


def parse_post(comment_html: str) -> dict | None:
    """-> {company, roles, header, url, text} for a structured post, else None."""
    text = html_to_markdown(comment_html)
    first = text.split("\n", 1)[0].strip()
    parts = [p.strip() for p in first.split("|")]
    if len(parts) < 3:
        return None  # replies and free-form comments
    company = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", parts[0]).strip(" *_")
    company = re.sub(r"\s*\(.*?\)\s*", " ", company).strip()
    if not company or len(company) > 60:
        return None
    soup = BeautifulSoup(comment_html, "html.parser")
    links = [a["href"] for a in soup.find_all("a", href=True) if a["href"].startswith("http") and "ycombinator.com" not in a["href"]]
    return {"company": company, "roles": parts[1], "header": first, "url": links[0] if links else "", "text": text}


def to_candidate(post: dict, item_id: str, created: str = "") -> Candidate | None:
    if not ENGINEERING.search(post["header"]):
        return None
    host = re.sub(r"^https?://", "", post["url"]).split("/")[0]
    if CORPORATE_HOST.match(host) or BIG_COMPANY.search(post["text"]):
        return None
    return Candidate(
        url=post["url"] or f"https://news.ycombinator.com/item?id={item_id}",
        title=f"{post['company']} is hiring: {post['roles'][:70]}",
        snippet=post["header"][:160], source="hiring", published_at=created,
        company=post["company"],
        meta={"roles": post["roles"], "item_id": item_id, "text": post["text"], "website": post["url"]},
        content=f"# {post['company']} — hiring on Hacker News\n\n{post['text'][:3500]}\n\nSource: https://news.ycombinator.com/item?id={item_id}",
    )


def fetch(client: httpx.Client | None = None, max_posts: int = MAX_POSTS) -> list[Candidate]:
    client = client or httpx.Client(timeout=20)
    try:
        r = client.get(f"{API}/search_by_date", params={"tags": "story,author_whoishiring", "query": "Who is hiring", "hitsPerPage": 3})
        r.raise_for_status()
        thread = next(h for h in r.json()["hits"] if "who is hiring" in (h.get("title") or "").lower() and "wants to be hired" not in h["title"].lower())
        c = client.get(f"{API}/search", params={"tags": f"comment,story_{thread['objectID']}", "hitsPerPage": 400})
        c.raise_for_status()
        hits = c.json()["hits"]
    except (httpx.HTTPError, StopIteration, KeyError, ValueError):
        return []
    out: list[Candidate] = []
    for h in hits:
        if str(h.get("parent_id")) != str(thread["objectID"]):
            continue  # top-level posts only
        post = parse_post(h.get("comment_text") or "")
        cand = to_candidate(post, h["objectID"], h.get("created_at", "")) if post else None
        if cand:
            out.append(cand)
        if len(out) >= max_posts:
            break
    return out
