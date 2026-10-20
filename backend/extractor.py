"""Turn scraped Markdown into a structured StartupProfile via Groq."""

import json
import os

from groq import Groq

from models import StartupProfile

# Groq no longer serves any Llama 70B model; gpt-oss-120b is the closest large model available.
MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
MAX_CHARS = 24_000

SYSTEM_PROMPT = f"""You analyze web pages about tech startups (launch posts, Show HN, funding news).
Return ONLY a JSON object matching this JSON schema:
{json.dumps(StartupProfile.model_json_schema())}

Field rules:
- company_name: the startup's name.
- core_product: one sentence on what it builds.
- tech_stack: technologies explicitly mentioned or strongly implied; [] if none.
- likely_bottleneck: deduce the engineering bottleneck this company most likely faces,
  based on its tech stack and product (e.g. search quality, data-heavy UI, retrieval over unstructured data).
- value_prop_pitch: EXACTLY two sentences, written from a freelance engineer to the company,
  showing how they can remove that bottleneck using Next.js and vector semantic search.
- is_relevant: true only if the page is about a specific early-stage tech startup and a
  Next.js + semantic search engagement plausibly fits; otherwise false (still fill all fields).
Do not invent facts that the page does not support."""


def extract_profile(markdown: str, client: Groq | None = None) -> StartupProfile:
    client = client or Groq()  # reads GROQ_API_KEY
    completion = client.chat.completions.create(
        model=MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": markdown[:MAX_CHARS]},
        ],
    )
    return StartupProfile.model_validate_json(completion.choices[0].message.content)
