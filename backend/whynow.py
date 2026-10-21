"""Deterministic "why now" timing signals for a lead, each with the evidence it came from. No LLM, no network."""

from datetime import datetime, timezone
from urllib.parse import urlparse

FRESH_DAYS = 14
EARLY_STAGES = ("pre-seed", "preseed", "seed", "series a")


def _host(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def _age_days(iso: str, now: datetime) -> int | None:
    try:
        t = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return max((now - t).days, 0)


def why_now(profile: dict, now: datetime | None = None) -> list[dict]:
    """Signals like {"signal": "form_d", "text": ..., "source_url": ...}, strongest first."""
    now = now or datetime.now(timezone.utc)
    url = profile.get("source_url", "")
    host = _host(url)
    age = _age_days(profile.get("discovered_at", ""), now)
    fresh = age is not None and age <= FRESH_DAYS
    out: list[dict] = []

    if host.endswith("sec.gov") and fresh:
        out.append({"signal": "form_d", "text": f"Filed an SEC Form D {age}d ago: money just came in", "source_url": url})
    if host == "news.ycombinator.com" and fresh:
        out.append({"signal": "hn", "text": f"Posted on Hacker News {age}d ago (hiring or launch)", "source_url": url})
    stage = (profile.get("funding_stage") or "").lower()
    if fresh and stage in EARLY_STAGES:
        out.append({"signal": "early_stage", "text": f"Newly found at {stage} stage", "source_url": url})
    for sig in profile.get("signals") or []:
        a = _age_days(sig.get("posted_at") or sig.get("seen_at", ""), now)
        when = f" ({a}d ago)" if a is not None else ""
        roles = ", ".join(sig.get("roles", [])[:3])
        text = {
            "hiring": f"Hiring{when}: {roles}" if roles else f"Hiring{when}",
            "seeking_freelancer": f"Looking for freelancers{when}",
            "launch": f"Launched{when}", "funding": f"Raised money{when}",
        }.get(sig.get("type", ""), "")
        if text:
            out.append({"signal": sig["type"], "text": text, "source_url": sig.get("url", "")})
    return out
