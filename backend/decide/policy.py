"""Lead decision policy: what to do with a lead next, and how urgently. Deterministic and explainable.

Inputs are the exported profile fields (score, gaps, contact, people, discovered_at, funding_stage) plus any
outcome you recorded. Output: action (contact_now | enrich_more | watch | skip | follow_up), urgency
(hot | warm | cold), a ranking `priority`, plain-language `reasons`, and a concrete `next_step`.
"""

from datetime import datetime, timezone

from signals import signal_strength

HOT_DAYS, WARM_DAYS = 7, 21
FOLLOW_UP_DAYS = 7


def _age_days(iso: str, now: datetime) -> float | None:
    try:
        t = datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return max((now - t).total_seconds() / 86400, 0.0)


def decide_lead(profile: dict, outcome: dict | None = None, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    raw_score = int(profile.get("score") or 0)
    signals = profile.get("signals") or []
    strength = signal_strength(signals, now)  # 0-10: hiring / founding roles / seeking freelancers / fresh launch
    score = min(100, raw_score + round(3 * strength))  # thin hiring-post profiles score low on data, not on intent
    contact = profile.get("contact") or {}
    emails = contact.get("emails") or []
    phones = contact.get("phones") or []
    people = profile.get("people") or []
    gaps = profile.get("gaps") or []
    leaders = [p for p in people if any(k in (p.get("role") or "").lower() for k in ("founder", "ceo", "cto", "chief"))]
    social_people = [p for p in (leaders or people) if p.get("linkedin") or p.get("twitter") or p.get("github")]
    direct = bool(emails or phones)
    reachable = direct or bool(social_people) or bool(contact.get("contact_page"))
    age = _age_days(profile.get("discovered_at", ""), now)
    fresh = "hot" if age is not None and age <= HOT_DAYS else "warm" if age is not None and age <= WARM_DAYS else "cold"
    reasons: list[str] = []

    def result(action: str, urgency: str, next_step: str, weight: float = 1.0) -> dict:
        base = score * 0.6 + {"hot": 30, "warm": 15, "cold": 0}[fresh] + (10 if direct else 5 if social_people else 0)
        priority = round(base * weight, 1)  # leads that are done or waiting on someone else sink in the ranking
        return {"action": action, "urgency": urgency, "priority": priority, "reasons": reasons, "next_step": next_step, "provider": "policy"}

    # 1) Your own outcome always wins.
    status = (outcome or {}).get("status")
    if status in ("passed", "won", "meeting"):
        why = (outcome or {}).get("reason", "").replace("_", " ")
        reasons.append(f"you marked this '{status}'" + (f" ({why})" if why else ""))
        return result("skip", "cold", "No action needed", weight=0.2)
    if status in ("contacted", "replied"):
        since = _age_days((outcome or {}).get("updated", ""), now)
        reasons.append(f"you {status} on {(outcome or {}).get('updated', '')[:10]}")
        if status == "contacted" and since is not None and since >= FOLLOW_UP_DAYS:
            return result("follow_up", "warm", "Follow up: no reply recorded in over a week")
        return result("watch", "cold", "Waiting on their reply" if status == "contacted" else "Continue the conversation", weight=0.4)

    # 2) Otherwise decide from fit, freshness and reachability.
    reasons.append(f"lead score {raw_score}")
    if strength:
        reasons.append(f"signal strength {strength}/10: " + ", ".join(sorted({s_["type"].replace("_", " ") for s_ in signals})))
    if age is not None:
        reasons.append(f"found {int(age)} day(s) ago ({fresh})")
    if score < 35:
        reasons.append("weak fit or too little data")
        return result("skip", "cold", "Skip unless it resurfaces", weight=0.2)

    first_leader = (leaders or people or [{}])[0].get("name", "a founder")
    if score >= 70 and direct and fresh != "cold":
        reasons.append("fresh, strong fit and a published way to reach them")
        who = emails[0]["value"] if emails else phones[0]["value"]
        return result("contact_now", "hot" if fresh == "hot" else "warm", f"Email/call {who} with the pitch")
    if score >= 55 and (direct or social_people) and fresh != "cold":
        reasons.append("good fit; reachable through a profile" if not direct else "good fit and reachable")
        via = emails[0]["value"] if emails else "LinkedIn/X"
        return result("contact_now", "warm", f"Reach {first_leader} via {via}")
    if score >= 45 and not reachable:
        reasons.append("fit looks decent but no contact route found")
        return result("enrich_more", "warm" if fresh != "cold" else "cold", "Find a contact: " + (", ".join(gaps[:3]) or "check their site/team page"))
    if score >= 55 and fresh == "cold":
        reasons.append("good fit but the news is old")
        return result("watch", "cold", "Revisit when there is fresh news")
    reasons.append("not enough signal yet")
    return result("watch", "cold", "Wait for more data")
