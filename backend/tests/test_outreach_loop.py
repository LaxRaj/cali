"""The closed outreach loop added on 2026-11-06: reply intent, skipped retries, crash recovery, unified breaker, local
follow-ups, setup checks, the dashboard summary, and decider labels from real outcomes. Nothing is ever sent."""

import json
from datetime import datetime, timedelta, timezone

import pytest

import gmail_sync
import outreach
from decide.training import labelled, outcome_labels
from draft import OPT_OUT, build_draft
from outcomes import mark

NOW = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)  # a Tuesday, inside the send window


def lead(name="Acme", domain="acme.io", score=80, body_extra=""):
    body = f"Hi {name} team,\n\nOne thing I noticed: slow joins.{body_extra}\n\n{OPT_OUT}\n\nSam"
    return {
        "company_name": name, "score": score, "likely_bottleneck": "slow joins", "tech_stack": ["Rust"],
        "decision": {"action": "contact_now", "priority": 50, "score": score},
        "email_draft": {"to": f"hi@{domain}", "to_source_url": f"https://{domain}/", "subject": f"{name}: slow joins",
                        "body": body, "intent": "build_for", "intent_reason": "r"},
    }


@pytest.mark.parametrize("text,intent", [
    ("I am out of the office until Monday with limited access to email.", "ooo"),
    ("Automatic reply: thanks for your message", "ooo"),
    ("This is not spam, just checking: can you send more details?", "interested"),
    ("Please stop spamming me", "complaint"),
    ("Not right now, maybe next quarter.", "not_now"),
    ("I'm not the right person, reach out to jane@acme.io", "referral"),
    ("Sounds interesting, let's chat Thursday", "interested"),
    ("Please remove me from your list", "unsubscribe"),
    ("What would that cost?", "question"),
])
def test_classify_reply(text, intent):
    assert gmail_sync.classify_reply(text) == intent


def test_out_of_office_is_not_a_reply():
    me = {"labelIds": ["SENT"], "from": "me@x.io", "snippet": "hi"}
    ooo = {"labelIds": ["INBOX"], "from": "a@acme.io", "snippet": "Out of office until Nov 12"}
    assert gmail_sync.classify([me, ooo]) == ("sent", "")
    later = {"labelIds": ["INBOX"], "from": "a@acme.io", "snippet": "Back now. Sounds good, let's talk"}
    assert gmail_sync.classify([me, ooo, later]) == ("replied", "interested")


def test_a_later_opt_out_on_a_replied_thread_still_suppresses(tmp_path):
    outreach.queue_from_profiles([lead()], tmp_path, NOW)
    outreach.set_status("Acme", "first", "sent", tmp_path, NOW, gmail_thread_id="t1")
    outreach.set_status("Acme", "first", "replied", tmp_path, NOW, reply_intent="interested")

    class Svc:
        def users(self):
            return self

        def threads(self):
            return self

        def get(self, **kw):
            class R:
                def execute(self):
                    return {"messages": [{"labelIds": ["SENT"], "snippet": "hi", "payload": {"headers": []}},
                                         {"labelIds": ["INBOX"], "snippet": "Actually please remove me", "payload": {"headers": [{"name": "From", "value": "a@acme.io"}]}}]}
            return R()

    gmail_sync.sync(tmp_path, svc=Svc())
    assert outreach.load_outbox(tmp_path)["acme::first"]["status"] == "opted_out"
    assert "hi@acme.io" in outreach.load_suppressed(tmp_path)


def test_skipped_draft_is_retried_only_when_it_changed_and_never_blocks_the_domain(tmp_path):
    outreach.queue_from_profiles([lead(score=60)], tmp_path, NOW)
    outreach.set_status("Acme", "first", "skipped", tmp_path, NOW, skip_reason="score 60 < 70")
    assert outreach.queue_from_profiles([lead(score=60)], tmp_path, NOW) == []  # same draft: stays skipped
    again = outreach.queue_from_profiles([lead(score=82)], tmp_path, NOW)  # rescored: worth another look
    assert [i["company"] for i in again] == ["Acme"] and outreach.load_outbox(tmp_path)["acme::first"]["status"] == "queued"
    # a skipped draft (never sent) does not use up a domain's cooldown
    d2 = tmp_path / "d2"
    outreach.queue_from_profiles([lead("Acme", "shared.io", score=60)], d2, NOW)
    outreach.set_status("Acme", "first", "skipped", d2, NOW)
    assert [i["company"] for i in outreach.queue_from_profiles([lead("Acme Labs", "shared.io")], d2, NOW)] == ["Acme Labs"]


def test_a_send_stuck_mid_flight_becomes_an_error_trips_the_breaker_and_needs_resolving(tmp_path):
    outreach.queue_from_profiles([lead()], tmp_path, NOW)
    outreach.set_status("Acme", "first", "sending", tmp_path, NOW - timedelta(hours=2))
    stuck = outreach.recover_stuck(tmp_path, NOW)
    assert [i["status"] for i in stuck] == ["error"]
    reason = outreach.breaker_reason(outreach.load_outbox(tmp_path))
    assert "unknown result" in reason
    assert outreach.run(tmp_path, NOW, svc=object.__new__(object)).startswith("paused")
    with pytest.raises(ValueError):
        outreach.resolve("Acme", "first", "maybe", tmp_path)
    outreach.resolve("Acme", "first", "skipped", tmp_path)
    outreach.set_paused(False, data_dir=tmp_path, now=NOW + timedelta(minutes=1))
    assert outreach.breaker_reason(outreach.load_outbox(tmp_path), outreach.load_state(tmp_path)["resumed_at"]) == ""


def test_resume_is_not_undone_by_the_bounces_it_acknowledged(tmp_path):
    for n in range(3):
        outreach.queue_from_profiles([lead(f"C{n}", f"c{n}.io")], tmp_path, NOW)
        outreach.set_status(f"C{n}", "first", "sent", tmp_path, NOW)
        outreach.set_status(f"C{n}", "first", "bounced", tmp_path, NOW)
    assert outreach.breaker_tripped(outreach.load_outbox(tmp_path))
    outreach.set_paused(False, data_dir=tmp_path, now=NOW + timedelta(minutes=5))
    assert outreach.breaker_reason(outreach.load_outbox(tmp_path), outreach.load_state(tmp_path)["resumed_at"]) == ""


def test_follow_up_becomes_due_locally_without_a_commit_round_trip(tmp_path):
    p = {**lead(), "decision": {"action": "watch", "priority": 10}, "discovered_at": (NOW - timedelta(days=3)).isoformat(),
         "outcome": None}
    mark("Acme", "contacted", "", tmp_path, NOW - timedelta(days=8))
    [d] = outreach.with_local_decisions([p], tmp_path, NOW)
    assert d["decision"]["action"] == "follow_up" and d["outcome"]["status"] == "contacted"


def test_drafts_with_nothing_specific_need_a_human_and_the_gate_blocks_them():
    thin = {"company_name": "Blank", "core_product": "An app.", "people": [], "contact": {"emails": []}}
    d = build_draft(thin, sender={"name": "Sam", "bio": "", "links": ""})
    assert d["needs_human"] and "[" not in d["body"]
    assert "draft needs a human" in "; ".join(outreach.gate({"score": 90, "specific": True, "needs_human": True}))


def test_drafts_never_address_publisher_or_off_domain_inboxes():
    p = {"company_name": "Deeptune", "website": "https://fortune.com", "source_url": "https://fortune.com/2026/03/19/x",
         "core_product": "Voice AI.", "people": [], "likely_bottleneck": "latency",
         "contact": {"emails": [{"value": "nadine.ghosn@fortune.com", "kind": "person", "source_url": "https://fortune.com/x"}]}}
    assert build_draft(p, sender={"name": "Sam", "bio": "", "links": ""})["to"] == ""


def test_doctor_reports_sender_switches_and_dns(tmp_path):
    outreach.init_sender(tmp_path, "Sam Doe", "sam@samdoe.dev")
    records = {"samdoe.dev": ["v=spf1 include:_spf.google.com ~all"], "_dmarc.samdoe.dev": []}
    checks = {c: (ok, d) for c, ok, d in outreach.doctor(tmp_path, NOW, resolver=lambda n: records[n], config_dir=tmp_path)}
    assert checks["sender"] == (True, "Sam Doe")
    assert checks["spf"][0] and not checks["dmarc"][0]
    assert not checks["gmail token"][0]
    with pytest.raises(ValueError):
        outreach.init_sender(tmp_path, "  ")
    assert outreach.dns_checks("gmail.com", resolver=lambda n: 1 / 0)[0][1] is True  # managed by Google, no lookup


def test_summary_is_address_free(tmp_path):
    outreach.queue_from_profiles([lead(), lead("Beta", "beta.io")], tmp_path, NOW)
    outreach.set_status("Acme", "first", "sent", tmp_path, NOW)
    outreach.set_status("Acme", "first", "replied", tmp_path, NOW, reply_intent="interested")
    s = outreach.summary(tmp_path, NOW)
    assert s["sent"] == 1 and s["replied"] == 1 and s["reply_rate"] == 1.0 and s["reply_intents"] == {"interested": 1}
    raw = (tmp_path / "outreach_summary.json").read_text()
    assert "@" not in raw and "slow joins" not in raw


def test_decider_labels_skip_hiring_lane_rows_and_dedupe_and_learn_from_outcomes():
    rows = [
        {"url": "a", "title": "Acme raises seed", "source": "rss", "outcome": "rejected"},
        {"url": "a", "title": "Acme raises seed", "source": "rss", "outcome": "accepted"},  # latest wins
        {"url": "h", "title": "Opsfleet is hiring", "source": "hiring", "outcome": "accepted", "lane": True},
    ]
    assert [lab for _, lab in labelled(rows)] == [1]
    profiles = [{"company_name": n, "core_product": f"{n} builds search", "likely_bottleneck": "slow joins"} for n in ("A", "B", "C", "D")]
    outcomes = {"a": {"status": "replied"}, "b": {"status": "passed", "reason": "wrong_stage"},
                "c": {"status": "passed", "reason": "no_contact"}, "d": {"status": "contacted"}}
    assert sorted(lab for _, lab in outcome_labels(profiles, outcomes)) == [0, 1]


def test_cli_init_writes_me_json(tmp_path, monkeypatch):
    import sys

    monkeypatch.setattr(sys, "argv", ["outreach.py", "--data-dir", str(tmp_path), "init", "--name", "Sam", "--email", "s@x.dev",
                                      "--bio", "b", "--links", "l"])
    outreach.main()
    assert json.loads((tmp_path / "me.json").read_text())["name"] == "Sam"
