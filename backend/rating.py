"""Lead score (0-100) with a breakdown and a list of gaps, so the dashboard shows what a lead still needs.

Besides the sum, `axes` separates the three questions behind a great lead (is it the right company, can we reach
them, do we know enough to say something specific) and `qualified` marks leads worth pursuing.
"""

import re
import unicodedata
from dataclasses import dataclass, field

from models import Contact, Edge, Person, StartupProfile

EARLY = re.compile(r"pre-?seed|seed|series a|angel|accelerator|yc", re.I)
GROWTH = re.compile(r"series b|bridge", re.I)  # still a fit, with less runway for a freelancer to matter
LEADER = re.compile(r"founder|ceo|cto|chief|president", re.I)
INVESTOR_RELS = {"invested_in", "backed_by"}
EMAIL_TIER = {"person": 12, "general": 9, "sales": 9, "support": 6, "press": 6}  # points by how directly it reaches a human


@dataclass
class Rating:
    score: int
    parts: dict[str, int]
    gaps: list[str]
    axes: dict[str, int] = field(default_factory=dict)  # fit / reach / evidence, each 0-100
    qualified: bool = False  # worth pursuing: we know the stage and who runs it, and can reach them


def _stage(text: str) -> str:
    """LLMs and pages emit non-breaking hyphens and fancy dashes ("pre‑seed"); fold them to ASCII."""
    return unicodedata.normalize("NFKC", text or "").replace("‑", "-").replace("–", "-")


def rate(profile: StartupProfile, people: list[Person], edges: list[Edge], contact: Contact | None,
         hiring_roles: list[str] | None = None) -> Rating:
    contact = contact or Contact()
    gaps: list[str] = []
    parts = {"fit": 0, "identity": 0, "people": 0, "connections": 0, "contact": 0}
    stage = _stage(profile.funding_stage)
    if not stage and "ycombinator.com/" in (profile.source_url or "") and "news.ycombinator.com" not in profile.source_url:
        stage = "YC"  # listed on YC's own launches/companies pages: accelerator-backed by definition
    early, growth = bool(EARLY.search(stage)), bool(GROWTH.search(stage))

    # fit (25): is this the kind of startup we want, and do we understand it
    parts["fit"] += 10 if profile.is_relevant else 0
    parts["fit"] += 10 if early else 6 if growth else 0
    understood = len(profile.core_product) > 30 and len(profile.likely_bottleneck) > 20
    parts["fit"] += 5 if understood or (hiring_roles and len(profile.core_product) > 30) else 0  # open roles = a stated need
    if not (early or growth):
        gaps.append("funding stage")

    # identity (15)
    for pts, ok, gap in (
        (6, profile.website or contact.website, "website"),
        (3, profile.hq, "location"),
        (3, profile.funding_amount, "funding amount"),
        (3, profile.tech_stack, "tech stack"),
    ):
        if ok:
            parts["identity"] += pts
        else:
            gaps.append(gap)

    # people (20)
    leaders = [p for p in people if LEADER.search(p.role or "")]
    parts["people"] += 10 if leaders else 0
    parts["people"] += 5 if len(people) >= 2 else 0
    parts["people"] += 5 if any(p.linkedin or p.twitter or p.github for p in people) else 0
    if not leaders:
        gaps.append("founder")
    if not any(p.linkedin or p.twitter or p.github for p in people):
        gaps.append("people profiles")

    # connections (20)
    has_investor = any(e.rel in INVESTOR_RELS for e in edges)
    parts["connections"] += 10 if has_investor else 0
    parts["connections"] += 5 if len(edges) >= 3 else 0
    parts["connections"] += 5 if any(e.rel in {"previously_at", "partner_of", "customer_of", "advises"} for e in edges) else 0
    if not has_investor:
        gaps.append("investors")

    # contact (20): only first-party published details count, and a person's address beats a generic inbox.
    # Phones are rare and optional: they top up the total, but a perfect lead does not need one.
    tier = max((EMAIL_TIER.get(e.kind, 6) for e in contact.emails), default=0)
    parts["contact"] = min(20, tier + (4 if contact.contact_page else 0) + (4 if contact.socials else 0) + (4 if contact.phones else 0))
    if not contact.emails:
        gaps.append("email")
    if not contact.phones:
        gaps.append("phone")

    axes = {
        "fit": round(100 * parts["fit"] / 25),
        "reach": round(100 * min(1.0, (tier + (4 if contact.contact_page else 0) + (2 if contact.socials else 0)) / 12)),
        "evidence": round(100 * (parts["identity"] + parts["people"] + parts["connections"]) / 55),
    }
    qualified = bool(contact.emails or contact.contact_page) and bool(leaders) and (early or growth)
    return Rating(sum(parts.values()), parts, gaps, axes, qualified)
