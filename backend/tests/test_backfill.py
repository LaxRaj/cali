import json

from backfill import backfill, needs_enrichment
from enrich import Fetched
from memory import _rows, TABLE, upsert_edges, upsert_people, upsert_profile
from models import Edge, Extraction, Person, StartupProfile
from scraper import Page


def prof(name, source_url, **kw):
    return StartupProfile(company_name=name, core_product="Semantic search for legal contracts and filings",
                          tech_stack=["Go"], likely_bottleneck="Keyword search misses clauses at scale",
                          value_prop_pitch="One. Two.", is_relevant=True, source_url=source_url,
                          discovered_at=kw.pop("discovered_at", "2026-10-19"), **kw)


HOME = '<html><body><a href="mailto:hello@acme.io">mail</a><a href="https://www.linkedin.com/company/acme-io">li</a></body></html>'


async def test_backfill_enriches_only_startups_without_contacts_and_keeps_existing_data(tmp_path):
    d = tmp_path / "db"
    upsert_profile(prof("Acme", "https://techcrunch.com/acme", discovered_at="2026-10-19"), db_dir=d)
    upsert_profile(prof("Done", "https://x.com/y", discovered_at="2026-10-18"), db_dir=d,
                   extras={"score": 90, "score_json": "{}", "contact_json": json.dumps({"status": "ok"})})
    upsert_people([Person(name="Jane Roe", role="CEO", org="Acme", evidence="Jane Roe is CEO of Acme")], db_dir=d)
    upsert_edges([Edge(src="Jane Roe", rel="founded", dst="Acme", evidence="Jane Roe founded Acme")], db_dir=d)
    assert [needs_enrichment(r) for r in sorted(_rows(TABLE, d), key=lambda r: r["company_name"])] == [True, False]

    scraped = []

    async def fake_scrape(urls):
        scraped.extend(urls)
        return [Page(urls[0], "Acme raised money. See [Acme](https://acme.io/). Jane Roe is CEO of Acme.")]

    async def fake_fetch(urls):
        return [Fetched(u, HOME, "") for u in urls if u in ("https://acme.io/",)]

    def fake_extract(md):
        raise AssertionError("no team page was found, so no LLM call is expected")

    out = await backfill(d, scrape_fn=fake_scrape, fetch_fn=fake_fetch, extract_fn=fake_extract)

    assert scraped == ["https://techcrunch.com/acme"]  # only the un-enriched startup was touched
    assert len(out) == 1 and out[0]["company"] == "Acme" and out[0]["website"] == "https://acme.io" and out[0]["emails"] == 1
    rows = {r["company_name"]: r for r in _rows(TABLE, d)}
    assert rows["Acme"]["website"] == "https://acme.io" and rows["Acme"]["score"] > 0
    assert json.loads(rows["Acme"]["contact_json"])["emails"][0]["value"] == "hello@acme.io"
    assert rows["Done"]["score"] == 90  # untouched
    profiles = {p["company_name"]: p for p in json.loads((d / "profiles.json").read_text())}
    assert profiles["Acme"]["people"][0]["name"] == "Jane Roe" and profiles["Acme"]["contact"]["status"] == "ok"
    assert await backfill(d, scrape_fn=fake_scrape, fetch_fn=fake_fetch) == []  # idempotent: nothing left to do
    assert not any(isinstance(x, Extraction) for x in out)


async def test_backfill_respects_limit_and_only_filter(tmp_path):
    d = tmp_path / "db"
    for i, n in enumerate(["A1", "B2", "C3"]):
        upsert_profile(prof(n, f"https://techcrunch.com/{n}", discovered_at=f"2026-10-1{i}"), db_dir=d)

    async def no_scrape(urls):
        return []

    async def no_fetch(urls):
        return []

    assert [r["company"] for r in await backfill(tmp_path / "db", limit=1, scrape_fn=no_scrape, fetch_fn=no_fetch)] == ["C3"]  # newest first
    only = await backfill(tmp_path / "db", only=["a1"], scrape_fn=no_scrape, fetch_fn=no_fetch)
    assert [r["company"] for r in only] == ["A1"] and only[0]["status"] == "no_website"


def _row(status="", attempts=0, last=""):
    return {"contact_json": json.dumps({"status": status, "attempts": attempts, "last_attempt": last})}


def test_needs_enrichment_caps_attempts_and_applies_cooldown():
    from datetime import datetime, timezone
    from backfill import MAX_ATTEMPTS

    now = datetime(2026, 10, 23, tzinfo=timezone.utc)
    assert needs_enrichment(_row("no_website", 1, "2026-10-19T00:00:00+00:00"), now)  # 4 days >= 3-day cooldown
    assert not needs_enrichment(_row("no_website", 1, "2026-10-22T00:00:00+00:00"), now)  # still cooling down
    assert not needs_enrichment(_row("crawl_failed", 2, "2026-10-19T00:00:00+00:00"), now)  # 2 attempts => 6 days
    assert not needs_enrichment(_row("crawl_failed", MAX_ATTEMPTS, "2026-01-01T00:00:00+00:00"), now)  # given up
    assert not needs_enrichment(_row("ok"), now)


async def test_backfill_counts_failed_attempts_and_prefers_fresh_rows(tmp_path):
    d = tmp_path / "db"
    upsert_profile(prof("Old", "https://techcrunch.com/old", discovered_at="2026-10-01"), db_dir=d)
    upsert_profile(prof("New", "https://techcrunch.com/new", discovered_at="2026-10-10"), db_dir=d)
    upsert_profile(prof("Dead", "https://techcrunch.com/dead", discovered_at="2026-10-20"), db_dir=d,
                   extras={"score": 1, "score_json": "{}", "contact_json": json.dumps(
                       {"status": "no_website", "attempts": 1, "last_attempt": "2026-01-01T00:00:00+00:00"})})

    async def no_scrape(urls):
        return []

    async def no_fetch(urls):
        return []

    out = await backfill(d, limit=2, scrape_fn=no_scrape, fetch_fn=no_fetch)
    assert [r["company"] for r in out] == ["New", "Old"]  # zero-attempt rows first, even though Dead is newest
    rows = {r["company_name"]: json.loads(r["contact_json"]) for r in _rows(TABLE, d)}
    assert rows["New"]["attempts"] == 1 and rows["New"]["last_attempt"] and rows["Dead"]["attempts"] == 1
