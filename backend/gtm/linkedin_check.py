"""LinkedIn presence only. We never fetch LinkedIn (CLAUDE.md): this just notes company-published profile URLs."""

from datetime import datetime, timezone


def linkedin_check(socials: dict[str, str], people: list, now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    company = socials.get("linkedin", "")
    leaders = [p for p in people if getattr(p, "linkedin", "") and getattr(p, "link_source", "")]
    if not company and not leaders:
        return []
    bits = (["company page"] if company else []) + ([f"{len(leaders)} team profile(s)"] if leaders else [])
    return [{
        "name": "linkedin", "kind": "linkedin", "age_days": None, "value": "published: " + ", ".join(bits),
        "evidence_url": leaders[0].linkedin if leaders else company, "observed_at": now.isoformat(timespec="seconds"),
    }]
