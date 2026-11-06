"""Static exports for the dashboard: profiles.json (all startups) and graph.json (the network)."""

import json
import re
from datetime import datetime
from pathlib import Path

from decide.policy import decide_lead
from entities import canonical_key
from draft import build_draft, load_sender
from insights import load_watchlist, similar_companies, timeline, watch_hits
from investors import investor_clusters
from ledger import TABLE as LEDGER
from memory import DB_DIR, EDGES, PEOPLE, TABLE, _rows
from outcomes import load_outcomes
from outreach import load_outbox
from paths import find_path, load_known
from whynow import why_now

PERSON_FIELDS = ("name", "role", "org", "evidence", "linkedin", "twitter", "github", "homepage", "link_source")


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "unnamed"


def _key(name: str) -> str:
    return name.strip().lower()


def _loads(raw) -> dict:
    try:
        return json.loads(raw) if raw else {}
    except ValueError:
        return {}


TRACKBACK_FIELDS = ("entity_type", "entity_key", "field", "label", "value", "source_url", "evidence", "run_id", "first_seen", "last_seen", "seen_count", "confidence")


def _trackbacks(db_dir) -> dict[str, list[dict]]:
    """Ledger facts grouped by canonical company name, most recently seen first."""
    by: dict[str, list[dict]] = {}
    for r in sorted(_rows(LEDGER, db_dir), key=lambda r: r["last_seen"], reverse=True):
        by.setdefault(r["company"], []).append({f: r[f] for f in TRACKBACK_FIELDS})
    return by


def _loads_list(raw) -> list:
    try:
        return json.loads(raw) if raw else []
    except ValueError:
        return []


def lead_scorer(db_dir):
    """p(worth pursuing) from the learned 'lead' head, or None until there are enough recorded outcomes to train it
    (so the embedder is not even loaded when there is nothing to blend in)."""
    try:
        heads = json.loads((Path(db_dir) / "decider_model.json").read_text()).get("heads", {})
    except (OSError, ValueError):
        return None
    if "lead" not in heads:
        return None
    from decide.decisions import LEAD
    from decide.local import LocalProvider
    from decide.training import lead_state

    provider = LocalProvider(data_dir=Path(db_dir))
    return lambda p: provider.decide(lead_state(p), [LEAD])["lead"].noul if lead_state(p) else None


def build_profiles(db_dir, now: datetime | None = None) -> list[dict]:
    people = _rows(PEOPLE, db_dir)
    edges = _rows(EDGES, db_dir)
    outcomes = load_outcomes(db_dir)
    outbox = load_outbox(db_dir)
    known = load_known(db_dir)
    trackbacks = _trackbacks(db_dir)
    rows = _rows(TABLE, db_dir)
    similar = similar_companies(rows, slugify)
    watch = load_watchlist(db_dir)
    out = []
    for r in rows:
        name = r["company_name"]
        k = _key(name)
        row = {f: r[f] for f in r if f not in ("vector", "contact_json", "score_json", "signals_json")}
        contact = _loads(r.get("contact_json"))
        breakdown = _loads(r.get("score_json"))
        out.append(
            {
                **row,
                "slug": slugify(name),
                "score": r.get("score", 0),
                "score_parts": breakdown.get("parts", {}),
                "gaps": breakdown.get("gaps", []),
                "axes": breakdown.get("axes", {}),
                "qualified": breakdown.get("qualified", False),
                "contact": contact,
                "signals": _loads_list(r.get("signals_json")),
                "people": [
                    {f: p.get(f, "") for f in PERSON_FIELDS}
                    for p in people
                    if _key(p["org"]) == k
                ],
                "edges": [
                    {f: e[f] for f in ("src", "rel", "dst", "evidence")}
                    for e in edges
                    if _key(e["src"]) == k or _key(e["dst"]) == k
                ],
            }
        )
    sender = load_sender(db_dir)
    lead_p = lead_scorer(db_dir)
    for p in out:
        outcome = outcomes.get(p["company_name"].strip().lower())
        p["outcome"] = outcome or None
        p["decision"] = decide_lead(p, outcome, now, lead_p=lead_p(p) if lead_p else None)
        p["trackbacks"] = trackbacks.get(canonical_key(p["company_name"]), [])
        p["similar"] = similar.get(p["company_name"], [])
        p["timeline"] = timeline(p["trackbacks"], p["signals"], p.get("discovered_at", ""))
        p["watch"] = watch_hits(p, watch)
        p["why_now"] = why_now(p, now)
        p["warm_path"] = find_path(edges, known, p["company_name"])
        p["email_draft"] = build_draft(p, p["warm_path"], sender=sender)
        p["outreach"] = [
            {f: i[f] for f in ("kind", "status", "to", "updated")}
            for i in outbox.values()
            if i["company"].strip().lower() == _key(p["company_name"])
        ]
    return sorted(out, key=lambda p: (p["score"], p.get("discovered_at", "")), reverse=True)


def build_graph(db_dir) -> dict:
    """Nodes are startups / people / orgs (investors etc.); edges are the typed, evidenced links."""
    nodes: dict[str, dict] = {}

    def add(name: str, kind: str, **extra):
        k = _key(name)
        if k and k not in nodes:
            nodes[k] = {"id": k, "label": name.strip(), "type": kind, "degree": 0, **extra}
        return k

    for r in _rows(TABLE, db_dir):
        add(r["company_name"], "startup", website=r.get("website", ""), score=r.get("score", 0))
    for p in _rows(PEOPLE, db_dir):
        links = {f: p.get(f, "") for f in ("linkedin", "twitter", "github", "homepage") if p.get(f, "")}
        add(p["name"], "person", role=p.get("role", ""), links=links)

    sources: dict[str, list[dict]] = {}
    for o in sorted(_rows(LEDGER, db_dir), key=lambda o: o["first_seen"]):
        if o["entity_type"] == "edge":
            sources.setdefault(o["entity_key"], []).append({f: o[f] for f in ("source_url", "run_id", "first_seen", "last_seen")})

    edges = []
    for e in _rows(EDGES, db_dir):
        s, t = add(e["src"], "org"), add(e["dst"], "org")  # unknown endpoints (funds, companies) are orgs
        if not s or not t or s == t:
            continue
        found = sources.get(f"{canonical_key(e['src'])}|{e['rel']}|{canonical_key(e['dst'])}", [])
        edges.append({"source": s, "target": t, "rel": e["rel"], "evidence": e["evidence"], "sources": found})
        nodes[s]["degree"] += 1
        nodes[t]["degree"] += 1
    startups = [n["label"] for n in nodes.values() if n["type"] == "startup"]
    raw = [{f: e[f] for f in ("src", "rel", "dst", "evidence")} for e in _rows(EDGES, db_dir)]
    return {
        "nodes": sorted(nodes.values(), key=lambda n: -n["degree"]),
        "edges": edges,
        "investors": investor_clusters(raw, startups),
    }


def export_all(db_dir=DB_DIR) -> None:
    db_dir = Path(db_dir)
    (db_dir / "profiles.json").write_text(json.dumps(build_profiles(db_dir), indent=2, ensure_ascii=False))
    (db_dir / "graph.json").write_text(json.dumps(build_graph(db_dir), indent=2, ensure_ascii=False))
