"""Warm-intro paths: shortest chain of evidenced edges from someone/something you know to a target company.

`me.json` (in the data dir, optional): {"known": ["Stripe", "Jane Doe", "Sequoia"]}, the employers, investors and
people you already have a real connection to. No file means no paths. Every hop carries the verbatim evidence quote.
"""

import json
from collections import deque
from pathlib import Path

# Relations that make a believable introduction route; competitor_of / customer_of do not.
INTRO_RELS = {"founded", "cofounded", "works_at", "invested_in", "advises", "backed_by", "previously_at", "partner_of"}
MAX_HOPS = 3


def _key(name: str) -> str:
    return name.strip().lower()


def load_known(data_dir: Path) -> set[str]:
    try:
        raw = json.loads((Path(data_dir) / "me.json").read_text()).get("known", [])
    except (OSError, ValueError, AttributeError):
        return set()
    return {_key(n) for n in raw if isinstance(n, str) and n.strip()}


def find_path(edges: list[dict], known: set[str], target: str, max_hops: int = MAX_HOPS) -> dict | None:
    """BFS over undirected intro edges. Returns {"hops": [{src, rel, dst, evidence}], "via": name, "summary": str}."""
    goal = _key(target)
    if not known or goal in known:
        return None
    adj: dict[str, list[tuple[str, dict]]] = {}
    for e in edges:
        if e["rel"] not in INTRO_RELS:
            continue
        a, b = _key(e["src"]), _key(e["dst"])
        adj.setdefault(a, []).append((b, e))
        adj.setdefault(b, []).append((a, e))

    queue = deque((k, []) for k in sorted(known))
    seen = set(known)
    while queue:
        node, hops = queue.popleft()
        if len(hops) >= max_hops:
            continue
        for nxt, e in adj.get(node, []):
            if nxt in seen:
                continue
            path = hops + [{f: e[f] for f in ("src", "rel", "dst", "evidence")}]
            if nxt == goal:
                via = path[0]["src"] if _key(path[0]["src"]) in known else path[0]["dst"]
                return {"hops": path, "via": via, "summary": _summary(path, via)}
            seen.add(nxt)
            queue.append((nxt, path))
    return None


def _summary(hops: list[dict], via: str) -> str:
    n = len(hops)
    return f"We're {n} step{'s' if n > 1 else ''} apart through {via}"
