"""Pick the decision provider. CALI_DECIDER = local (default) | jev | auto (jev only if TYPESAFE_API_KEY is set)."""

import os
import time

from decide.jev import JevProvider, ProviderError
from decide.protocol import Answer, DecisionProvider, Question

STATS: dict = {"provider": "local", "calls": 0, "fallbacks": 0, "latency_ms": 0.0, "jev_input_tokens": 0}


def reset_stats(provider: str = "local") -> None:
    STATS.update({"provider": provider, "calls": 0, "fallbacks": 0, "latency_ms": 0.0, "jev_input_tokens": 0})


class FallbackProvider:
    """Primary provider with automatic fallback to the local one (never lets a hosted outage stop a run)."""

    def __init__(self, primary, fallback):
        self.primary, self.fallback = primary, fallback
        self.name = primary.name

    def decide(self, state: str, questions: list[Question]) -> dict[str, Answer]:
        t = time.monotonic()
        try:
            out = self.primary.decide(state, questions)
        except ProviderError:
            STATS["fallbacks"] += 1
            out = self.fallback.decide(state, questions)
        STATS["calls"] += 1
        STATS["latency_ms"] += (time.monotonic() - t) * 1000
        STATS["jev_input_tokens"] = getattr(self.primary, "input_tokens", 0)
        return out


_cache: dict[str, DecisionProvider] = {}


def get_provider(mode: str | None = None) -> DecisionProvider:
    mode = (mode or os.environ.get("CALI_DECIDER", "local")).lower()
    if mode == "auto":
        mode = "jev" if os.environ.get("TYPESAFE_API_KEY") else "local"
    if mode in _cache:
        return _cache[mode]
    from decide.local import LocalProvider

    local = LocalProvider()
    if mode == "jev":
        jev = JevProvider()
        provider: DecisionProvider = FallbackProvider(jev, local) if jev.available else local
    else:
        provider = local
    _cache[mode] = provider
    return provider


def timed(provider: DecisionProvider):
    """Wrap a plain provider so its calls show up in STATS (the fallback wrapper already does)."""
    if isinstance(provider, FallbackProvider):
        return provider

    class _Timed:
        name = provider.name

        def decide(self, state, questions):
            t = time.monotonic()
            out = provider.decide(state, questions)
            STATS["calls"] += 1
            STATS["latency_ms"] += (time.monotonic() - t) * 1000
            return out

    return _Timed()
