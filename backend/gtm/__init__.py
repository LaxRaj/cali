"""GTM-freshness router: cheap checks first, escalate only when the lead looks worth it. Never fatal."""

import os
from datetime import datetime, timezone

from gtm.hn_check import hn_check
from gtm.linkedin_check import linkedin_check
from gtm.score import CUSTOMER_ROLE_KINDS, age_days, score_checks
from gtm.webapp_check import webapp_check

ESCALATE_AT = 1.0  # T0+T1 score needed before we spend the web-app probe


def gtm_enabled() -> bool:
    return os.environ.get("CALI_GTM", "1") != "0"


def _signal_checks(signals: list[dict], now: datetime) -> list[dict]:
    out = []
    for s in signals:
        if s.get("type") != "hiring":
            continue
        when = s.get("posted_at") or s.get("seen_at", "")
        roles = ", ".join(s.get("roles", [])[:3])
        out.append({
            "name": "hiring", "kind": "signal", "age_days": age_days(when, now), "value": f"hiring: {roles}" if roles else "hiring",
            "evidence_url": s.get("url", ""), "observed_at": when,
            "strength": 1.0 if set(s.get("role_kinds", [])) & CUSTOMER_ROLE_KINDS else 0.5,  # sales/customer/founding = hunting customers
        })
    return out


def run_gtm(website: str, company: str, pages: list[tuple[str, str]], socials: dict, people: list, signals: list[dict],
            *, hn_fn=hn_check, now: datetime | None = None) -> dict:
    """The `gtm` block: {score, stage, checked_at, checks}. pages = [(url, html)] already crawled for enrichment."""
    now = now or datetime.now(timezone.utc)
    checks = _signal_checks(signals, now) + linkedin_check(socials, people, now)  # T0: free
    if website:
        checks += hn_fn(website, company, now)  # T1: one HTTP call
    stage = "unknown"
    if any(c["name"] == "hn_launch" for c in checks) or score_checks(checks) >= ESCALATE_AT:  # T2: only worthwhile leads
        stage, web = webapp_check(pages, now)
        checks += web
    return {"score": score_checks(checks, stage), "stage": stage, "checked_at": now.isoformat(timespec="seconds"), "checks": checks}
