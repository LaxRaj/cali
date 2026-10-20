"""The concrete decisions the scout makes with a provider (Jev-shaped questions, local by default)."""

import math
import re
from dataclasses import dataclass

from decide.protocol import DecisionProvider, noul
from decide.registry import get_provider, timed

# Prototype sentences (' || ' separates examples). Tuned on real titles from our own runs.
STARTUP_TRUE = " || ".join([
    "company raises seed funding round led by investors",
    "startup announces Series A financing",
    "founders launch a new startup building software for businesses",
    "YC-backed startup launches its product",
    "developer tools company for AI and data teams",
    "B2B SaaS platform for teams and enterprises",
    "AI infrastructure startup",
])
STARTUP_FALSE = " || ".join([
    "tutorial or step by step how-to guide",
    "listicle of the top 10 best tools",
    "industry funding report and market trends roundup",
    "Amazon, Google, Microsoft, Apple or Nvidia big tech company announcement",
    "video game, retro console emulator, or hobby side project built for fun",
    "personal website, toy demo or art project",
    "opinion essay or news commentary",
    "company reaches multibillion dollar valuation",
])
STARTUP = noul("startup", "Is this about one specific early-stage startup (a launch, funding round, product or founders)?",
               STARTUP_TRUE, STARTUP_FALSE)

# Prior (logit shift) per discovery source: where startups are announced vs where hobby projects live.
SOURCE_PRIOR = {"launch_hn": 1.5, "yc": 1.0, "edgar": 0.0, "rss": 0.3, "hiring": 0.3, "hn": -0.2, "web": -0.3}
GATE_MIN = 0.30  # skip extraction below this page-level probability (recall-biased: extraction re-checks)
HEAD_CHARS = 600
_PREFIX = re.compile(r"^(Show HN|Launch HN|Tell HN):\s*", re.I)


def _logit(p: float) -> float:
    p = min(max(p, 1e-4), 1 - 1e-4)
    return math.log(p / (1 - p))


def _provider(provider: DecisionProvider | None) -> DecisionProvider:
    return timed(provider or get_provider())


def candidate_state(title: str, snippet: str, source: str) -> str:
    title = _PREFIX.sub("", title).strip()
    # HN snippets are just "N points"; for news/search the snippet is real content
    return f"{title}. {snippet[:120]}" if source in ("rss", "web", "edgar", "hiring") and snippet else title


def triage_scores(cands, provider: DecisionProvider | None = None) -> list[float]:
    """0-10 'is this a startup worth crawling' score per candidate (text semantics + source prior)."""
    prov = _provider(provider)
    out = []
    for c in cands:
        p = prov.decide(candidate_state(c.title, c.snippet, c.source), [STARTUP])["startup"].noul
        out.append(round(10 / (1 + math.exp(-(_logit(p) + SOURCE_PRIOR.get(c.source, 0)))), 2))
    return out


def page_head(markdown: str, n: int = HEAD_CHARS) -> str:
    md = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", markdown)
    md = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", md)
    return re.sub(r"\s+", " ", md).strip()[:n]


@dataclass
class Gate:
    ok: bool
    p: float


def gate_page(markdown: str, provider: DecisionProvider | None = None, threshold: float = GATE_MIN) -> Gate:
    """Cheap check before spending LLM tokens: does the top of the page look like a startup page?"""
    p = _provider(provider).decide(page_head(markdown), [STARTUP])["startup"].noul
    return Gate(p >= threshold, round(p, 3))
