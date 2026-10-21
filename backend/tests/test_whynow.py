from datetime import datetime, timezone

from whynow import why_now

NOW = datetime(2026, 10, 20, tzinfo=timezone.utc)


def test_fresh_form_d_is_a_signal():
    p = {"source_url": "https://www.sec.gov/Archives/x", "discovered_at": "2026-10-15T00:00:00+00:00", "funding_stage": "seed"}
    kinds = [s["signal"] for s in why_now(p, NOW)]
    assert kinds == ["form_d", "early_stage"]
    assert "5d ago" in why_now(p, NOW)[0]["text"]


def test_stale_lead_has_no_signals():
    p = {"source_url": "https://www.sec.gov/Archives/x", "discovered_at": "2026-08-01T00:00:00+00:00", "funding_stage": "seed"}
    assert why_now(p, NOW) == []


def test_bad_date_is_ignored():
    assert why_now({"source_url": "https://news.ycombinator.com/item?id=1", "discovered_at": "garbage"}, NOW) == []


def test_hn_post_is_a_signal():
    p = {"source_url": "https://news.ycombinator.com/item?id=1", "discovered_at": "2026-10-19T00:00:00Z"}
    assert [s["signal"] for s in why_now(p, NOW)] == ["hn"]
