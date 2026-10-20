"""Turn scraped Markdown into a structured Extraction (startup + people + edges) via Groq."""

import json

from groq import Groq

from llm import MODEL, complete, get_client, route_extraction
from models import Extraction
from objective import OBJECTIVE

MAX_CHARS = 14_000  # ~3.5k tokens: bounds Groq free-tier usage

SYSTEM_PROMPT = f"""You analyze web pages about tech startups (launch posts, Show HN, funding news).
Overall goal of the research: {OBJECTIVE}

Return ONLY a JSON object matching this JSON schema:
{json.dumps(Extraction.model_json_schema())}

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


def extract(markdown: str, client: Groq | None = None) -> Extraction:
    client = client or get_client()
    completion = complete(
        client,
        [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": markdown[:MAX_CHARS]}],
        models=route_extraction(markdown),
    )
    return Extraction.model_validate_json(completion.choices[0].message.content)
