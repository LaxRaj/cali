import json

import pytest

import telemetry
from telemetry import RunLog


def test_stage_records_timing_counts_and_order(tmp_path):
    log = RunLog()
    with log.stage("discover") as st:
        st["counts"] = {"candidates": 5}
    with log.stage("triage"):
        pass
    log.close()
    assert [s["name"] for s in log.stages] == ["discover", "triage"]
    assert log.stages[0]["counts"] == {"candidates": 5} and log.stages[0]["status"] == "ok"
    assert log.stages[0]["duration_s"] >= 0


def test_failing_stage_is_recorded_and_reraised():
    log = RunLog()
    with pytest.raises(ValueError):
        with log.stage("crawl"):
            raise ValueError("boom")
    log.close()
    assert log.stages[0]["status"] == "error"
    assert "boom" in log.errors[0]


def test_current_log_is_available_during_run_and_cleared_after():
    assert telemetry.current() is None
    log = RunLog()
    assert telemetry.current() is log
    log.close()
    assert telemetry.current() is None


def test_write_creates_run_file_and_rolling_index(tmp_path, monkeypatch):
    monkeypatch.setattr(telemetry, "MAX_INDEX", 3)
    ids = []
    for i in range(5):
        log = RunLog()
        log.run_id = f"2026010{i}T000000Z"  # distinct ids
        log.passed = i % 2 == 0
        log.source("hn", 4, 0.5)
        log.usage = {"total_tokens": 100 * i}
        log.write(tmp_path)
        log.close()
        ids.append(log.run_id)

    run = json.loads((tmp_path / "runs" / f"{ids[0]}.json").read_text())
    assert run["passed"] is True and run["source_health"]["hn"]["candidates"] == 4
    index = json.loads((tmp_path / "runs_index.json").read_text())["runs"]
    assert [r["run_id"] for r in index] == ids[-3:]  # capped, oldest dropped, sorted
    assert index[-1]["tokens"] == 400


def test_llm_usage_accumulates_and_tolerates_missing_usage():
    from types import SimpleNamespace

    import llm

    llm.reset_usage()
    llm.record_usage(SimpleNamespace(usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15)))
    llm.record_usage(SimpleNamespace())  # fakes without usage must not break
    assert llm.USAGE["total_tokens"] == 15 and llm.USAGE["calls"] == 2
    llm.reset_usage()
    assert llm.USAGE["total_tokens"] == 0


def _run(passed, quota=False, budget=0):
    log = RunLog()
    log.passed, log.quota_exhausted, log.token_budget = passed, quota, budget
    log.close()
    return log


def test_summary_status_distinguishes_quota_from_failure():
    assert _run(True).summary()["status"] == "passed"
    assert _run(False).summary()["status"] == "failed"
    assert _run(False, quota=True).summary()["status"] == "quota"
    assert _run(True, quota=True).summary()["status"] == "passed"  # finished fine despite touching the limit


def test_summary_carries_token_budget():
    assert _run(True, budget=400_000).summary()["token_budget"] == 400_000


def test_token_budget_scales_with_keys(monkeypatch):
    import llm

    for n in ["GROQ_API_KEY"] + [f"GROQ_API_KEY_{i}" for i in range(2, 10)]:
        monkeypatch.delenv(n, raising=False)
    assert llm.token_budget() == 200_000
    monkeypatch.setenv("GROQ_API_KEY", "a")
    monkeypatch.setenv("GROQ_API_KEY_2", "b")
    assert llm.token_budget() == 400_000


def test_backfill_index_adds_status_from_run_files(tmp_path):
    (tmp_path / "runs").mkdir()
    entries = [
        {"run_id": "a", "passed": True},
        {"run_id": "b", "passed": False},
        {"run_id": "c", "passed": False},
        {"run_id": "d", "passed": False, "status": "failed"},
    ]
    (tmp_path / "runs_index.json").write_text(json.dumps({"runs": entries}))
    (tmp_path / "runs" / "b.json").write_text(json.dumps({"quality": {"quota_exhausted": True}}))
    (tmp_path / "runs" / "c.json").write_text(json.dumps({"quality": {"quota_exhausted": False}}))
    assert telemetry.backfill_index(tmp_path) == 3
    got = {r["run_id"]: r["status"] for r in json.loads((tmp_path / "runs_index.json").read_text())["runs"]}
    assert got == {"a": "passed", "b": "quota", "c": "failed", "d": "failed"}
