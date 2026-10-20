"""Static exports for the dashboard: profiles.json (all startups) and graph.json (the network)."""

import json
import re
from pathlib import Path

from memory import DB_DIR, EDGES, PEOPLE, TABLE, _rows


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "unnamed"


def _key(name: str) -> str:
    return name.strip().lower()


def build_profiles(db_dir) -> list[dict]:
    people = _rows(PEOPLE, db_dir)
    edges = _rows(EDGES, db_dir)
    out = []
    for r in _rows(TABLE, db_dir):
        name = r["company_name"]
        k = _key(name)
        out.append(
            {
                **{f: r[f] for f in r if f != "vector"},
                "slug": slugify(name),
                "people": [
                    {f: p[f] for f in ("name", "role", "org", "evidence")}
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
    return sorted(out, key=lambda p: p.get("discovered_at", ""), reverse=True)


def build_graph(db_dir) -> dict:
    """Nodes are startups / people / orgs (investors etc.); edges are the typed, evidenced links."""
    nodes: dict[str, dict] = {}

    def add(name: str, kind: str):
        k = _key(name)
        if k and k not in nodes:
            nodes[k] = {"id": k, "label": name.strip(), "type": kind, "degree": 0}
        return k

    for r in _rows(TABLE, db_dir):
        add(r["company_name"], "startup")
    for p in _rows(PEOPLE, db_dir):
        add(p["name"], "person")

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
