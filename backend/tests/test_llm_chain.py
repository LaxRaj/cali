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


# --- multiple Groq keys ---------------------------------------------------------------------------------


class KeyClient:
    def __init__(self, outcome):
        self.outcome, self.calls = outcome, 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.calls += 1
        if isinstance(self.outcome, Exception):
            raise self.outcome
        msg = SimpleNamespace(content=json.dumps(REPLY))
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=None)


def test_second_key_takes_over_when_the_first_hits_its_daily_quota_and_stays_active():
    a, b = KeyClient(TPD), KeyClient("ok")
    multi = llm.MultiKeyGroq([a, b])
    assert extract("page", client=multi).startup.company_name == "Acme"
    assert extract("page", client=multi).startup.company_name == "Acme"
    assert (a.calls, b.calls) == (1, 2)  # the spent key is not retried on every call


def test_other_errors_are_not_masked_by_key_rotation_and_all_keys_spent_raises():
    with pytest.raises(RuntimeError, match="boom"):
        llm.MultiKeyGroq([KeyClient(RuntimeError("boom")), KeyClient("ok")]).create(model="m", messages=[])
    with pytest.raises(RuntimeError, match="TPD"):
        extract("page", client=llm.MultiKeyGroq([KeyClient(TPD), KeyClient(TPD)]))


def test_api_keys_are_read_in_order_and_blank_ones_ignored(monkeypatch):
    for n in ["GROQ_API_KEY"] + [f"GROQ_API_KEY_{i}" for i in range(2, 10)]:
        monkeypatch.delenv(n, raising=False)
    assert llm.api_keys() == []
    monkeypatch.setenv("GROQ_API_KEY", "k1")
    monkeypatch.setenv("GROQ_API_KEY_2", "  ")
    monkeypatch.setenv("GROQ_API_KEY_3", "k3")
    assert llm.api_keys() == ["k1", "k3"]
    assert type(llm.get_client()).__name__ == "MultiKeyGroq"
    assert llm.get_client() is llm.get_client()  # shared, so the 'active key' survives across calls
    monkeypatch.delenv("GROQ_API_KEY_3")
    assert type(llm.get_client()).__name__ == "Groq"  # a single key keeps the plain client
