"""Deterministic quality checks: per-record validators and run-level gates (no LLM involved)."""

import re
from dataclasses import asdict, dataclass, field

from models import Edge, Extraction, Person, StartupProfile
from objective import MIN_SOURCES, MIN_VALID_STARTUPS, MIN_VALIDITY_RATE

PLACEHOLDERS = {"", "n/a", "na", "none", "unknown", "null", "unnamed", "tbd", "-"}
_QUOTES = str.maketrans(
    {"‘": "'", "’": "'", "“": '"', "”": '"'}
    | {c: "-" for c in "‐‑‒–—−"}
)


def _norm(text: str) -> str:
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)  # markdown links -> their text
    text = re.sub(r"[*_`#>]", "", text.translate(_QUOTES))
    return re.sub(r"\s+", " ", text).strip().lower()


def is_placeholder(value: str) -> bool:
    return value.strip().lower() in PLACEHOLDERS


def grounded(quote: str, markdown: str) -> bool:
    """True if the quote appears verbatim in the page (after normalising markup, case, dashes).

    A quote may elide text with "..." / "…"; every fragment must then appear, in order.
    """
    page = _norm(markdown)
    fragments = [f.strip(" .,;:") for f in re.split(r"\.{3}|\u2026", _norm(quote))]
    fragments = [f for f in fragments if f]
    if not fragments or max(map(len, fragments)) < 8 or min(map(len, fragments)) < 4:
        return False
    pos = 0
    for f in fragments:
        pos = page.find(f, pos)
        if pos < 0:
            return False
        pos += len(f)
    return True


def sentence_count(text: str) -> int:
    return len([s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s])


def validate_profile(p: StartupProfile) -> list[str]:
    issues = []
    if is_placeholder(p.company_name):
        issues.append("missing company_name")
    if is_placeholder(p.core_product):
        issues.append("missing core_product")
    if not any(t.strip() for t in p.tech_stack):
        issues.append("warn: empty tech_stack")  # soft: real startups often omit their stack
    if is_placeholder(p.likely_bottleneck):
        issues.append("missing likely_bottleneck")
    if sentence_count(p.value_prop_pitch) != 2:
        issues.append(f"pitch has {sentence_count(p.value_prop_pitch)} sentences, expected 2")
    return issues


def filter_people(people: list[Person], markdown: str) -> list[Person]:
    return [
        x for x in people
        if not is_placeholder(x.name) and grounded(x.evidence, markdown) and _norm(x.name) in _norm(markdown)
    ]


def filter_edges(edges: list[Edge], markdown: str) -> list[Edge]:
    return [
        e for e in edges
        if not is_placeholder(e.src) and not is_placeholder(e.dst) and e.src.strip().lower() != e.dst.strip().lower()
        and grounded(e.evidence, markdown)
    ]


@dataclass
class Checked:
    """Outcome of validating one extraction."""

    extraction: Extraction
    accepted: bool
    issues: list[str] = field(default_factory=list)
    dropped_people: int = 0
    dropped_edges: int = 0


def check_extraction(ex: Extraction, markdown: str) -> Checked:
    """Reject non-startups / invalid profiles; strip ungrounded people and edges from the rest."""
    people = filter_people(ex.people, markdown)
    edges = filter_edges(ex.edges, markdown)
    cleaned = ex.model_copy(update={"people": people, "edges": edges})
    if not ex.startup.is_relevant:
        return Checked(cleaned, False, ["not a relevant startup page"], len(ex.people) - len(people), len(ex.edges) - len(edges))
    issues = validate_profile(ex.startup)
    blocking = [i for i in issues if not i.startswith("warn:")]
    return Checked(cleaned, not blocking, issues, len(ex.people) - len(people), len(ex.edges) - len(edges))


@dataclass
class RunReport:
    candidates: int = 0
    crawled: int = 0
    extracted: int = 0
    relevant: int = 0  # pages the LLM called a relevant startup
    valid: int = 0  # ...that also passed validation
    sources: dict[str, int] = field(default_factory=dict)  # valid startups per discovery source
    people: int = 0
    edges: int = 0
    dropped_ungrounded: int = 0
    issues: dict[str, int] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)
    passed: bool = False

    @property
    def validity_rate(self) -> float:
        return self.valid / self.relevant if self.relevant else 0.0

    def to_dict(self) -> dict:
        return {**asdict(self), "validity_rate": round(self.validity_rate, 3)}


def evaluate_run(r: RunReport) -> RunReport:
    """Apply the run-level gates; fills r.failures and r.passed."""
    r.failures = []
    if r.valid < MIN_VALID_STARTUPS:
        r.failures.append(f"only {r.valid} valid startups (< {MIN_VALID_STARTUPS})")
    if r.validity_rate < MIN_VALIDITY_RATE:
        r.failures.append(f"validity rate {r.validity_rate:.0%} (< {MIN_VALIDITY_RATE:.0%})")
    if len(r.sources) < MIN_SOURCES:
        r.failures.append(f"only {len(r.sources)} discovery sources produced valid startups (< {MIN_SOURCES})")
    r.passed = not r.failures
    return r
