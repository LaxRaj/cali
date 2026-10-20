"""Shared Groq helpers."""

import json
import os
from functools import lru_cache

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


class _Completions:
    def __init__(self, owner: "MultiKeyGroq"):
        self._owner = owner

    def create(self, **kwargs):
        return self._owner.create(**kwargs)


class MultiKeyGroq:
    """Several Groq keys behind one client. Quota is per account, so when a key hits its daily token limit
    (TPD 429) we move to the next key and stay there; any other error is raised as usual."""

    def __init__(self, clients: list):
        self.clients = clients
        self.active = 0
        self.chat = type("Chat", (), {"completions": _Completions(self)})()

    def create(self, **kwargs):
        last: Exception | None = None
        for i in range(self.active, len(self.clients)):
            try:
                out = self.clients[i].chat.completions.create(**kwargs)
                self.active = i
                return out
            except Exception as e:
                last = e
                if not quota_exhausted(e):
                    raise
                self.active = i + 1 if i + 1 < len(self.clients) else i  # this key is spent for the day
        raise last  # pragma: no cover


def api_keys() -> list[str]:
    """GROQ_API_KEY, then GROQ_API_KEY_2, GROQ_API_KEY_3, ... (blank values ignored)."""
    names = ["GROQ_API_KEY"] + [f"GROQ_API_KEY_{i}" for i in range(2, 10)]
    return [v for n in names if (v := os.environ.get(n, "").strip())]


@lru_cache(maxsize=4)
def _client_for(keys: tuple[str, ...]):
    if len(keys) <= 1:
        return Groq(max_retries=5)  # the SDK backs off on 429s; reads GROQ_API_KEY
    return MultiKeyGroq([Groq(api_key=k, max_retries=5) for k in keys])


def get_client():
    """One shared client per key set, so a key that is spent for the day is remembered across calls."""
    return _client_for(tuple(api_keys()))


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
