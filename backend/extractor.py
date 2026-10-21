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

MAX_CHARS = 9_000  # ~2.2k tokens; launch/funding facts sit at the top of a page

# Compact field list instead of pydantic's full JSON schema (descriptions and $defs cost ~600 tokens per call).
SCHEMA = (
    '{"startup": {"company_name": str, "core_product": str, "tech_stack": [str], "likely_bottleneck": str, '
    '"value_prop_pitch": str, "is_relevant": bool, "funding_stage": str, "funding_amount": str, "hq": str, '
    '"website": str, "source_url": str, "discovered_at": str}, '
    '"people": [{"name": str, "role": str, "org": str, "evidence": str, "linkedin": str, "twitter": str, '
    '"github": str, "homepage": str}], '
    '"edges": [{"src": str, "rel": one of ' + "|".join(get_args(Relation)) + ', "dst": str, "evidence": str}]}'
)

SYSTEM_PROMPT = f"""Extract a tech startup from a web page (launch, funding, Show HN, founder story). Return ONLY JSON:
{SCHEMA}

startup:
- company_name: the startup; "" if the page is not about one specific startup. core_product: one sentence.
- tech_stack: technologies stated or strongly implied, else [].
- likely_bottleneck: the engineering bottleneck this company most likely faces, from its stack and product.
- value_prop_pitch: EXACTLY two sentences from a freelance engineer to the company on removing that bottleneck
  with Next.js and vector semantic search.
- funding_stage ("seed", "Series A"...) and funding_amount ("$5.75M") if stated; hq as stated; else "".
- website: the company's OWN site, only if that URL appears on the page (never the article URL or a social network).
- is_relevant: true ONLY if the page is about ONE real early-stage tech startup with a product (launch, funding or
  founder story). False for how-to guides, listicles, market reports, big-company news, hobby projects/demos and
  a company's generic marketing/SEO posts. When false return company_name "", all else empty, "people": [], "edges": [].
- source_url, discovered_at: "".

people: HUMAN founders, key engineers, investors and advisors named on the page, with title. Funds, companies and
past employers are NOT people (use edges). evidence = short verbatim quote (one contiguous span, NO ellipses).
Fill linkedin/twitter/github/homepage ONLY with a URL printed next to that person; else "".
edges: investors/funds in the round (invested_in: investor -> startup), founders (founded/cofounded), founders'
earlier companies (previously_at), advises, backed_by, customer_of, etc. src/dst are names; evidence = verbatim quote.
Never invent people, relationships or URLs."""


PEOPLE_PROMPT = f"""You read a company's own About/Team page. Return ONLY a JSON object:
{{"people": [{{"name": str, "role": str, "org": str, "evidence": str, "linkedin": str, "twitter": str, "github": str, "homepage": str}}],
 "edges": [{{"src": str, "rel": one of {"|".join(get_args(Relation))}, "dst": str, "evidence": str}}]}}
List founders, key engineers, investors and advisors named on the page. evidence MUST be a short verbatim quote
(one contiguous span, NO ellipses) from the page. Fill profile URLs ONLY if they literally appear next to the person.
Never invent people, relationships or URLs."""
PEOPLE_MAX_CHARS = 4_000

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
