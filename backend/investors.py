"""Investor clusters: who backs several startups in our pool, and who co-invests with whom. Pure graph math over the stored edges."""

from collections import defaultdict
from itertools import combinations


def _key(name: str) -> str:
    return name.strip().lower()


def investor_clusters(edges: list[dict], startups: list[str], min_companies: int = 2) -> list[dict]:
    """[{investor, companies, count, co_investors: [{name, shared}]}], biggest portfolio in our pool first.

    `invested_in` runs investor -> company, `backed_by` runs company -> investor. Only companies in `startups` count.
    """
    pool = {_key(s): s for s in startups}
    portfolio: dict[str, set[str]] = defaultdict(set)
    label: dict[str, str] = {}
    for e in edges:
        if e["rel"] == "invested_in":
            inv, co = e["src"], e["dst"]
        elif e["rel"] == "backed_by":
            inv, co = e["dst"], e["src"]
        else:
            continue
        if _key(co) in pool and _key(inv) != _key(co):
            portfolio[_key(inv)].add(_key(co))
            label.setdefault(_key(inv), inv.strip())

    shared: dict[str, dict[str, int]] = defaultdict(dict)
    for a, b in combinations(sorted(portfolio), 2):
        n = len(portfolio[a] & portfolio[b])
        if n:
            shared[a][b] = shared[b][a] = n

    out = [
        {
            "investor": label[k],
            "companies": sorted(pool[c] for c in cos),
            "count": len(cos),
            "co_investors": sorted(({"name": label[o], "shared": n} for o, n in shared[k].items()), key=lambda x: (-x["shared"], x["name"])),
        }
        for k, cos in portfolio.items()
        if len(cos) >= min_companies
    ]
    return sorted(out, key=lambda c: (-c["count"], c["investor"]))
