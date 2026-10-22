import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

import outreach
from outcomes import mark

CASES = json.loads((Path(__file__).parent / "fixtures" / "outreach_cases.json").read_text())
NOW = datetime(2026, 10, 20, 9, tzinfo=timezone.utc)


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_fold_matches_the_shared_contract(case):
    got = outreach.fold(case["events"], outreach.parse_time(case["now"]))
    assert {k: got[k] for k in case["expected"]} == case["expected"]


def test_new_event_validates_and_drops_empty_fields():
    e = outreach.new_event("Acme", "sent", NOW, subject="Hi", to="", note="")
    assert e["type"] == "sent" and e["subject"] == "Hi" and "to" not in e and "note" not in e and e["at"] == "2026-10-20T09:00:00+00:00"
    with pytest.raises(ValueError):
        outreach.new_event("Acme", "emailed")


def test_append_and_load_round_trip_and_skip_garbage(tmp_path):
    outreach.append(outreach.new_event("Acme", "sent", NOW, to="hi@acme.io", to_source_url="https://acme.io/contact"), tmp_path)
    with (tmp_path / outreach.FILE).open("a") as f:
        f.write("not json\n" + json.dumps({"id": "x", "company": "Acme", "type": "teleported", "at": NOW.isoformat()}) + "\n")
    events = outreach.load_events(tmp_path)
    assert len(events) == 1 and events[0]["to_source_url"] == "https://acme.io/contact"


def test_legacy_outcomes_are_read_as_events_and_union_with_the_log(tmp_path):
    mark("Acme", "contacted", "emailed", tmp_path, now=datetime(2026, 10, 1, 9, tzinfo=timezone.utc))
    outreach.append(outreach.new_event("Acme", "sent", datetime(2026, 10, 8, 9, tzinfo=timezone.utc)), tmp_path)
    state = outreach.fold(outreach.by_company(outreach.load_events(tmp_path))["acme"], NOW)
    assert state["status"] == "contacted" and state["touches"] == 2 and state["last_contact"] == "2026-10-08T09:00:00+00:00"
    mark("Acme", "passed", "", tmp_path, now=NOW, reason="wrong_stage")
    legacy = [e for e in outreach.load_events(tmp_path) if e["id"] == "legacy-acme-passed"][0]
    assert legacy["reason"] == "wrong_stage" and legacy["type"] == "passed"


def test_import_merges_dashboard_exports_without_duplicates(tmp_path):
    export = tmp_path / "export.json"
    ev = outreach.new_event("Acme", "replied", NOW)
    export.write_text(json.dumps({"events": [ev, {"id": "bad", "company": "Acme", "type": "nope", "at": NOW.isoformat()}]}))
    assert outreach.import_events(export, tmp_path) == 1
    assert outreach.import_events(export, tmp_path) == 0
    assert [e["id"] for e in outreach.load_events(tmp_path)] == [ev["id"]]
