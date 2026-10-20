import json
from types import SimpleNamespace

import pytest

import llm
from extractor import extract

REPLY = {"startup": {"company_name": "Acme", "core_product": "p", "likely_bottleneck": "b", "value_prop_pitch": "One. Two.", "is_relevant": True}}


class Chain:
    """Fake Groq client: each model has its own behaviour (ok, or daily-quota 429)."""

    def __init__(self, behaviour):
        self.behaviour, self.models = behaviour, []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.models.append(kw["model"])
        outcome = self.behaviour[kw["model"]]
        if isinstance(outcome, Exception):
            raise outcome
        msg = SimpleNamespace(content=json.dumps(REPLY))
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15))


TPD = RuntimeError("Error code: 429 - Rate limit reached ... on tokens per day (TPD): Limit 200000")


def test_daily_quota_falls_through_to_the_next_model(monkeypatch):
    monkeypatch.setattr(llm, "MODEL_CHAIN", ["big", "backup"])
    c = Chain({"big": TPD, "backup": "ok"})
    ex = extract("page", client=c)
    assert ex.startup.company_name == "Acme" and c.models == ["big", "backup"]


def test_non_quota_errors_and_last_model_failures_are_not_swallowed(monkeypatch):
    monkeypatch.setattr(llm, "MODEL_CHAIN", ["big", "backup"])
    with pytest.raises(RuntimeError, match="boom"):
        extract("page", client=Chain({"big": RuntimeError("boom"), "backup": "ok"}))
    with pytest.raises(RuntimeError, match="TPD"):
        extract("page", client=Chain({"big": TPD, "backup": TPD}))


def test_short_pages_try_the_cheap_model_first_only_if_configured(monkeypatch):
    monkeypatch.setattr(llm, "MODEL_CHAIN", ["big"])
    monkeypatch.setattr(llm, "SIMPLE_MODEL", "")
    assert llm.route_extraction("short") == ["big"]  # default: no behaviour change
    monkeypatch.setattr(llm, "SIMPLE_MODEL", "small")
    assert llm.route_extraction("short") == ["small", "big"]
    assert llm.route_extraction("x" * 5000) == ["big"]
