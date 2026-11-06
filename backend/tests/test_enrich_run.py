import json

import enrich_run
import llm


async def boom(*a, **k):
    raise AssertionError("backfill must not run")


async def test_enrich_run_skips_when_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("CALI_ENRICH", "0")
    out = await enrich_run.run(tmp_path, backfill_fn=boom)
    assert out["skipped"] == "CALI_ENRICH=0" and not (tmp_path / enrich_run.LAST_RUN).exists()


async def test_enrich_run_skips_when_quota_spent(tmp_path, monkeypatch):
    monkeypatch.delenv("CALI_ENRICH", raising=False)
    monkeypatch.setattr(llm, "quota_blocked", lambda d: True)
    assert (await enrich_run.run(tmp_path, backfill_fn=boom))["skipped"] == "groq quota exhausted"


async def test_enrich_run_writes_last_run(tmp_path, monkeypatch):
    monkeypatch.delenv("CALI_ENRICH", raising=False)
    monkeypatch.setattr(llm, "quota_blocked", lambda d: False)
    seen = {}

    async def fake_backfill(data_dir, limit, search_fn, github_fn):
        seen.update(limit=limit, github=callable(github_fn))
        return [{"company": "Acme", "status": "ok"}]

    out = await enrich_run.run(tmp_path, limit=4, backfill_fn=fake_backfill)
    assert seen == {"limit": 4, "github": True} and out["startups"][0]["company"] == "Acme"
    assert json.loads((tmp_path / enrich_run.LAST_RUN).read_text())["startups"][0]["status"] == "ok"


def test_total_failure_needs_several_attempts_that_all_broke():
    broken = [{"status": "crawl_failed", "notes": []}, {"status": "ok", "notes": ["error: timeout"]}, {"status": "crawl_failed"}]
    assert enrich_run.total_failure({"startups": broken})
    assert not enrich_run.total_failure({"startups": broken[:2]})  # too few to call it broken
    assert not enrich_run.total_failure({"startups": broken + [{"status": "ok", "notes": []}]})


async def test_every_key_spent_mid_run_marks_the_quota(tmp_path, monkeypatch):
    monkeypatch.delenv("CALI_ENRICH", raising=False)
    monkeypatch.setattr(llm, "quota_blocked", lambda d: False)
    monkeypatch.setattr(llm, "api_keys", lambda: ["k1"])

    async def spending_backfill(data_dir, limit, search_fn, github_fn):
        llm.record_quota_hit(Exception("tokens per day (TPD): Limit 1, Used 1"), "key1", "m")
        return []

    out = await enrich_run.run(tmp_path, backfill_fn=spending_backfill)
    assert out["quota_exhausted"] and (tmp_path / llm.QUOTA_FILE).exists()
    llm.reset_usage()
