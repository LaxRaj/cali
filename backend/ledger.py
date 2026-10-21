"""Append-only provenance ledger: every fact we store, with the page it came from and when we saw it.

Lives in its own lance table (`observations`) so the entity tables and their keys stay untouched. One row per
(entity, field, value, source) with first_seen / last_seen / seen_count, so re-finding a fact on a later run
extends its history instead of overwriting it. Powers the "trackbacks" on the startup pages and graph edges.
"""

import hashlib
from pathlib import Path

from entities import canonical_key
from memory import DB_DIR, _rows, _upsert
from models import Contact, Edge, Person, StartupProfile

TABLE = "observations"
STARTUP_FIELDS = ("funding_stage", "funding_amount", "hq", "website", "core_product", "likely_bottleneck")

# How much we trust where a value came from.
GROUNDED = 1.0  # quote verified on the page, or published by the company itself
MATCHED = 0.6  # profile found by a name/company match in search results
INFERRED = 0.4  # the LLM's reading of the page (no quote to check)


def _key(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:24]


def _obs(company: str, etype: str, entity: str, field: str, value: str, source_url: str, evidence: str, confidence: float, label: str = "") -> dict:
    return {
        "key": _key(company, etype, entity, field, value, source_url),
        "label": label or f"{field}: {value}",  # human text for the dashboard; not part of the key
        "company": company, "entity_type": etype, "entity_key": entity, "field": field,
        "value": value, "source_url": source_url, "evidence": evidence, "confidence": confidence,
    }


def observations_for(startup: StartupProfile, people: list[Person], edges: list[Edge], contact: Contact | None, source_url: str) -> list[dict]:
    """The facts of one accepted startup as ledger rows (without run id / dates; `record` adds those)."""
    co = canonical_key(startup.company_name)
    out = []
    for f in STARTUP_FIELDS:
        v = getattr(startup, f, "")
        if v:
            out.append(_obs(co, "startup", co, f, str(v), source_url, "", INFERRED))
    for p in people:
        pk = f"{canonical_key(p.name)}|{canonical_key(p.org) or co}"
        out.append(_obs(co, "person", pk, "role", p.role, source_url, p.evidence, GROUNDED, f"{p.name} · {p.role}"))
        for net in ("linkedin", "twitter", "github", "homepage"):
            url = getattr(p, net)
            if url:
                out.append(_obs(co, "person", pk, net, url, p.link_source or source_url, p.evidence, MATCHED if p.link_source == "search" else GROUNDED, f"{p.name} · {net}"))
    for e in edges:
        ek = f"{canonical_key(e.src)}|{e.rel}|{canonical_key(e.dst)}"
        out.append(_obs(co, "edge", ek, e.rel, f"{e.src} {e.rel} {e.dst}", source_url, e.evidence, GROUNDED, f"{e.src} {e.rel.replace('_', ' ')} {e.dst}"))
    if contact:
        for kind, items in (("email", contact.emails), ("phone", contact.phones)):
            for it in items:
                out.append(_obs(co, "contact", co, kind, it.value, it.source_url, "", GROUNDED))
        for net, url in contact.socials.items():
            out.append(_obs(co, "contact", co, net, url, contact.contact_page or contact.website, "", GROUNDED))
    return out


def record(rows: list[dict], run_id: str, now: str, db_dir: str | Path = DB_DIR) -> int:
    """Merge observations into the ledger. Known facts keep first_seen and gain last_seen / seen_count; returns new-fact count."""
    if not rows:
        return 0
    existing = {r["key"]: r for r in _rows(TABLE, db_dir)}
    merged, new = {}, 0
    for r in rows:
        old = existing.get(r["key"]) or merged.get(r["key"])
        if old:
            seen = old["seen_count"] + (0 if old.get("run_id") == run_id else 1)
            merged[r["key"]] = {**old, "last_seen": now, "run_id": run_id, "seen_count": seen, "evidence": r["evidence"] or old["evidence"]}
        else:
            new += 1
            merged[r["key"]] = {**r, "run_id": run_id, "first_seen": now, "last_seen": now, "seen_count": 1}
    _upsert(TABLE, "key", list(merged.values()), db_dir)
    return new


def load(db_dir: str | Path = DB_DIR) -> list[dict]:
    return _rows(TABLE, db_dir)
