"""Hiring / launch / funding signals: deterministic, no LLM. A signal says *why now* and *what they need*.

A signal is a plain dict so it round-trips through the profile JSON:
    {"type": "hiring"|"launch"|"funding"|"seeking_freelancer", "source": ..., "url": ..., "roles": [...],
     "role_kinds": ["eng", ...], "posted_at": iso, "seen_at": iso}
"""

import re
from datetime import datetime, timezone

from models import Extraction, StartupProfile

# (kind, pattern) in priority order: the first match names the role.
ROLE_KINDS = [
    ("founding", re.compile(r"founding|first (hire|engineer)|co-?founder|\bcto\b|head of engineering", re.I)),
    ("customer", re.compile(r"customer|support|success|solutions|implementation|community|research", re.I)),
    ("sales", re.compile(r"sales|account exec|business development|\bbdr\b|\bsdr\b|growth|marketing|partnership", re.I)),
    ("design", re.compile(r"design|\bux\b|\bui\b|brand", re.I)),
    ("product", re.compile(r"product (manager|lead|owner)|\bpm\b|product$", re.I)),
    ("eng", re.compile(r"engineer|developer|backend|back-end|front.?end|full.?stack|\bml\b|machine learning|\bai\b|data|devops|\bsre\b|infra|software|mobile|\bios\b|android", re.I)),
]
INTENT = {"seeking_freelancer": 3.0, "hiring": 1.7, "launch": 0.6, "funding": 0.8}


def role_kind(title: str) -> str:
    for kind, pat in ROLE_KINDS:
        if pat.search(title or ""):
            return kind
    return "other"


def make_signal(type_: str, source: str, url: str, roles: list[str] | None = None, posted_at: str = "", now: datetime | None = None) -> dict:
    roles = [r.strip() for r in (roles or []) if r.strip()]
    kinds = list(dict.fromkeys(role_kind(r) for r in roles))
    return {
        "type": type_, "source": source, "url": url, "roles": roles[:12], "role_kinds": kinds,
        "posted_at": posted_at, "seen_at": (now or datetime.now(timezone.utc)).isoformat(timespec="seconds"),
    }


def merge_signals(old: list[dict], new: list[dict]) -> list[dict]:
    """One entry per (type, source); the newest sighting wins, roles are unioned."""
    out: dict[tuple, dict] = {(s["type"], s["source"]): s for s in old}
    for s in new:
        k = (s["type"], s["source"])
        if k in out:
            roles = list(dict.fromkeys(out[k].get("roles", []) + s.get("roles", [])))
            kinds = list(dict.fromkeys(out[k].get("role_kinds", []) + s.get("role_kinds", [])))
            s = {**s, "roles": roles[:12], "role_kinds": kinds}
        out[k] = s
    return list(out.values())


def parse_roles(field_text: str) -> list[str]:
    """'Senior Backend Engineer, Product Designer' / 'ML Eng & Founding Eng' -> separate role titles."""
    flat, depth = [], 0
    for ch in field_text:  # separators inside (...) belong to one title: "Data Platform (NYC, Hybrid)"
        depth += (ch == "(") - (ch == ")")
        flat.append("\0" if ch in ",;/&+" and depth <= 0 else ch)
    parts = re.split(r"\0|\band\b", "".join(flat))
    return [r.strip(" .") for r in parts if 3 <= len(r.strip(" .")) <= 70]


def hiring_extraction(company: str, roles_text: str, text: str, website: str = "") -> Extraction:
    """A thin profile built straight from a job post: the post says who they are and who they want; no LLM."""
    paras = [p.strip() for p in re.split(r"\n+", text)
             if len(p.strip()) > 60 and "|" not in p[:80] and not re.match(r"(hi|hello|hey)\b", p.strip(), re.I)]
    product = re.sub(r"\s+", " ", re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", paras[0] if paras else roles_text))[:240]
    sp = StartupProfile(
        company_name=company, core_product=product, likely_bottleneck="", value_prop_pitch="",
        is_relevant=True, website=website,
    )
    return Extraction(startup=sp, people=[], edges=[])


def signal_strength(signals: list[dict], now: datetime | None = None) -> float:
    """0-10: freelancer-seeking > founding/first-hire roles > hiring > fresh launch/funding; decays over 30 days."""
    now = now or datetime.now(timezone.utc)
    best = 0.0
    for s in signals:
        w = INTENT.get(s["type"], 0.3) * 3.0
        kinds = s.get("role_kinds", [])
        if s["type"] == "hiring" and set(kinds) & {"eng", "founding", "product", "customer", "design"}:
            w += 1.5  # roles we can help with directly
        if "founding" in kinds:
            w += 2.0
        if len(s.get("roles", [])) >= 3:
            w += 1.0
        try:
            t = datetime.fromisoformat((s.get("posted_at") or s["seen_at"]).replace("Z", "+00:00"))
            if t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
            age = max((now - t).days, 0)
        except (ValueError, KeyError):
            age = 14
        best = max(best, w * (1.0 if age <= 14 else 0.6 if age <= 30 else 0.3))
    return round(min(best, 10.0), 1)
