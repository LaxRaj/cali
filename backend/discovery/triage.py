"""Filter candidates before the (expensive) crawl + extraction stages."""

import os
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
        if not c.content and any(host == h or host.endswith("." + h) for h in BLOCKED_HOSTS):
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


LLM_SHORTLIST = 60  # Groq free tier allows ~8k tokens/minute; one scoring call must stay well below that


def shortlist(cands: list[Candidate], n: int = LLM_SHORTLIST) -> list[Candidate]:
    """Round-robin across sources (keeping each source's own order) so no feed crowds out the rest."""
    by_src: dict[str, list[Candidate]] = defaultdict(list)
    for c in cands:
        by_src[c.source].append(c)
    out: list[Candidate] = []
    while len(out) < n and any(by_src.values()):
        for src in list(by_src):
            if by_src[src] and len(out) < n:
                out.append(by_src[src].pop(0))
    return out


def llm_scores(cands: list[Candidate], client=None) -> dict[int, int]:
    lines = "\n".join(f"{i}. [{c.source}] {c.title[:110]} — {c.snippet[:90]}" for i, c in enumerate(cands))
    data = chat_json(SYSTEM, lines, client, purpose="triage")
    return {int(s["i"]): int(s["score"]) for s in data.get("scores", [])}


DECIDER_SHORTLIST = 150  # local decisions are ~free, so we can look at far more candidates than the LLM could
BORDER_LO, BORDER_HI, REFINE_MAX = 3.5, 6.5, 20  # only genuinely uncertain items get an LLM second opinion


def decider_scores(cands: list[Candidate], decider, client=None, refine: bool = False) -> dict[int, float]:
    """Score with the decision layer (local/Jev); optionally let the LLM re-score a few borderline items."""
    from decide.decisions import triage_scores

    scores = dict(enumerate(triage_scores(cands, decider)))
    if refine:
        border = [i for i, v in sorted(scores.items(), key=lambda kv: abs(kv[1] - 5)) if BORDER_LO <= v <= BORDER_HI][:REFINE_MAX]
        if border:
            try:
                refined = llm_scores([cands[i] for i in border], client)
                for j, i in enumerate(border):
                    if j in refined:
                        scores[i] = round((scores[i] + refined[j]) / 2, 2)
            except Exception as e:
                print(f"LLM refinement skipped: {e}")
    return scores


def select(
    cands: list[Candidate],
    seen: set[str],
    client=None,
    min_score: int = 4,
    caps: dict[str, int] | None = None,
    decider=None,
    refine_llm: bool = os.environ.get("CALI_REFINE") == "1",
) -> list[Candidate]:
    """Dedupe, drop junk/seen, score, then take the best with a per-source cap.

    With a `decider` (the default in the pipeline) scoring is local and free; the LLM only breaks ties on
    borderline items. Without one, the LLM scores a shortlist (the original behaviour).
    """
    if decider is not None:
        cands = shortlist(heuristic_filter(cands, seen), DECIDER_SHORTLIST)
        scores = decider_scores(cands, decider, client, refine_llm)
    else:
        cands = shortlist(heuristic_filter(cands, seen))
        try:
            scores = llm_scores(cands, client)
        except Exception as e:
            print(f"LLM triage failed, keeping heuristic order: {e}")
            scores = {i: 5 for i in range(len(cands))}
    for i, c in enumerate(cands):
        c.triage = float(scores.get(i, 0))
    ranked = sorted(
        ((scores[i], c) for i, c in enumerate(cands) if scores.get(i, 0) >= min_score),
        key=lambda sc: -sc[0],
    )
    per_source: dict[str, int] = defaultdict(int)
    chosen = []
    for _, c in ranked:
        if per_source[c.source] >= (caps or {}).get(c.source, PER_SOURCE_CAP):
            continue
        per_source[c.source] += 1
        chosen.append(c)
    return chosen[:MAX_CRAWLS]
