import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from extractor import SYSTEM_PROMPT, extract
from llm import MODEL
from models import Extraction

DUMMY_MD = """# Acme Search: semantic search for legal docs
Acme Search launched on Show HN. Built with Python, Postgres and a React frontend.
Founded by Jane Roe. We index millions of contracts; customers complain keyword search misses clauses.
"""

FAKE_REPLY = {
    "startup": {
        "company_name": "Acme Search",
        "core_product": "Semantic search for legal documents.",
        "tech_stack": ["Python", "Postgres", "React"],
        "likely_bottleneck": "Keyword search over millions of contracts misses relevant clauses.",
        "value_prop_pitch": "Your Postgres keyword search misses clauses. I can ship a Next.js app backed by vector semantic search.",
        "is_relevant": True,
    },
    "people": [{"name": "Jane Roe", "role": "founder", "org": "Acme Search", "evidence": "Founded by Jane Roe"}],
    "edges": [{"src": "Jane Roe", "rel": "founded", "dst": "Acme Search", "evidence": "Founded by Jane Roe"}],
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


def test_extract_parses_startup_people_and_edges():
    client = FakeClient(json.dumps(FAKE_REPLY))
    ex = extract(DUMMY_MD, client=client)

    assert isinstance(ex, Extraction)
    assert ex.startup.company_name == "Acme Search"
    assert ex.startup.tech_stack == ["Python", "Postgres", "React"]
    assert ex.people[0].name == "Jane Roe"
    assert ex.edges[0].rel == "founded"

    call = client.calls[0]
    assert call["model"] == MODEL
    assert call["response_format"] == {"type": "json_object"}
    assert call["messages"][0]["content"] == SYSTEM_PROMPT
    assert call["messages"][1]["content"] == DUMMY_MD
    assert "Next.js" in SYSTEM_PROMPT and "verbatim" in SYSTEM_PROMPT


def test_malformed_output_is_rejected():
    bad = {**FAKE_REPLY, "edges": [{"src": "a", "rel": "married", "dst": "b", "evidence": "x"}]}
    with pytest.raises(ValidationError):
        extract(DUMMY_MD, client=FakeClient(json.dumps(bad)))
