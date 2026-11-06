"""Regression tests for data-integrity bugs found in the 2026-11-06 QA, built from the real bad records."""

import json

import pytest

import pipeline
from backfill import backfill
from discovery import Candidate
from enrich import (
    PageFacts, _valid_email, build_contact, email_on_company_domain, host_matches_company, is_crawlable_host,
    post_emails, resolve_website,
)
from entities import normalize_stage
from memory import TABLE, _rows, upsert_profile
from models import StartupProfile
from scraper import scrape_urls


@pytest.mark.parametrize("host,company,ok", [
    ("acme.io", "Acme Search", True),
    ("getacme.com", "Acme", True),
    ("acme-search.dev", "Acme Search", True),
    ("jawbuddy.com", "JawBuddy", True),
    ("all-clad.com", "Clad", False),  # stored as Clad's site in production
    ("ventureburn.com", "Keenable", False),
    ("fortune.com", "Deeptune", False),
])
def test_host_matches_company(host, company, ok):
    assert host_matches_company(host, company) is ok


def test_publisher_article_is_never_the_company_site():
    # Keenable's and Deeptune's "websites" were the news articles that covered them
    assert resolve_website("Keenable", "", "https://ventureburn.com/keenable-raises-26-million/", "web", "") == ""
    assert resolve_website("Deeptune", "", "https://fortune.com/2026/03/19/deeptune-series-a/", "web", "") == ""
    # a product's own page still resolves
    assert resolve_website("Acme Search", "", "https://acme.io/launch", "hn", "") == "https://acme.io"


def test_job_boards_are_never_the_company_site():
    for url in ("https://tether.recruitee.com/o/eng-lead", "https://apply.workable.com/valis-insights-1/j/9D0C",
                "https://digikey.wd5.myworkdayjobs.com/en-US/x", "https://www.linkedin.com/jobs/view/4478769287/"):
        assert resolve_website("Tether", "", url, "hiring", "") == ""
        assert pipeline.lane_website("Tether", url) == ""
    assert pipeline.lane_website("Acme", "https://acme.io/jobs") == "https://acme.io/jobs"


def test_off_domain_and_template_emails_are_dropped():
    page = PageFacts(url="https://www.jawbuddy.com/privacy",
                     emails=[("info@jawbuddy.com", "general"), ("jawbuddy-dpo@chino.io", "person")])
    contact = build_contact("https://www.jawbuddy.com", [page], "JawBuddy")
    assert [e.value for e in contact.emails] == ["info@jawbuddy.com"]
    assert not _valid_email("jordan@yourcompany.com")
    assert email_on_company_domain("hi@acme.com", "https://acme.ai", "Acme")  # sister domain with the company's name
    assert not email_on_company_domain("nadine.ghosn@fortune.com", "", "Deeptune")


def test_hiring_post_emails_must_be_on_the_company_domain():
    text = "Apply: jobs@acme.io or ping our recruiter jane@talentagency.com"
    got = [e.value for e in post_emails(text, "https://news.ycombinator.com/item?id=1", "https://acme.io", "Acme")]
    assert got == ["jobs@acme.io"]


@pytest.mark.parametrize("raw,want", [
    ("pre‑Seed", "pre-seed"), ("Pre-seed", "pre-seed"), ("preseed", "pre-seed"), ("pre-Seed", "pre-seed"),
    ("seed-plus", "seed"), ("Seed", "seed"), ("Series A2", "Series A"), ("series b", "Series B"),
    ("Series D", "Series C+"), ("YC", "YC"), ("Y Combinator W26", "YC"), ("", ""), ("Grant-funded", "Grant-funded"),
])
def test_normalize_stage(raw, want):
    assert normalize_stage(raw) == want


def test_no_crawl_hosts():
    assert not is_crawlable_host("linkedin.com") and not is_crawlable_host("www.linkedin.com".removeprefix("www."))
    assert is_crawlable_host("acme.io")


async def test_scrape_urls_never_fetches_linkedin():
    # returns before a browser is ever started
    assert await scrape_urls(["https://www.linkedin.com/jobs/view/1/"]) == []


def _profile(name, **kw):
    return StartupProfile(company_name=name, core_product="Search infra for agents", tech_stack=[], likely_bottleneck="",
                          value_prop_pitch="", is_relevant=True, **kw)


def test_upsert_matches_canonical_name_and_normalises_stage(tmp_path):
    upsert_profile(_profile("Multikor", funding_stage="pre‑Seed", discovered_at="2026-10-01T00:00:00+00:00"), db_dir=tmp_path)
    upsert_profile(_profile("Multikor, Inc.", funding_stage="Seed", discovered_at="2026-11-01T00:00:00+00:00"), db_dir=tmp_path)
    rows = _rows(TABLE, tmp_path)
    assert len(rows) == 1
    assert rows[0]["company_name"] == "Multikor" and rows[0]["funding_stage"] == "seed"
    assert rows[0]["discovered_at"].startswith("2026-10-01")


async def test_backfill_never_recrawls_a_linkedin_source(tmp_path):
    upsert_profile(_profile("HiO", source_url="https://www.linkedin.com/jobs/view/4468585742/"), db_dir=tmp_path)
    scraped = []

    async def scrape_fn(urls):
        scraped.extend(urls)
        return []

    async def fetch_fn(urls):
        return []

    await backfill(tmp_path, limit=1, scrape_fn=scrape_fn, fetch_fn=fetch_fn, extract_fn=None, jobs_fn=None)
    assert scraped == []


async def test_known_company_in_hiring_lane_is_refreshed_not_re_enriched(monkeypatch, tmp_path):
    upsert_profile(_profile("Opsfleet"), db_dir=tmp_path,
                   extras={"contact_json": json.dumps({"status": "no_website", "attempts": 2}), "signals_json": "[]"})
    post = Candidate("https://www.linkedin.com/jobs/view/4478769287/", "Opsfleet is hiring", "Opsfleet | DevOps | Remote",
                     "hiring", company="Opsfleet", published_at="2026-11-01T00:00:00Z", content="# Opsfleet hiring post",
                     meta={"roles": "DevOps Engineer", "item_id": "77", "text": "Opsfleet builds cloud ops tooling " * 3,
                           "website": "https://www.linkedin.com/jobs/view/4478769287/"})

    async def fake_discover():
        return [post]

    seen: list[str] = []
    monkeypatch.setenv("CALI_ENRICH", "0")
    monkeypatch.setattr(pipeline, "discover", fake_discover)
    monkeypatch.setattr(pipeline, "select", lambda c, seen, caps=None, **kw: [])
    monkeypatch.setattr(pipeline, "mark_seen", lambda urls, db_dir=None: seen.extend(urls))
    report = await pipeline.run(tmp_path)

    assert report.valid == 0  # not re-accepted, so it is not re-enriched or re-labelled
    row = _rows(TABLE, tmp_path)[0]
    assert json.loads(row["contact_json"])["attempts"] == 2  # the retry counter survives
    sig = json.loads(row["signals_json"])
    assert sig and sig[0]["url"] == "https://news.ycombinator.com/item?id=77"
    assert any("linkedin.com/jobs/view/4478769287" in u for u in seen)


async def test_hiring_lane_uses_the_hn_post_as_source_and_drops_job_board_websites(monkeypatch, tmp_path):
    post = Candidate("https://apply.workable.com/valis-insights-1/j/9D0C", "VALIS is hiring", "VALIS | ML | Remote",
                     "hiring", company="VALIS", published_at="2026-11-01T00:00:00Z", content="# VALIS hiring post",
                     meta={"roles": "ML Engineer", "item_id": "88", "text": "VALIS builds clinical insight tooling for hospitals.",
                           "website": "https://apply.workable.com/valis-insights-1/j/9D0C"})

    async def fake_discover():
        return [post]

    monkeypatch.setenv("CALI_ENRICH", "0")
    monkeypatch.setattr(pipeline, "discover", fake_discover)
    monkeypatch.setattr(pipeline, "select", lambda c, seen, caps=None, **kw: [])
    stored = []
    monkeypatch.setattr(pipeline, "upsert_profile", lambda s, **k: stored.append(s))
    await pipeline.run(tmp_path)
    decisions = [json.loads(x) for x in (tmp_path / "decisions.jsonl").read_text().splitlines() if x.strip()]
    rows = [r for r in decisions if r.get("source") == "hiring"]
    assert rows and all(r.get("lane") for r in rows)
    brief = tmp_path / "daily_brief.json"
    for s in stored:
        assert s.source_url == "https://news.ycombinator.com/item?id=88" and s.website == ""
    if brief.exists():
        for f in json.loads(brief.read_text())["findings"]:
            assert "workable.com" not in f["website"]


@pytest.mark.parametrize("addr,site,company,ok", [
    ("founders@lmnr.ai", "https://laminar.sh", "Laminar", True),  # abbreviated domain, published on its own site
    ("founders@prbe.ai", "https://www.useprobe.ai", "Probe", True),
    ("hi@quiver.ai", "", "QuiverAI", True),
    ("hello@vaeridion.com", "", "VÆRIDION", True),
    ("priya@spotify.com", "https://dorislabs.com", "Doris Labs", False),  # example addresses in page copy
    ("mhaffey@tripleaimbenefits.com", "https://www.atlis.health", "Atlis Health, LLC", False),
])
def test_company_domain_variants(addr, site, company, ok):
    assert email_on_company_domain(addr, site, company) is ok


def test_repair_row_fixes_publisher_site_and_off_domain_emails_and_stage():
    from repair import repair_row

    row = {
        "company_name": "Keenable", "core_product": "Search index for AI agents", "tech_stack": [], "likely_bottleneck": "",
        "value_prop_pitch": "", "is_relevant": True, "funding_stage": "pre‑Seed",
        "source_url": "https://ventureburn.com/keenable-raises/", "website": "https://ventureburn.com", "score": 40, "score_json": "{}",
        "contact_json": json.dumps({"website": "https://ventureburn.com", "status": "ok",
                                    "emails": [{"value": "contact@ventureburn.com", "kind": "general",
                                                "source_url": "https://ventureburn.com/"}]}),
    }
    upd, notes = repair_row(row, [], [], [row])
    assert upd["website"] == "" and upd["funding_stage"] == "pre-seed"
    contact = json.loads(upd["contact_json"])
    assert contact["emails"] == [] and contact["status"] == "" and contact["attempts"] == 0  # re-enters the backlog
    assert "axes" in json.loads(upd["score_json"])
    again, _ = repair_row({**row, **upd}, [], [], [row])  # idempotent
    assert again == {}


def test_dedupe_decisions_keeps_latest_row_per_url(tmp_path):
    from repair import dedupe_decisions

    rows = [{"url": "a", "outcome": "accepted", "n": 1}, {"url": "b", "outcome": "rejected"}, {"url": "a", "outcome": "accepted", "n": 2}]
    (tmp_path / "decisions.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    assert dedupe_decisions(tmp_path, dry_run=False) == (3, 2)
    out = [json.loads(x) for x in (tmp_path / "decisions.jsonl").read_text().splitlines()]
    assert [(r["url"], r.get("n")) for r in out] == [("b", None), ("a", 2)]
