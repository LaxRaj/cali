"""Live evaluation of the extractor on golden pages. Run: uv run --env-file .env.local pytest -m live"""

import json
import os
from pathlib import Path

import pytest

from extractor import extract
from quality import check_extraction, grounded

FIX = Path(__file__).parent / "fixtures"
EXPECTED = json.loads((FIX / "expected.json").read_text())

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not os.environ.get("GROQ_API_KEY"), reason="GROQ_API_KEY not set"),
]


@pytest.fixture(scope="module")
def results():
    out = {}
    for name in EXPECTED:
        md = (FIX / f"{name}.md").read_text()
        out[name] = (md, check_extraction(extract(md), md))
    return out


def test_junk_pages_are_never_accepted(results):
    for name, exp in EXPECTED.items():
        if not exp["relevant"]:
            assert not results[name][1].accepted, f"{name} should be rejected"


def test_real_startups_are_accepted_with_correct_name(results):
    for name, exp in EXPECTED.items():
        if exp["relevant"]:
            checked = results[name][1]
            assert checked.accepted, f"{name}: {checked.issues}"
            assert exp["name"].lower() in checked.extraction.startup.company_name.lower()


def test_people_recall(results):
    expected = [(n, p) for n, e in EXPECTED.items() if e["relevant"] for p in e["people"]]
    found = 0
    for name, person in expected:
        names = [p.name.lower() for p in results[name][1].extraction.people]
        found += any(person.lower() in n or n in person.lower() for n in names)
    assert found / len(expected) >= 0.75, f"people recall {found}/{len(expected)}"


def test_founder_edges_extracted(results):
    for name, exp in EXPECTED.items():
        who = exp.get("founder_edge_for")
        if who:
            edges = results[name][1].extraction.edges
            assert any(e.rel in ("founded", "cofounded") and who.lower() in e.src.lower() for e in edges), name


def test_everything_kept_is_grounded(results):
    for md, checked in results.values():
        for p in checked.extraction.people:
            assert grounded(p.evidence, md)
        for e in checked.extraction.edges:
            assert grounded(e.evidence, md)
