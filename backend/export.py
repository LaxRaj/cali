"""Static exports for the dashboard: profiles.json (all startups) and graph.json (the network)."""

import json
import re
from datetime import datetime
from pathlib import Path

from decide.policy import decide_lead
from outcomes import load_outcomes

PERSON_FIELDS = ("name", "role", "org", "evidence", "linkedin", "twitter", "github", "homepage", "link_source")

from memory import DB_DIR, EDGES, PEOPLE, TABLE, _rows


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "unnamed"


def _key(name: str) -> str:
    return name.strip().lower()


def _loads(raw) -> dict:
    try:
        return json.loads(raw) if raw else {}
    except ValueError:
        return {}


def build_profiles(db_dir, now: datetime | None = None) -> list[dict]:
    people = _rows(PEOPLE, db_dir)
    edges = _rows(EDGES, db_dir)
    outcomes = load_outcomes(db_dir)
    out = []
    for r in _rows(TABLE, db_dir):
        name = r["company_name"]
        k = _key(name)
        row = {f: r[f] for f in r if f not in ("vector", "contact_json", "score_json")}
        contact = _loads(r.get("contact_json"))
        breakdown = _loads(r.get("score_json"))
        out.append(
            {
                **row,
                "slug": slugify(name),
                "score": r.get("score", 0),
                "score_parts": breakdown.get("parts", {}),
                "gaps": breakdown.get("gaps", []),
                "contact": contact,
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
    for p in out:
        outcome = outcomes.get(p["company_name"].strip().lower())
        p["outcome"] = outcome or None
        p["decision"] = decide_lead(p, outcome, now)
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

    edges = []
    for e in _rows(EDGES, db_dir):
        s, t = add(e["src"], "org"), add(e["dst"], "org")  # unknown endpoints (funds, companies) are orgs
        if not s or not t or s == t:
            continue
        edges.append({"source": s, "target": t, "rel": e["rel"], "evidence": e["evidence"]})
        nodes[s]["degree"] += 1
        nodes[t]["degree"] += 1
    return {"nodes": sorted(nodes.values(), key=lambda n: -n["degree"]), "edges": edges}


def export_all(db_dir=DB_DIR) -> None:
    db_dir = Path(db_dir)
    (db_dir / "profiles.json").write_text(json.dumps(build_profiles(db_dir), indent=2, ensure_ascii=False))
    (db_dir / "graph.json").write_text(json.dumps(build_graph(db_dir), indent=2, ensure_ascii=False))
