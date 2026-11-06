import json
from types import SimpleNamespace

import pytest

import draft_llm
import llm
from draft import OPT_OUT


class FakeGroq:
    """Stands in for the Groq client: returns whatever JSON it was given (or raises)."""

    def __init__(self, payload=None, error=None):
        self.payload, self.error = payload, error
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        if self.error:
            raise self.error
        msg = SimpleNamespace(content=json.dumps(self.payload))
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15))


PROFILE = {"company_name": "Acme", "core_product": "Semantic search for contracts.", "likely_bottleneck": "Keyword search misses clauses."}
ITEM = {"company": "Acme", "kind": "first", "subject": "Quick call about Acme?", "body": f"Hi Ada,\n\nLong text here.\n\n{OPT_OUT}\n\nSam"}


def test_polish_returns_a_clean_observation_and_subject():
    got = draft_llm.polish(PROFILE, FakeGroq({"observation": "Acme makes contract search work at scale; keyword search misses clauses.", "subject": "Contract search at scale"}))
    assert got == {"observation": "Acme makes contract search work at scale; keyword search misses clauses.", "subject": "Contract search at scale"}


@pytest.mark.parametrize("bad", [
    {"observation": "", "subject": "x"},
    {"observation": "Great! Wow!", "subject": "x"},
    {"observation": "See [placeholder]", "subject": "x"},
    {"observation": "Visit https://acme.io now", "subject": "x"},
    {"observation": "word " * 50, "subject": "x"},
    {"observation": "fine sentence", "subject": "one two three four five six seven eight nine"},
])
def test_polish_rejects_unusable_model_output(bad):
    assert draft_llm.polish(PROFILE, FakeGroq(bad)) is None


def test_polish_falls_back_when_the_call_fails_or_there_is_no_key(monkeypatch):
    assert draft_llm.polish(PROFILE, FakeGroq(error=TimeoutError("down"))) is None
    monkeypatch.setattr(llm, "api_keys", lambda: [])
    assert draft_llm.polish(PROFILE) is None and not draft_llm.available()


def test_revise_applies_feedback_and_returns_the_new_text():
    new = {"subject": "Acme + me", "body": f"Hi Ada,\n\nShorter.\n\n{OPT_OUT}\n\nSam"}
    assert draft_llm.revise(ITEM, "shorter", FakeGroq(new)) == new


def test_revise_discards_rewrites_that_break_the_rules():
    with pytest.raises(ValueError, match="opt-out"):
        draft_llm.revise(ITEM, "shorter", FakeGroq({"subject": "s", "body": "Hi Ada, short."}))
    with pytest.raises(ValueError, match="breaks a rule"):
        draft_llm.revise(ITEM, "x", FakeGroq({"subject": "s", "body": f"Hi, it's FREE!!\n{OPT_OUT}"}))
    with pytest.raises(ValueError, match="empty"):
        draft_llm.revise(ITEM, "x", FakeGroq({"subject": "", "body": ""}))
    with pytest.raises(ValueError, match="rewrite failed"):
        draft_llm.revise(ITEM, "x", FakeGroq(error=TimeoutError("down")))


def test_revise_without_a_key_says_so(monkeypatch):
    monkeypatch.setattr(llm, "api_keys", lambda: [])
    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        draft_llm.revise(ITEM, "shorter")
