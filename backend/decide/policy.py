"""Lead decision policy: what to do with a lead next, and how urgently. Deterministic and explainable.

Inputs are the exported profile fields (score, gaps, contact, people, discovered_at, funding_stage) plus any
outcome you recorded. Output: action (contact_now | review | enrich_more | watch | skip | follow_up), urgency
(hot | warm | cold), a ranking `priority`, plain-language `reasons`, a concrete `next_step`, and the signal-adjusted
`score` the outreach quality gate checks.

`contact_now` means "the outreach agent may send this": a fresh, strong lead (score >= SEND_MIN_SCORE) with a
company-published address on the company's own domain. Good leads that miss one of those become `review` (a human
looks first) or `enrich_more`. Outreach is email-only, so profile links are never offered as the channel.
"""

from datetime import datetime, timezone
from urllib.parse import urlparse

from signals import signal_strength

HOT_DAYS, WARM_DAYS = 7, 21
FOLLOW_UP_DAYS = 7
SEND_MIN_SCORE = 70  # outreach.py's unattended-send gate uses the same bar
REVIEW_MIN_SCORE = 55
LEAD_HEAD_SPAN = 0.4  # learned 'lead' probability scales priority by 0.8 .. 1.2


def _age_days(iso: str, now: datetime) -> float | None:
    try:
        t = datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return max((now - t).total_seconds() / 86400, 0.0)


def _host(url: str) -> str:
    return urlparse(url or "").netloc.lower().removeprefix("www.")


def found_on_publisher(profile: dict) -> bool:
    """The "website" is just the host the lead was discovered on (a news site, SEC, HN) and does not carry the
    company's name: anything found there is the publisher's, not the company's."""
    from enrich import host_matches_company

    site, found = _host(profile.get("website", "")), _host(profile.get("source_url", ""))
    return bool(site) and site == found and not host_matches_company(site, profile.get("company_name", ""))


def sendable_emails(profile: dict) -> list[dict]:
    """Company-published addresses we may write to: sourced, on the company's own domain, not from a publisher page."""
    from enrich import email_on_company_domain

    if found_on_publisher(profile):
        return []
    site = (profile.get("contact") or {}).get("website") or profile.get("website", "")
    return [
        e for e in (profile.get("contact") or {}).get("emails") or []
        if e.get("source_url") and e.get("kind") not in ("support", "press")
        and email_on_company_domain(e.get("value", ""), site, profile.get("company_name", ""))
    ]


def decide_lead(profile: dict, outcome: dict | None = None, now: datetime | None = None, lead_p: float | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    raw_score = int(profile.get("score") or 0)
    signals = profile.get("signals") or []
    strength = signal_strength(signals, now)  # 0-10: hiring / founding roles / seeking freelancers / fresh launch
    score = min(100, raw_score + round(3 * strength))  # thin hiring-post profiles score low on data, not on intent
    contact = profile.get("contact") or {}
    emails = sendable_emails(profile)
    phones = contact.get("phones") or []
    people = profile.get("people") or []
    gaps = profile.get("gaps") or []
    leaders = [p for p in people if any(k in (p.get("role") or "").lower() for k in ("founder", "ceo", "cto", "chief"))]
    social_people = [p for p in (leaders or people) if p.get("linkedin") or p.get("twitter") or p.get("github")]
    direct = bool(emails)
    reachable = direct or bool(phones) or bool(contact.get("contact_page"))
    age = _age_days(profile.get("discovered_at", ""), now)
    fresh = "hot" if age is not None and age <= HOT_DAYS else "warm" if age is not None and age <= WARM_DAYS else "cold"
    reasons: list[str] = []

    def result(action: str, urgency: str, next_step: str, weight: float = 1.0) -> dict:
        base = score * 0.6 + {"hot": 30, "warm": 15, "cold": 0}[fresh] + (10 if direct else 5 if social_people or phones else 0)
        if lead_p is not None:
            weight *= 1 - LEAD_HEAD_SPAN / 2 + LEAD_HEAD_SPAN * lead_p  # learned from your own replies / passes
        priority = round(base * weight, 1)  # leads that are done or waiting on someone else sink in the ranking
        out = {"action": action, "urgency": urgency, "priority": priority, "reasons": reasons, "next_step": next_step,
               "provider": "policy", "score": score}
        if lead_p is not None:
            out["lead_p"] = round(lead_p, 3)
        return out

    # 1) Your own outcome always wins.
    status = (outcome or {}).get("status")
    if status in ("passed", "won", "meeting"):
        why = (outcome or {}).get("reason", "").replace("_", " ")
        reasons.append(f"you marked this '{status}'" + (f" ({why})" if why else ""))
        return result("skip", "cold", "No action needed", weight=0.2)
    if status in ("contacted", "replied"):
        since = _age_days((outcome or {}).get("updated", ""), now)
        reasons.append(f"you {status} on {(outcome or {}).get('updated', '')[:10]}")
        intent = (outcome or {}).get("intent", "")
        if status == "replied" and intent:
            reasons.append(f"their reply reads as '{intent.replace('_', ' ')}'")
        if status == "contacted" and since is not None and since >= FOLLOW_UP_DAYS:
            return result("follow_up", "warm", "Follow up: no reply recorded in over a week")
        if status == "replied" and intent == "referral":
            return result("review", "hot", "They pointed you to someone else: write to that person")
        return result("watch", "cold", "Waiting on their reply" if status == "contacted" else "Continue the conversation", weight=0.4)

    # 2) Otherwise decide from fit, freshness and reachability.
    reasons.append(f"lead score {raw_score}")
    if strength:
        reasons.append(f"signal strength {strength}/10: " + ", ".join(sorted({s_["type"].replace("_", " ") for s_ in signals})))
    if age is not None:
        reasons.append(f"found {int(age)} day(s) ago ({fresh})")
    if lead_p is not None:
        reasons.append(f"similar to leads that answered: {round(100 * lead_p)}%")
    if found_on_publisher(profile):
        reasons.append("contact details came from a publisher page, not the company")
    if score < 35:
        reasons.append("weak fit or too little data")
        return result("skip", "cold", "Skip unless it resurfaces", weight=0.2)

    first_leader = (leaders or people or [{}])[0].get("name", "a founder")
    if score >= SEND_MIN_SCORE and direct and fresh != "cold":
        reasons.append("fresh, strong fit and a company-published address")
        return result("contact_now", "hot" if fresh == "hot" else "warm", f"Email {emails[0]['value']} with the pitch")
    if score >= REVIEW_MIN_SCORE and (direct or phones or contact.get("contact_page")) and fresh != "cold":
        if direct:
            reasons.append(f"good fit, below the {SEND_MIN_SCORE} bar for unattended sending")
            return result("review", "warm", f"Review the draft, then email {emails[0]['value']} yourself")
        reasons.append("good fit; no company address to email")
        route = contact.get("contact_page") or (phones[0]["value"] if phones else "")
        return result("review", "warm", f"Reach {first_leader} via {route}" if route else "Find a company address on their site")
    if score >= 45 and not reachable:
        reasons.append("fit looks decent but no contact route found")
        return result("enrich_more", "warm" if fresh != "cold" else "cold", "Find a contact: " + (", ".join(gaps[:3]) or "check their site/team page"))
    if score >= REVIEW_MIN_SCORE and fresh == "cold":
        reasons.append("good fit but the news is old")
        return result("watch", "cold", "Revisit when there is fresh news")
    reasons.append("not enough signal yet")
    return result("watch", "cold", "Wait for more data")
