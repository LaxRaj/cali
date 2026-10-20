import json
import os
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from extractor import MODEL, SYSTEM_PROMPT, extract_profile
from models import StartupProfile

DUMMY_MD = """# Acme Search: semantic search for legal docs
Acme Search launched on Show HN. Built with Python, Postgres and a React frontend.
We index millions of contracts; customers complain keyword search misses relevant clauses.
"""

FAKE_REPLY = {
    "company_name": "Acme Search",
    "core_product": "Semantic search for legal documents.",
    "tech_stack": ["Python", "Postgres", "React"],
    "likely_bottleneck": "Keyword search over millions of contracts misses relevant clauses.",
    "value_prop_pitch": "Your Postgres keyword search misses clauses. I can ship a Next.js app backed by vector semantic search so lawyers find them instantly.",
    "is_relevant": True,
}


class FakeClient:
    def __init__(self, content: str):
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self._content = content

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        msg = SimpleNamespace(content=self._content)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def test_extract_profile_parses_into_model():
    client = FakeClient(json.dumps(FAKE_REPLY))
    profile = extract_profile(DUMMY_MD, client=client)

    assert isinstance(profile, StartupProfile)
    assert profile.company_name == "Acme Search"
    assert profile.tech_stack == ["Python", "Postgres", "React"]
    assert profile.is_relevant is True

    call = client.calls[0]
    assert call["model"] == MODEL
    assert call["response_format"] == {"type": "json_object"}
    assert call["messages"][0]["content"] == SYSTEM_PROMPT
    assert call["messages"][1]["content"] == DUMMY_MD
    assert "Next.js" in SYSTEM_PROMPT and "likely_bottleneck" in SYSTEM_PROMPT


def test_malformed_output_is_rejected():
    bad = {**FAKE_REPLY, "is_relevant": "maybe"}
    with pytest.raises(ValidationError):
        extract_profile(DUMMY_MD, client=FakeClient(json.dumps(bad)))


@pytest.mark.skipif(not os.environ.get("GROQ_API_KEY"), reason="GROQ_API_KEY not set")
def test_live_groq_extraction():
    profile = extract_profile(DUMMY_MD)
    assert profile.company_name
    assert isinstance(profile.is_relevant, bool)
