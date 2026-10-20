import json

import pipeline
from decide.decisions import Gate
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
    monkeypatch.setenv("CALI_ENRICH", "0")  # no network in unit tests
    monkeypatch.setattr(pipeline, "gate_page", lambda md, *a, **k: Gate(True, 1.0))  # fake pages aren't real prose
    cands = [Candidate(f"https://{i}.com", "t", "s", sources[i]) for i in range(len(extractions))]

    async def fake_discover():
        return cands

    async def fake_scrape(urls):
        return [Page(u, "Acme page. Founded by Jane Roe in 2025.") for u in urls]

    it = iter(extractions)
    monkeypatch.setattr(pipeline, "discover", fake_discover)
    monkeypatch.setattr(pipeline, "select", lambda c, seen, caps=None, **kw: c)
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
    run = json.loads(next((tmp_path / "runs").glob("*.json")).read_text())
    assert [s["name"] for s in run["stages"]] == ["discover", "triage", "crawl", "extract", "gates", "store"]
    assert run["funnel"] == {"candidates": 4, "selected": 4, "crawled": 4, "extracted": 4, "relevant": 4, "valid": 4}
    assert len(run["accepted"]) == 4 and run["passed"] is True
    assert (tmp_path / "graph.json").exists() and (tmp_path / "profiles.json").exists()
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
    assert not (tmp_path / "daily_brief.json").exists()  # no bad data for CI to commit
    # ...but the failed run itself is logged so the dashboard can show it
    run = json.loads(next((tmp_path / "runs").glob("*.json")).read_text())
    assert run["passed"] is False and run["failures"] and len(run["rejections"]) == 5
    assert [s["name"] for s in run["stages"]][-1] == "gates"
    assert len(json.loads((tmp_path / "runs_index.json").read_text())["runs"]) == 1
    assert json.loads((tmp_path / "quality_report.json").read_text())["failures"]


async def test_hallucinated_evidence_is_counted_and_dropped(monkeypatch, tmp_path):
    exs = [make_extraction(f"Co{i}", quote="Founded by Someone Else") for i in range(3)]
    setup(monkeypatch, exs, ["hn", "rss", "yc"])
    report = await pipeline.run(tmp_path)

    assert report.valid == 3 and report.people == 0 and report.edges == 0
    assert report.dropped_ungrounded == 6


async def test_quota_exhaustion_stops_extracting_and_is_recorded(monkeypatch, tmp_path):
    setup(monkeypatch, [], [])
    cands = [Candidate(f"https://{i}.com", "t", "s", "hn") for i in range(5)]

    async def fake_discover():
        return cands

    calls = []

    def boom(md):
        calls.append(1)
        raise RuntimeError("Error code: 429 - Rate limit reached ... on tokens per day (TPD): Limit 200000")

    monkeypatch.setattr(pipeline, "discover", fake_discover)
    monkeypatch.setattr(pipeline, "extract", boom)
    report = await pipeline.run(tmp_path)

    assert len(calls) == 1  # first 429 (daily limit) ends extraction; no point hammering a dead quota
    assert report.quota_exhausted and not report.passed
    run = json.loads(next((tmp_path / "runs").glob("*.json")).read_text())
    assert len(run["rejections"]) == 5 and run["quality"]["quota_exhausted"] is True


async def test_inline_content_skips_crawl_and_enrichment_scores_and_exports_contacts(monkeypatch, tmp_path):
    from models import Contact, ContactItem

    exs = [make_extraction(f"Co{i}") for i in range(4)]
    setup(monkeypatch, exs, ["hn", "rss", "yc", "launch_hn"])
    monkeypatch.setenv("CALI_ENRICH", "1")
    crawled = []

    async def fake_discover():
        return [Candidate("https://0.com", "t", "s", "hn"), Candidate("https://1.com", "t", "s", "rss"),
                Candidate("https://2.com", "t", "s", "yc"),
                Candidate("https://news.ycombinator.com/item?id=9", "Launch HN: Co3", "s", "launch_hn", content="Founded by Jane Roe. We build.")]

    async def fake_scrape(urls):
        crawled.extend(urls)
        return [Page(u, "Acme page. Founded by Jane Roe in 2025.") for u in urls]

    async def fake_enrich(ex, source, md, **kw):
        c = Contact(website=f"https://{ex.startup.company_name.lower()}.io", status="ok",
                    emails=[ContactItem(value=f"hi@{ex.startup.company_name.lower()}.io", kind="general", source_url="u")])
        return pipeline.EnrichResult(ex, c, ["ok"])

    monkeypatch.setattr(pipeline, "discover", fake_discover)
    monkeypatch.setattr(pipeline, "scrape_urls", fake_scrape)
    monkeypatch.setattr(pipeline, "enrich_startup", fake_enrich)
    report = await pipeline.run(tmp_path)

    assert "https://news.ycombinator.com/item?id=9" not in crawled  # content was inline
    assert report.passed and report.valid == 4 and report.with_email == 4 and report.with_website == 4 and report.avg_score > 0
    brief = json.loads((tmp_path / "daily_brief.json").read_text())
    f = brief["findings"][0]
    assert f["contact"]["emails"][0]["value"].startswith("hi@") and "email" not in f["gaps"] and f["score"] > 0
    run = json.loads(next((tmp_path / "runs").glob("*.json")).read_text())
    assert "enrich" in [s["name"] for s in run["stages"]] and all("score" in a for a in run["accepted"])


async def test_gate_skips_extraction_for_non_startup_pages_and_logs_training_rows(monkeypatch, tmp_path):
    exs = [make_extraction("Real")]
    setup(monkeypatch, exs, ["rss"])
    cands = [Candidate("https://real.com", "Real raises seed", "s", "rss", triage=8.0),
             Candidate("https://guide.com", "10 best tools", "s", "web", triage=4.5)]

    async def fake_discover():
        return cands

    async def fake_scrape(urls):
        return [Page(u, "Acme page. Founded by Jane Roe in 2025.") for u in urls]

    extracted = []
    it = iter(exs)
    monkeypatch.setattr(pipeline, "discover", fake_discover)
    monkeypatch.setattr(pipeline, "scrape_urls", fake_scrape)
    monkeypatch.setattr(pipeline, "extract", lambda md: extracted.append(md) or next(it))
    monkeypatch.setattr(pipeline, "gate_page", lambda md, *a, **k: Gate(True, 0.9) if len(extracted) == 0 else Gate(False, 0.1))
    report = await pipeline.run(tmp_path)

    assert len(extracted) == 1 and report.gated == 1 and report.valid == 1  # the second page never reached the LLM
    run = json.loads(next((tmp_path / "runs").glob("*.json")).read_text())
    assert run["decisions"]["gated_pages"] == 1 and run["decisions"]["tokens_saved_est"] == 4500
    assert run["decisions"]["provider"] == "local" and "avg_latency_ms" in run["decisions"]
    rows = [json.loads(line) for line in (tmp_path / "decisions.jsonl").read_text().splitlines()]
    assert {(r["title"], r["outcome"]) for r in rows} == {("Real raises seed", "accepted"), ("10 best tools", "gated")}
    assert rows[0]["run_id"] == run["run_id"] and rows[0]["triage"] in (8.0, 4.5)


async def test_edgar_candidates_get_the_company_website_added_before_extraction_or_are_dropped(monkeypatch, tmp_path):
    setup(monkeypatch, [make_extraction("Nocturnal")], ["edgar"])
    good = Candidate("https://www.sec.gov/Archives/a/", "Nocturnal raises $1.85M (SEC Form D)", "s", "edgar", content="FILING FACTS", company="Nocturnal Inc.")
    lost = Candidate("https://www.sec.gov/Archives/b/", "Ghost raises $1M (SEC Form D)", "s", "edgar", content="FILING FACTS", company="Ghost LLC")

    async def fake_discover():
        return [good, lost]

    async def fake_materialize(cand, search_fn=None, fetch_fn=None):
        return "FILING FACTS\n\nWebsite: https://nocturnal.ai\n\nNocturnal builds things." if cand.company == "Nocturnal Inc." else None

    seen_md = []
    it = iter([make_extraction("Nocturnal")])
    monkeypatch.setattr(pipeline, "discover", fake_discover)
    monkeypatch.setattr(pipeline.edgar, "materialize", fake_materialize)
    monkeypatch.setattr(pipeline, "extract", lambda md: seen_md.append(md) or next(it))
    await pipeline.run(tmp_path)

    assert len(seen_md) == 1 and "Nocturnal builds things." in seen_md[0]  # the extractor saw the website text
    run = json.loads(next((tmp_path / "runs").glob("*.json")).read_text())
    assert [(r["source"], r["reasons"]) for r in run["rejections"]] == [("edgar", ["no company website found"])]
    rows = [json.loads(line) for line in (tmp_path / "decisions.jsonl").read_text().splitlines()]
    assert {(r["title"][:5], r["outcome"]) for r in rows} == {("Noctu", "accepted"), ("Ghost", "no_website")}
