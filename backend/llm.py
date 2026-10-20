"""Shared Groq helpers."""

import json
import os

from groq import Groq

# Groq no longer serves any Llama 70B model; gpt-oss-120b is the closest large model available.
MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
# Each Groq model has its own daily token quota: when one is exhausted, fall through to the next.
# Only list models that pass the extractor eval (the 20b model failed JSON mode when tried).
MODEL_CHAIN = [m.strip() for m in os.environ.get("GROQ_MODEL_CHAIN", MODEL).split(",") if m.strip()]
SIMPLE_MODEL = os.environ.get("GROQ_MODEL_SIMPLE", "")  # optional cheaper model tried first for short pages


USAGE = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "calls": 0}


def reset_usage() -> None:
    for k in USAGE:
        USAGE[k] = 0


def record_usage(completion) -> None:
    """Accumulate Groq token usage (tolerates fakes without a usage field)."""
    usage = getattr(completion, "usage", None)
    USAGE["calls"] += 1
    for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
        USAGE[k] += int(getattr(usage, k, 0) or 0)


def get_client() -> Groq:
    return Groq(max_retries=5)  # the SDK backs off on 429s; reads GROQ_API_KEY


def route_extraction(markdown: str) -> list[str]:
    """Model order for one page: short/simple pages may try the cheaper model first, then the chain."""
    simple = len(markdown) < 3000 and SIMPLE_MODEL
    return list(dict.fromkeys(([SIMPLE_MODEL] if simple else []) + MODEL_CHAIN))


def complete(client, messages: list[dict], models: list[str] | None = None):
    """chat.completions.create with JSON mode; on a daily-quota 429 try the next model in the chain."""
    chain = models or MODEL_CHAIN
    last: Exception | None = None
    for i, model in enumerate(chain):
        try:
            completion = client.chat.completions.create(
                model=model, temperature=0, response_format={"type": "json_object"}, messages=messages
            )
            record_usage(completion)
            return completion
        except Exception as e:
            last = e
            if not (quota_exhausted(e) and i < len(chain) - 1):
                raise
    raise last  # pragma: no cover


def chat_json(system: str, user: str, client: Groq | None = None) -> dict:
    client = client or get_client()
    completion = complete(client, [{"role": "system", "content": system}, {"role": "user", "content": user}])
    return json.loads(completion.choices[0].message.content)


def quota_exhausted(error: Exception) -> bool:
    """True for Groq's daily-token (TPD) 429: retrying or continuing the run is pointless."""
    return "tokens per day" in str(error).lower() or "(TPD)" in str(error)
