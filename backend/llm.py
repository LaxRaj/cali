"""Shared Groq helpers."""

import json
import os

from groq import Groq

# Groq no longer serves any Llama 70B model; gpt-oss-120b is the closest large model available.
MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")


def get_client() -> Groq:
    return Groq(max_retries=5)  # the SDK backs off on 429s; reads GROQ_API_KEY


def chat_json(system: str, user: str, client: Groq | None = None) -> dict:
    client = client or get_client()
    completion = client.chat.completions.create(
        model=MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    return json.loads(completion.choices[0].message.content)
