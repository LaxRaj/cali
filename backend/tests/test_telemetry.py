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
