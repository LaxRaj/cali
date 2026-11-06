"""Competitive features added 2026-11-06: lookalikes, change timeline, watchlist, site tech, run diff, digest/alerts,
per-key quota telemetry. All local and free."""

import json
from datetime import datetime, timedelta, timezone

import llm
import pipeline
from digest import alerts, weekly
from insights import _iso, load_watchlist, similar_companies, timeline, watch_hits
from techstack import detect
from tests.test_pipeline import make_extraction, setup

NOW = datetime(2026, 11, 6, 12, tzinfo=timezone.utc)


def test_similar_companies_uses_stored_vectors_and_excludes_self():
    rows = [{"company_name": "A", "vector": [1, 0, 0]}, {"company_name": "B", "vector": [0.9, 0.1, 0]},
            {"company_name": "C", "vector": [0, 0, 1]}]
    sim = similar_companies(rows, lambda n: n.lower())
    assert [s["company_name"] for s in sim["A"]] == ["B"]  # C is below the similarity floor
    assert sim["A"][0]["slug"] == "b" and 0.9 < sim["A"][0]["similarity"] <= 1
    assert similar_companies(rows[:1], str) == {}


def test_timeline_groups_facts_by_run_marks_discovery_and_normalises_feed_dates():
    tb = [
        {"entity_type": "startup", "field": "funding_stage", "value": "seed", "label": "", "source_url": "https://a/1",
         "run_id": "r1", "first_seen": "2026-10-01T00:00:00+00:00"},
        {"entity_type": "contact", "field": "email", "value": "hi@acme.io", "label": "", "source_url": "https://acme.io/",
         "run_id": "r2", "first_seen": "2026-10-09T00:00:00+00:00"},
    ]
    sig = [{"type": "funding", "url": "https://n/x", "posted_at": "Thu, 05 Nov 2026 11:50:53 +0000", "roles": []}]
    t = timeline(tb, sig)
    assert [e["kind"] for e in t] == ["funding", "learned", "discovered"]
    assert t[0]["at"] == "2026-11-05T11:50:53+00:00" and t[1]["items"] == ["Published email: hi@acme.io"]
    assert _iso("garbage") == "" and timeline([], [], "2026-10-01T00:00:00+00:00")[0]["kind"] == "discovered"


def test_watchlist(tmp_path):
    (tmp_path / "watchlist.json").write_text(json.dumps({"companies": ["Acme"], "keywords": ["vector search"]}))
    w = load_watchlist(tmp_path)
    assert watch_hits({"company_name": "acme", "core_product": "Vector search for law"}, w) == ["company", "keyword: vector search"]
    assert watch_hits({"company_name": "Other", "core_product": "vectors searched"}, w) == []
    assert load_watchlist(tmp_path / "missing") == {"companies": [], "keywords": []}


def test_site_tech_fingerprints():
    html = '<script src="/_next/static/chunks/main.js"></script><script src="https://js.stripe.com/v3"></script>' \
           '<script src="https://widget.intercom.io/widget/x"></script>'
    names = [t["name"] for t in detect([html])]
    assert names[:1] == ["Next.js"] and {"React", "Stripe", "Intercom"} <= set(names)
    assert detect(["<html>plain</html>"]) == []


async def test_run_diff_records_added_companies(monkeypatch, tmp_path):
    setup(monkeypatch, [make_extraction(f"Co{i}") for i in range(4)], ["hn", "rss", "yc", "hn"])
    await pipeline.run(tmp_path)
    run = json.loads(next((tmp_path / "runs").glob("*.json")).read_text())
    assert sorted(a["company"] for a in run["diff"]["added"]) == ["Co0", "Co1", "Co2", "Co3"] and run["diff"]["updated"] == []
    brief = json.loads((tmp_path / "daily_brief.json").read_text())
    assert "watchlist_hits" in brief and brief["diff"] == run["diff"]


def _index(tmp_path, runs):
    (tmp_path / "runs_index.json").write_text(json.dumps({"runs": runs}))


def test_alerts_fire_for_stale_data_and_two_quota_days_only(tmp_path):
    _index(tmp_path, [{"started_at": (NOW - timedelta(hours=2)).isoformat(), "status": "passed"}])
    assert alerts(tmp_path, NOW) == []
    _index(tmp_path, [{"started_at": (NOW - timedelta(hours=30)).isoformat(), "status": "passed"}])
    assert "Stale data" in alerts(tmp_path, NOW)[0]
    _index(tmp_path, [{"started_at": (NOW - timedelta(days=1)).isoformat(), "status": "quota"},
                      {"started_at": (NOW - timedelta(hours=1)).isoformat(), "status": "quota"}])
    assert any("quota" in a for a in alerts(tmp_path, NOW))


def test_weekly_digest_lists_new_strong_leads_and_contact_next(tmp_path, monkeypatch):
    monkeypatch.setenv("CALI_DASHBOARD_URL", "https://cali.example")
    _index(tmp_path, [{"started_at": (NOW - timedelta(hours=2)).isoformat(), "status": "passed", "tokens": 1000,
                       "funnel": {"valid": 2}}])
    profiles = [{"company_name": "Acme", "slug": "acme", "score": 88, "discovered_at": (NOW - timedelta(days=1)).isoformat(),
                 "core_product": "Search", "decision": {"action": "contact_now", "priority": 70, "next_step": "Email hi@acme.io"}}]
    (tmp_path / "profiles.json").write_text(json.dumps(profiles))
    md = weekly(tmp_path, NOW)
    assert "[Acme](https://cali.example/startups/acme) (88)" in md and "Email hi@acme.io" in md and "500 per startup" in md


def test_usage_report_tracks_model_key_and_quota_hits():
    llm.reset_usage()

    class Usage:
        prompt_tokens, completion_tokens, total_tokens = 10, 5, 15

    class Completion:
        usage = Usage()

    llm.record_usage(Completion(), "extract", model="m1", key="key2")
    llm.record_quota_hit(Exception("Rate limit reached ... tokens per day (TPD): Limit 200000, Used 198484, Requested 2100"), "key1", "m1")
    rep = llm.usage_report()
    assert rep["by_model"]["m1"]["total_tokens"] == 15 and rep["by_key"]["key2"]["calls"] == 1
    assert rep["quota_hits"][0] | {"at": ""} == {"key": "key1", "model": "m1", "limit": 200000, "used": 198484, "requested": 2100, "at": ""}
    llm.reset_usage()
