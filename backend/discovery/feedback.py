"""Rate -> adjust: allocate the crawl budget across sources by how well each has paid off recently."""

import json
from pathlib import Path

from objective import MAX_CRAWLS

LOOKBACK = 14  # most recent runs considered
PRIOR = 0.15  # exploration floor so a source that had a bad week still gets looked at
MIN_PER_SOURCE = 2
MAX_PER_SOURCE = 7


def source_stats(data_dir: Path, lookback: int = LOOKBACK) -> dict[str, dict]:
    """Per source over recent runs: crawled, accepted, avg score, yield (= accepted / crawled)."""
    stats: dict[str, dict] = {}
    runs_dir = Path(data_dir) / "runs"
    for f in sorted(runs_dir.glob("*.json"))[-lookback:] if runs_dir.exists() else []:
        try:
            run = json.loads(f.read_text())
        except ValueError:
            continue
        for a in run.get("accepted", []):
            s = stats.setdefault(a["source"], {"crawled": 0, "accepted": 0, "score_sum": 0})
            s["crawled"] += 1
            s["accepted"] += 1
            s["score_sum"] += a.get("score", 50)
        for r in run.get("rejections", []):
            if "extraction error" in r.get("reasons", []):
                continue  # infrastructure failure (e.g. rate limit), not the source's fault
            stats.setdefault(r["source"], {"crawled": 0, "accepted": 0, "score_sum": 0})["crawled"] += 1
    for s in stats.values():
        s["yield"] = round(s["accepted"] / s["crawled"], 3) if s["crawled"] else 0.0
        s["avg_score"] = round(s["score_sum"] / s["accepted"], 1) if s["accepted"] else 0.0
    return stats


def allocate(stats: dict[str, dict], sources: list[str], total: int = MAX_CRAWLS) -> dict[str, int]:
    """Per-source crawl caps summing to roughly `total`, weighted by yield x quality, never below the floor."""
    weights = {}
    for s in sources:
        st = stats.get(s)
        q = (st["avg_score"] / 60) if st and st["avg_score"] else 1.0
        weights[s] = (st["yield"] if st and st["crawled"] else 0.3) * q + PRIOR
    norm = sum(weights.values())
    return {s: max(MIN_PER_SOURCE, min(MAX_PER_SOURCE, round(total * w / norm))) for s, w in weights.items()}
