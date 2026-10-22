"""Is the product actually live? Deterministic markers over pages already crawled for enrichment."""

import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

PRICING = re.compile(r"pricing|/plans?\b|/buy\b", re.I)
SIGNUP = re.compile(r"sign.?up|get started|start (free|now|building)|try (it )?(free|now)|book a demo|request (a )?demo|create account|/register", re.I)
LOGIN = re.compile(r"log.?in|sign.?in|/login|/app\b|app\.", re.I)
WAITLIST = re.compile(r"wait.?list|coming soon|early access|request (early )?access|join the beta|private beta", re.I)
CUSTOMERS = re.compile(r"trusted by|our customers|customer stories|case stud|testimonial|used by teams", re.I)
CHANGELOG = re.compile(r"changelog|release notes|what.?s new", re.I)
COPYRIGHT = re.compile(r"(?:©|&copy;|copyright)\s*(?:\d{4}\s*[-–]\s*)?(20\d{2})", re.I)


def webapp_check(pages: list[tuple[str, str]], now: datetime | None = None) -> tuple[str, list[dict]]:
    """pages: [(url, html)]. Returns (stage, checks). stage: pre_launch | live_no_pricing | live_pricing | established | unknown."""
    now = now or datetime.now(timezone.utc)
    if not pages:
        return "unknown", []
    flags: dict[str, bool] = dict.fromkeys(("pricing", "signup", "login", "waitlist", "customers", "changelog"), False)
    year = 0
    for _, html in pages:
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(" ", strip=True)
        links = " ".join(f"{a.get('href', '')} {a.get_text(' ', strip=True)}" for a in soup.find_all("a"))
        flags["pricing"] |= bool(PRICING.search(links))
        flags["signup"] |= bool(SIGNUP.search(links))
        flags["login"] |= bool(LOGIN.search(links))
        flags["waitlist"] |= bool(WAITLIST.search(text))
        flags["customers"] |= bool(CUSTOMERS.search(text))
        flags["changelog"] |= bool(CHANGELOG.search(links))
        if m := COPYRIGHT.search(text):
            year = max(year, int(m.group(1)))
    live = flags["login"] or (flags["signup"] and not flags["waitlist"])
    if flags["waitlist"] and not live:
        stage = "pre_launch"
    elif live and flags["customers"] and flags["pricing"] and flags["changelog"]:
        stage = "established"
    elif live and flags["pricing"]:
        stage = "live_pricing"
    elif live:
        stage = "live_no_pricing"
    else:
        stage = "unknown"
    markers = [k for k, v in flags.items() if v]
    stale = bool(year) and year < now.year - 1
    return stage, [{
        "name": "webapp_live", "kind": "web", "stage": stage, "age_days": None,
        "value": f"{stage}: {', '.join(markers) or 'no markers'}" + (f"; footer ©{year} (stale)" if stale else ""),
        "evidence_url": pages[0][0], "observed_at": now.isoformat(timespec="seconds"),
        "strength": 0.0 if stage in ("unknown", "pre_launch") or stale else 1.0,
    }]
