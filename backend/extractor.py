"""Turn scraped Markdown into a structured Extraction (startup + people + edges) via Groq."""

import hashlib
import json
import os
import re
from pathlib import Path
from typing import get_args

from groq import Groq

from llm import MODEL, complete, get_client, route_extraction
from models import Extraction, Relation
from objective import OBJECTIVE

MAX_CHARS = 14_000  # ~3.5k tokens: bounds Groq free-tier usage

# Compact field list instead of pydantic's full JSON schema (descriptions and $defs cost ~600 tokens per call).
SCHEMA = (
    '{"startup": {"company_name": str, "core_product": str, "tech_stack": [str], "likely_bottleneck": str, '
    '"value_prop_pitch": str, "is_relevant": bool, "funding_stage": str, "funding_amount": str, "hq": str, '
    '"website": str, "source_url": str, "discovered_at": str}, '
    '"people": [{"name": str, "role": str, "org": str, "evidence": str, "linkedin": str, "twitter": str, '
    '"github": str, "homepage": str}], '
    '"edges": [{"src": str, "rel": one of ' + "|".join(get_args(Relation)) + ', "dst": str, "evidence": str}]}'
)

SYSTEM_PROMPT = f"""You analyze web pages about tech startups (launch posts, Show HN, funding news).
Overall goal of the research: {OBJECTIVE}

Return ONLY a JSON object matching this JSON schema:
{SCHEMA}

startup fields:
- company_name: the startup's name; "" if the page is not about one specific startup.
- core_product: one sentence on what it builds.
- tech_stack: technologies explicitly mentioned or strongly implied; [] if none.
- likely_bottleneck: deduce the engineering bottleneck this company most likely faces,
  based on its tech stack and product (e.g. search quality, data-heavy UI, retrieval over unstructured data).
- value_prop_pitch: EXACTLY two sentences, written from a freelance engineer to the company,
  showing how they can remove that bottleneck using Next.js and vector semantic search.
- funding_stage: e.g. "pre-seed", "seed", "Series A", or "" if unknown. funding_amount: e.g. "$5.75M", or "".
- hq: headquarters as stated on the page ("Munich, Germany"), or "".
- website: the COMPANY'S OWN website, only if that URL (or a link to it) appears on the page; never the article's
  own URL or a social network; "" otherwise.
- is_relevant: true ONLY if the page is about ONE specific real early-stage tech startup with a product:
  a launch, a funding announcement, or a founder story about that company. False for: how-to guides,
  listicles, market reports, big-company news, personal side projects/demos, and a company's own
  marketing or SEO blog content that is not about its launch, funding or founders.
  This is about WHAT THE PAGE IS, not whether the startup suits the research goal.
  When false, still fill every field (use "" where unknown).
- Leave source_url and discovered_at as "".

people: founders, key engineers, investors and advisors named on the page. Extract people and edges
thoroughly whenever the page names them, regardless of is_relevant.
- evidence MUST be a short verbatim quote (copy it exactly, character for character, one contiguous
  span, NO ellipses) from the page that supports the person and role.
edges: relationships between named entities, rel one of founded, cofounded, works_at, invested_in, advises,
backed_by, competitor_of, previously_at (a person's earlier employer), partner_of, customer_of, acquired_by.
Capture INVESTORS and funds that led or joined a round (invested_in: fund/person -> startup) and founders'
previous companies (previously_at) whenever stated. src and dst are names (person or company/fund). evidence MUST be a verbatim quote
from the page (one contiguous span, NO ellipses) containing the relationship.
For each person, fill linkedin / twitter / github / homepage ONLY with a URL that literally appears on the page
next to that person (copy it exactly); otherwise leave them "". Never invent people, relationships or URLs that the
page does not state."""


PEOPLE_PROMPT = f"""You read a company's own About/Team page. Return ONLY a JSON object:
{{"people": [{{"name": str, "role": str, "org": str, "evidence": str, "linkedin": str, "twitter": str, "github": str, "homepage": str}}],
 "edges": [{{"src": str, "rel": one of {"|".join(get_args(Relation))}, "dst": str, "evidence": str}}]}}
List founders, key engineers, investors and advisors named on the page. evidence MUST be a short verbatim quote
(one contiguous span, NO ellipses) from the page. Fill profile URLs ONLY if they literally appear next to the person.
Never invent people, relationships or URLs."""
PEOPLE_MAX_CHARS = 6_000

_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LOCAL_LINK = re.compile(r"\[([^\]]*)\]\((?:#|/)[^)]*\)")  # relative / anchor links carry no information
_TRACKING = re.compile(r"[?&]utm_[^\s)&]*")
_NOISE = re.compile(
    r"cookie|consent|subscribe|newsletter|sign (in|up)|log ?in|skip to|©|all rights reserved|terms of (use|service)|"
    r"privacy policy|follow us|share (this|on)|accept all",
    re.I,
)


def clean(markdown: str) -> str:
    """Drop what costs tokens but says nothing: images, relative links, tracking params, short boilerplate lines.
    External URLs are kept (the company website and people's profile links must stay visible to the model)."""
    md = _TRACKING.sub("", _LOCAL_LINK.sub(r"\1", _IMAGE.sub("", markdown)))
    lines = [ln.rstrip() for ln in md.split("\n") if not (len(ln) < 140 and _NOISE.search(ln))]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines))


CACHE_FILE = "extract_cache.jsonl"
CACHE_MAX = 500


def _cache_path() -> Path:
    return Path(os.environ.get("CALI_DATA_DIR") or Path(__file__).parent / "data") / CACHE_FILE


def _cache_key(text: str) -> str:
    return hashlib.sha256((SYSTEM_PROMPT + "\0" + text).encode()).hexdigest()[:24]


def _cache_get(key: str) -> Extraction | None:
    try:
        for line in _cache_path().read_text().splitlines():
            row = json.loads(line)
            if row["k"] == key:
                return Extraction.model_validate(row["v"])
    except (OSError, ValueError, KeyError):
        pass
    return None


def _cache_put(key: str, ex: Extraction) -> None:
    path = _cache_path()
    try:
        rows = path.read_text().splitlines() if path.exists() else []
        rows.append(json.dumps({"k": key, "v": ex.model_dump()}))
        path.write_text("\n".join(rows[-CACHE_MAX:]) + "\n")
    except OSError:
        pass


def extract(markdown: str, client: Groq | None = None) -> Extraction:
    """Structured extraction. Without an explicit client, results are cached by content so a page that was
    already paid for (e.g. in a run that then failed its quality gates) is never sent to the LLM twice."""
    use_cache = client is None
    text = clean(markdown)[:MAX_CHARS]
    key = _cache_key(text)
    if use_cache and (hit := _cache_get(key)):
        return hit
    completion = complete(
        client or get_client(),
        [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": text}],
        models=route_extraction(markdown),
        purpose="extract",
    )
    ex = Extraction.model_validate_json(completion.choices[0].message.content)
    if use_cache:
        _cache_put(key, ex)
    return ex


def extract_people(markdown: str, client: Groq | None = None) -> Extraction:
    """People/edges from an About/Team page: short prompt, small cap, no startup fields."""
    completion = complete(
        client or get_client(),
        [{"role": "system", "content": PEOPLE_PROMPT}, {"role": "user", "content": clean(markdown)[:PEOPLE_MAX_CHARS]}],
        purpose="team",
    )
    data = json.loads(completion.choices[0].message.content)
    stub = {"company_name": "", "core_product": "", "likely_bottleneck": "", "value_prop_pitch": "", "is_relevant": False}
    return Extraction.model_validate({"startup": stub, "people": data.get("people", []), "edges": data.get("edges", [])})
