"""Lead decision policy: what to do with a lead next, and how urgently. Deterministic and explainable.

Inputs are the exported profile fields (score, gaps, contact, people, discovered_at, funding_stage) plus any
outcome you recorded. Output: action (contact_now | enrich_more | watch | skip | follow_up), urgency
(hot | warm | cold), a ranking `priority`, plain-language `reasons`, and a concrete `next_step`.
"""

from datetime import datetime, timezone

from outreach import LEGACY_TYPE, fold

HOT_DAYS, WARM_DAYS = 7, 21


def _age_days(iso: str, now: datetime) -> float | None:
    try:
        t = datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return max((now - t).total_seconds() / 86400, 0.0)


def _state_from_outcome(outcome: dict | None, now: datetime) -> dict:
    """Outreach state for callers that only have the legacy single-record outcome."""
    if not outcome:
        return fold([], now)
    etype = LEGACY_TYPE.get(outcome.get("status", ""))
    if not etype:
        return fold([], now)
    event = {"id": "legacy", "company": outcome.get("company", ""), "type": etype, "at": outcome.get("updated", ""), "reason": outcome.get("reason", "")}
    return fold([event], now)


def decide_lead(profile: dict, outcome: dict | None = None, now: datetime | None = None, state: dict | None = None) -> dict:
    """`state` is the folded outreach log (outreach.fold); without it the legacy `outcome` record is used."""
    now = now or datetime.now(timezone.utc)
    state = state or _state_from_outcome(outcome, now)
    score = int(profile.get("score") or 0)
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
        return {
            "action": action, "urgency": urgency, "priority": priority, "reasons": reasons, "next_step": next_step, "provider": "policy",
            "due": state["next_due"], "overdue": state["overdue"],
        }

    # 1) Your own outreach always wins.
    status = state["status"]
    if status in ("passed", "won", "meeting"):
        why = state.get("pass_reason", "").replace("_", " ")
        reasons.append(f"you marked this '{status}'" + (f" ({why})" if why else ""))
        return result("skip", "cold", "No action needed", weight=0.2)
    if status == "bounced":
        reasons.append(f"your email to {state['last_to'] or 'them'} bounced")
        return result("enrich_more", "warm", "Find another published contact route", weight=0.8)
    if status in ("contacted", "replied"):
        last = state["replied_at"] if status == "replied" and state["replied_at"] > state["last_contact"] else state["last_contact"]
        reasons.append(f"you {'contacted' if status == 'contacted' else 'heard back'} on {(last or state['last_contact'])[:10]} (touch {state['touches']})")
        if state["snoozed"]:
            reasons.append(f"snoozed until {state['next_due'][:10]}")
            return result("watch", "cold", f"Snoozed until {state['next_due'][:10]}", weight=0.3)
        if state["overdue"]:
            if status == "replied":
                return result("follow_up", "hot", "Reply: they answered and it has been waiting")
            return result("follow_up", "warm", f"Follow up (touch {state['touches'] + 1}): no reply since {state['last_contact'][:10]}")
        if state["exhausted"]:
            reasons.append(f"{state['touches']} touches without a reply")
            return result("watch", "cold", "No reply after several touches: leave it for now", weight=0.2)
        return result("watch", "cold", "Waiting on their reply" if status == "contacted" else "Continue the conversation", weight=0.4)
    if state["snoozed"]:
        reasons.append(f"snoozed until {state['next_due'][:10]}")
        return result("watch", "cold", f"Snoozed until {state['next_due'][:10]}", weight=0.3)

    # 2) Otherwise decide from fit, freshness and reachability.
    reasons.append(f"lead score {score}")
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
