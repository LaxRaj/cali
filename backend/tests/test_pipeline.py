import json

import pipeline
from discovery import Candidate
from models import Edge, Extraction, Person, StartupProfile
from scraper import Page

GOOD_PITCH = "Your search is slow. I can fix it with Next.js and vector semantic search."


def make_extraction(name, relevant=True, quote="Founded by Jane Roe"):
    return Extraction(
        startup=StartupProfile(company_name=name, core_product="Search", tech_stack=["Python"],
                               likely_bottleneck="Retrieval", value_prop_pitch=GOOD_PITCH, is_relevant=relevant),
        people=[Person(name="Jane Roe", role="founder", org=name, evidence=quote)],
        edges=[Edge(src="Jane Roe", rel="founded", dst=name, evidence=quote)],
    )


def setup(monkeypatch, extractions, sources):
    cands = [Candidate(f"https://{i}.com", "t", "s", sources[i]) for i in range(len(extractions))]

    async def fake_discover():
        return cands

    async def fake_scrape(urls):
        return [Page(u, "Acme page. Founded by Jane Roe in 2025.") for u in urls]

    it = iter(extractions)
    monkeypatch.setattr(pipeline, "discover", fake_discover)
    monkeypatch.setattr(pipeline, "select", lambda c, seen: c)
    monkeypatch.setattr(pipeline, "scrape_urls", fake_scrape)
    monkeypatch.setattr(pipeline, "extract", lambda md: next(it))
    monkeypatch.setattr(pipeline, "upsert_profile", lambda *a, **k: None)
    monkeypatch.setattr(pipeline, "upsert_people", lambda *a, **k: None)
    monkeypatch.setattr(pipeline, "upsert_edges", lambda *a, **k: None)
    monkeypatch.setattr(pipeline, "mark_seen", lambda *a, **k: None)


async def test_good_run_passes_and_exports_people_and_edges(monkeypatch, tmp_path):
    setup(monkeypatch, [make_extraction(f"Co{i}") for i in range(4)], ["hn", "rss", "yc", "hn"])
    report = await pipeline.run(tmp_path)

    assert report.passed and report.valid == 4 and report.people == 4 and report.edges == 4
    brief = json.loads((tmp_path / "daily_brief.json").read_text())
    assert len(brief["findings"]) == 4
    assert brief["findings"][0]["people"][0]["name"] == "Jane Roe"
    assert brief["findings"][0]["edges"][0]["rel"] == "founded"
    assert json.loads((tmp_path / "quality_report.json").read_text())["passed"] is True


async def test_junk_run_fails_gates_and_writes_no_data(monkeypatch, tmp_path):
    junk = [make_extraction(f"Co{i}", relevant=False) for i in range(5)]
    setup(monkeypatch, junk, ["hn"] * 5)
    report = await pipeline.run(tmp_path)

    assert not report.passed and report.valid == 0
    assert not (tmp_path / "daily_brief.json").exists()  # nothing for CI to commit
    assert json.loads((tmp_path / "quality_report.json").read_text())["failures"]


async def test_hallucinated_evidence_is_counted_and_dropped(monkeypatch, tmp_path):
    exs = [make_extraction(f"Co{i}", quote="Founded by Someone Else") for i in range(3)]
    setup(monkeypatch, exs, ["hn", "rss", "yc"])
    report = await pipeline.run(tmp_path)

    assert report.valid == 3 and report.people == 0 and report.edges == 0
    assert report.dropped_ungrounded == 6
