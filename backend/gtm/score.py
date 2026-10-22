"""GTM-freshness score: how likely a company is early, live and still hunting for customers.

Each check is a plain dict {"name", "value", "evidence_url", "observed_at", "age_days"?, "kind"} so the whole block
round-trips through the profile JSON. Deterministic: no LLM, no network.
"""

from datetime import datetime, timezone

# weight per check name; edit here (same style as signals.INTENT) or learn from outcomes later
WEIGHTS = {"hn_launch": 3.0, "hiring": 2.0, "webapp_live": 1.5, "linkedin": 0.5}
HALF_LIFE_DAYS = {"hn_launch": 60, "hiring": 30}
STAGE_MULT = {"pre_launch": 0.6, "live_no_pricing": 1.2, "live_pricing": 1.0, "established": 0.5, "unknown": 0.9}
CUSTOMER_ROLE_KINDS = {"sales", "customer", "founding"}


def decay(age_days: float | None, half_life: float) -> float:
    if age_days is None:
        return 0.3  # known to exist, undated: weak credit
    return 0.5 ** (max(age_days, 0) / half_life)


def age_days(iso: str, now: datetime) -> int | None:
    try:
        t = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return max((now - t).days, 0)


def band(days: int | None) -> str:
    if days is None:
        return "undated"
    return "hot" if days <= 30 else "warm" if days <= 180 else "cooling" if days <= 365 else "cold"


def score_checks(checks: list[dict], stage: str = "unknown") -> float:
    """Sum of weight x strength x recency decay over the checks, scaled by the web-app stage. Rounded to 0.1."""
    total = 0.0
    for c in checks:
        w = WEIGHTS.get(c.get("name", ""), 0.0) * float(c.get("strength", 1.0))
        hl = HALF_LIFE_DAYS.get(c.get("name", ""))
        total += w * (decay(c.get("age_days"), hl) if hl else 1.0)
    return round(total * STAGE_MULT.get(stage, 0.9), 1)
