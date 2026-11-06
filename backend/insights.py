"""Derived, zero-cost insights baked into profiles.json (the dashboard stays static):

* similar companies   -- cosine over the MiniLM vectors already stored per startup (Harmonic/PredictLeads-style lookalikes)
* change timeline     -- what we learned about a company, when, and from which page (from the evidence ledger + signals)
* watchlist           -- companies / keywords you follow (data/watchlist.json); hits are flagged in the export and brief
"""

import json
import re
from pathlib import Path

import numpy as np

SIMILAR_K, SIMILAR_MIN = 5, 0.35
WATCHLIST = "watchlist.json"
FIELD_LABELS = {
    ("startup", "funding_stage"): "Stage", ("startup", "funding_amount"): "Raised", ("startup", "hq"): "HQ",
    ("startup", "website"): "Website", ("startup", "core_product"): "Product", ("startup", "likely_bottleneck"): "Bottleneck",
    ("contact", "email"): "Published email", ("contact", "phone"): "Published phone",
    ("person", "role"): "Person", ("person", "linkedin"): "Profile link", ("person", "homepage"): "Homepage",
}


def similar_companies(rows: list[dict], slug_of, k: int = SIMILAR_K, min_sim: float = SIMILAR_MIN) -> dict[str, list[dict]]:
    """company_name -> [{"company_name", "slug", "similarity"}] nearest neighbours by stored embedding."""
    named = [(r["company_name"], r.get("vector")) for r in rows if r.get("vector") is not None]
    if len(named) < 2:
        return {}
    names = [n for n, _ in named]
    m = np.asarray([v for _, v in named], dtype=np.float32)
    m /= np.linalg.norm(m, axis=1, keepdims=True) + 1e-9
    sims = m @ m.T
    np.fill_diagonal(sims, -1)
    out: dict[str, list[dict]] = {}
    for i, name in enumerate(names):
        idx = np.argsort(-sims[i])[:k]
        out[name] = [{"company_name": names[j], "slug": slug_of(names[j]), "similarity": round(float(sims[i, j]), 3)}
                     for j in idx if sims[i, j] >= min_sim]
    return out


def _iso(raw: str) -> str:
    """ISO-8601 UTC for any date a feed gave us (RSS uses RFC 2822: 'Thu, 05 Nov 2026 11:50:53 +0000'); '' if unparseable."""
    from datetime import datetime, timezone
    from email.utils import parsedate_to_datetime

    if not raw:
        return ""
    try:
        t = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        try:
            t = parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            return ""
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return t.astimezone(timezone.utc).isoformat(timespec="seconds")


def timeline(trackbacks: list[dict], signals: list[dict], discovered_at: str = "", limit: int = 12) -> list[dict]:
    """Newest first. One event per run in which we learned something (first sighting of facts), plus dated signals."""
    by_run: dict[str, dict] = {}
    for t in trackbacks:
        key = t.get("run_id") or t["first_seen"][:10]
        ev = by_run.setdefault(key, {"at": t["first_seen"], "kind": "learned", "items": [], "source_urls": []})
        ev["at"] = min(ev["at"], t["first_seen"])
        label = FIELD_LABELS.get((t["entity_type"], t["field"]))
        if t["entity_type"] == "edge":
            label = t["field"].replace("_", " ").capitalize()
        text = f"{label or t['field'].replace('_', ' ')}: {t.get('value') or t.get('label', '')}"[:140]
        if text not in ev["items"]:
            ev["items"].append(text)
        if t.get("source_url") and t["source_url"] not in ev["source_urls"]:
            ev["source_urls"].append(t["source_url"])
    events = sorted(by_run.values(), key=lambda e: e["at"])
    if events:
        events[0]["kind"] = "discovered"
    elif discovered_at:
        events = [{"at": discovered_at, "kind": "discovered", "items": [], "source_urls": []}]
    for s in signals or []:
        at = _iso(s.get("posted_at") or s.get("seen_at") or "")
        if not at:
            continue
        roles = ", ".join((s.get("roles") or [])[:3])
        events.append({"at": at, "kind": s["type"], "items": [f"{s['type'].replace('_', ' ').capitalize()}{': ' + roles if roles else ''}"],
                       "source_urls": [s["url"]] if s.get("url") else []})
    for e in events:
        e["count"] = len(e["items"])
        e["items"], e["source_urls"] = e["items"][:6], e["source_urls"][:3]
    return sorted(events, key=lambda e: e["at"], reverse=True)[:limit]


def load_watchlist(data_dir) -> dict:
    """{"companies": [...names], "keywords": [...]}: edit data/watchlist.json by hand (committed, so CI sees it)."""
    try:
        w = json.loads((Path(data_dir) / WATCHLIST).read_text())
    except (OSError, ValueError):
        w = {}
    return {"companies": [c.strip().lower() for c in w.get("companies", []) if c.strip()],
            "keywords": [k.strip().lower() for k in w.get("keywords", []) if k.strip()]}


def watch_hits(profile: dict, watch: dict) -> list[str]:
    """Why this profile matches the watchlist ([] = it does not)."""
    hits = []
    if profile.get("company_name", "").strip().lower() in watch["companies"]:
        hits.append("company")
    text = " ".join(str(profile.get(f) or "") for f in ("core_product", "likely_bottleneck", "hq", "funding_stage")).lower()
    text += " " + " ".join(profile.get("tech_stack") or []).lower()
    hits += [f"keyword: {k}" for k in watch["keywords"] if re.search(rf"\b{re.escape(k)}\b", text)]
    return hits
