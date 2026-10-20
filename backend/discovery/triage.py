"""Filter candidates before the (expensive) crawl + extraction stages."""

import re
from collections import defaultdict

from discovery import Candidate, normalize_url
from llm import chat_json
from objective import MAX_CRAWLS, OBJECTIVE, PER_SOURCE_CAP

BLOCKED_HOSTS = {
    "youtube.com", "youtu.be", "twitter.com", "x.com", "linkedin.com", "reddit.com",
    "facebook.com", "instagram.com", "wikipedia.org", "medium.com", "news.ycombinator.com",
}
JUNK_TITLE = re.compile(
    r"\b(how to|guide|tips|best \w+ (tools|startups)|top \d+|\d+ (best|ways|tips)|checklist|"
    r"playbook|what is|vs\.?|report|market size|forecast)\b",
    re.I,
)


def heuristic_filter(cands: list[Candidate], seen: set[str]) -> list[Candidate]:
    out, keys = [], set()
    for c in cands:
        key = normalize_url(c.url)
        host = key.split("/")[0]
        if key in seen or key in keys:
            continue
        if any(host == h or host.endswith("." + h) for h in BLOCKED_HOSTS):
            continue
        if JUNK_TITLE.search(c.title):
            continue
        keys.add(key)
        out.append(c)
    return out


SYSTEM = f"""You triage search results for this objective:
{OBJECTIVE}

For each numbered item, give an integer score 0-10 for how likely the page is about ONE specific early-stage
startup (its launch, funding, product or founders) that fits the objective. Generic articles, listicles,
big-company news, personal projects and hobby demos score 0-3. Output ONLY JSON:
{{"scores": [{{"i": 0, "score": 7}}, ...]}}"""


def llm_scores(cands: list[Candidate], client=None) -> dict[int, int]:
    lines = "\n".join(f"{i}. [{c.source}] {c.title} — {c.snippet[:160]}" for i, c in enumerate(cands))
    data = chat_json(SYSTEM, lines, client)
    return {int(s["i"]): int(s["score"]) for s in data.get("scores", [])}


def select(cands: list[Candidate], seen: set[str], client=None, min_score: int = 4) -> list[Candidate]:
    """Dedupe, drop junk/seen, LLM-score, then take the best with a per-source cap."""
    cands = heuristic_filter(cands, seen)
    try:
        scores = llm_scores(cands, client)
    except Exception as e:
        print(f"LLM triage failed, keeping heuristic order: {e}")
        scores = {i: 5 for i in range(len(cands))}
    ranked = sorted(
        ((scores[i], c) for i, c in enumerate(cands) if scores.get(i, 0) >= min_score),
        key=lambda sc: -sc[0],
    )
    per_source: dict[str, int] = defaultdict(int)
    chosen = []
    for _, c in ranked:
        if per_source[c.source] >= PER_SOURCE_CAP:
            continue
        per_source[c.source] += 1
        chosen.append(c)
    return chosen[:MAX_CRAWLS]
