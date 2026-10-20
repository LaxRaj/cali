"""Lead score (0-100) with a breakdown and a list of gaps, so the dashboard shows what a lead still needs."""

import re
from dataclasses import dataclass

from models import Contact, Edge, Person, StartupProfile

EARLY = re.compile(r"pre-?seed|seed|series a|angel|accelerator|yc", re.I)
LEADER = re.compile(r"founder|ceo|cto|chief|president", re.I)
INVESTOR_RELS = {"invested_in", "backed_by"}


@dataclass
class Rating:
    score: int
    parts: dict[str, int]
    gaps: list[str]


def rate(profile: StartupProfile, people: list[Person], edges: list[Edge], contact: Contact | None) -> Rating:
    contact = contact or Contact()
    gaps: list[str] = []
    parts = {"fit": 0, "identity": 0, "people": 0, "connections": 0, "contact": 0}

    # fit (25): is this the kind of startup we want, and do we understand it
    parts["fit"] += 10 if profile.is_relevant else 0
    parts["fit"] += 10 if EARLY.search(profile.funding_stage or "") else 0
    parts["fit"] += 5 if len(profile.core_product) > 30 and len(profile.likely_bottleneck) > 20 else 0
    if not EARLY.search(profile.funding_stage or ""):
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

    # contact (20): only first-party published details count
    parts["contact"] += 10 if contact.emails else 0
    parts["contact"] += 4 if contact.phones else 0
    parts["contact"] += 3 if contact.socials else 0
    parts["contact"] += 3 if contact.contact_page else 0
    if not contact.emails:
        gaps.append("email")
    if not contact.phones:
        gaps.append("phone")

    return Rating(sum(parts.values()), parts, gaps)
