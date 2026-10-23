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
