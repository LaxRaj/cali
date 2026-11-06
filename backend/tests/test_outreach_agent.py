"""Sending: only approved emails go out; ramp, window, lint, circuit breaker, idempotency. Gmail is faked, time is injected."""

import base64
import json
import random
from datetime import datetime, timedelta, timezone
from email import message_from_bytes

import pytest

import outreach
from draft import OPT_OUT
from outcomes import load_outcomes

NOW = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)  # a Tuesday, inside the send window


def strong(name, domain, score=80, action="contact_now", priority=50):
    body = f"Hi {name} team,\n\nI came across {name}.\nOne thing I noticed: slow joins.\n\n{OPT_OUT}\n\nSam"
    return {
        "company_name": name,
        "score": score,
        "likely_bottleneck": "slow joins",
        "tech_stack": ["Rust"],
        "decision": {"action": action, "priority": priority, "reasons": ["lead score 80"]},
        "email_draft": {
            "to": f"hi@{domain}",
            "to_source_url": f"https://{domain}/",
            "subject": f"{name}: a thought on slow joins",
            "body": body,
            "intent": "build_for",
            "intent_reason": "r",
        },
    }


class Mail:
    """Just enough Gmail API: records sends, can fail, and serves a configurable thread."""

    def __init__(self, fail=False):
        self.sent, self.fail, self.thread_messages, self.n = [], fail, [], 0

    def users(self):
        return self

    def messages(self):
        return self

    def threads(self):
        return self

    def drafts(self):
        return self

    def getProfile(self, userId):
        return self._done({"emailAddress": "me@x.io"})

    def send(self, userId, body):
        if self.fail:
            raise TimeoutError("boom")
        self.n += 1
        self.sent.append(body)
        return self._done({"id": f"m{self.n}", "threadId": f"t{self.n}"})

    def get(self, **kw):
        if kw.get("metadataHeaders") == ["Message-Id"]:
            return self._done({"payload": {"headers": [{"name": "Message-Id", "value": "<first@x>"}]}})
        return self._done({"messages": self.thread_messages})

    def create(self, userId, body):
        return self._done({"id": "d1", "message": {"threadId": "t1"}})

    @staticmethod
    def _done(v):
        class R:
            def execute(self):
                return v

        return R()


def approve_all(d):
    for i in outreach.load_outbox(d).values():
        if i["status"] == "queued":
            outreach.approve(i["company"], i["kind"], d, NOW)


@pytest.fixture
def agent(tmp_path, monkeypatch):
    monkeypatch.setenv("CALI_OUTREACH_SEND", "1")
    for k in ("CALI_OUTREACH", "CALI_SENDER_NAME", "CALI_OUTREACH_DAILY_CAP"):
        monkeypatch.delenv(k, raising=False)
    (tmp_path / "me.json").write_text(json.dumps({"name": "Sam"}))

    def setup(*profiles, approve=True):
        (tmp_path / "profiles.json").write_text(json.dumps(list(profiles)))
        outreach.queue_from_profiles(list(profiles), tmp_path, NOW)
        if approve:
            approve_all(tmp_path)
        return tmp_path

    return setup


def decoded(body):
    return message_from_bytes(base64.urlsafe_b64decode(body["raw"]))


def test_lint_flags_bulk_looking_mail():
    ok = {"company": "Acme", "kind": "first", "subject": "Acme: a thought", "body": f"Hi,\nshort note.\n{OPT_OUT}"}
    assert outreach.lint(ok) == []
    assert "spam phrase" in outreach.lint({**ok, "body": ok["body"] + " It's free"})
    assert "ALL CAPS word" in outreach.lint({**ok, "body": ok["body"] + " URGENT"})
    assert outreach.lint({**ok, "company": "VOYGR", "body": ok["body"] + " VOYGR"}) == []  # a company's own name is fine
    assert "over 120 words" in outreach.lint({**ok, "body": ok["body"] + " word" * 130})
    assert "more than one link" in outreach.lint({**ok, "body": ok["body"] + " https://a.io https://b.io"})
    assert "unfilled [placeholder]" in outreach.lint({**ok, "body": ok["body"] + " [after trying it: one specific observation]"})[0]
    assert "HTML in body" in outreach.lint({**ok, "body": ok["body"] + "<b>hi</b>"})
    assert "too many exclamation marks" in outreach.lint({**ok, "body": ok["body"] + " wow! great!"})
    assert "missing opt-out line" in outreach.lint({**ok, "body": "Hi"})


def test_ramp_window_and_gate():
    assert outreach.ramp_cap({}, NOW) == 3
    assert outreach.ramp_cap({"a": {"sent_at": (NOW - timedelta(days=2)).isoformat()}}, NOW) == 7
    assert outreach.ramp_cap({"a": {"sent_at": (NOW - timedelta(days=60)).isoformat()}}, NOW) == outreach.DAILY_CAP
    assert outreach.in_send_window(NOW)
    assert not outreach.in_send_window(NOW.replace(day=18))  # Sunday
    assert not outreach.in_send_window(NOW.replace(hour=8)) and not outreach.in_send_window(NOW.replace(hour=16))
    assert outreach.gate({"score": 80, "specific": True}) == []
    assert len(outreach.gate({"score": 60, "specific": False})) == 2


def test_run_never_sends_an_email_you_have_not_approved(agent):
    d = agent(strong("A", "a.io"), approve=False)
    mail = Mail()
    out = outreach.run(d, NOW, svc=mail)
    assert out.startswith("nothing approved to send (1 waiting for your review") and mail.sent == []
    assert outreach.load_outbox(d)["a::first"]["status"] == "queued"


def test_run_sends_one_approved_plain_text_email_then_waits_a_random_gap(agent):
    d = agent(strong("A", "a.io", priority=9), strong("B", "b.io", priority=1))
    mail, rng = Mail(), random.Random(1)
    assert outreach.run(d, NOW, svc=mail, rng=rng) == "sent to hi@a.io (A, first)"
    msg = decoded(mail.sent[0])
    assert msg["To"] == "hi@a.io" and msg["From"] == "me@x.io" and msg["List-Unsubscribe"] == "<mailto:me@x.io?subject=unsubscribe>"
    assert msg.get_content_type() == "text/plain" and not msg.is_multipart()
    item = outreach.load_outbox(d)["a::first"]
    assert item["status"] == "sent" and item["gmail_thread_id"] == "t1" and item["sent_at"]
    assert load_outcomes(d)["a"]["status"] == "contacted"
    assert outreach.run(d, NOW + timedelta(minutes=1), svc=mail, rng=rng).startswith("waiting until")
    assert len(mail.sent) == 1
    assert outreach.run(d, NOW + timedelta(minutes=16), svc=mail, rng=rng) == "sent to hi@b.io (B, first)"


def test_the_approved_text_is_what_is_sent_including_your_edits(agent):
    d = agent(strong("A", "a.io"), approve=False)
    outreach.update_item("A", "first", d, NOW, body=f"Hi A,\n\nMy own words.\n\n{OPT_OUT}\n\nSam")
    outreach.approve("A", "first", d, NOW)
    mail = Mail()
    outreach.run(d, NOW, svc=mail)
    assert "My own words." in decoded(mail.sent[0]).get_payload(decode=True).decode()


def test_ramp_stops_after_three_on_the_first_day(agent):
    d = agent(*[strong(f"C{i}", f"c{i}.io", priority=i) for i in range(5)])
    mail, t = Mail(), NOW
    for _ in range(3):
        assert outreach.run(d, t, svc=mail, rng=random.Random(0)).startswith("sent to")
        t += timedelta(minutes=20)
    assert outreach.run(d, t, svc=mail) == "today's ramp cap reached (3)"
    assert len(mail.sent) == 3


def test_no_send_flag_means_drafts_only(agent, monkeypatch):
    d = agent(strong("A", "a.io"))
    monkeypatch.delenv("CALI_OUTREACH_SEND")
    mail = Mail()
    assert "drafts only" in outreach.run(d, NOW, svc=mail) and mail.sent == []


def test_outside_window_and_unsigned_do_not_send(agent):
    d = agent(strong("A", "a.io"))
    mail = Mail()
    assert outreach.run(d, NOW.replace(day=18), svc=mail).startswith("outside the send window")
    (d / "me.json").write_text("{}")
    assert outreach.run(d, NOW, svc=mail).startswith("not sending: set CALI_SENDER_NAME")
    assert mail.sent == []


def test_an_approved_email_that_now_breaks_a_rule_goes_back_to_review(agent):
    d = agent(strong("A", "a.io"))
    outreach.suppress("a.io", d)  # you blocked the domain after approving
    mail = Mail()
    assert outreach.run(d, NOW, svc=mail).startswith("nothing approved to send")
    item = outreach.load_outbox(d)["a::first"]
    assert item["status"] == "queued" and "suppressed" in item["review_note"] and mail.sent == []


def test_dry_run_reports_without_sending_or_marking(agent):
    d = agent(strong("A", "a.io"))
    assert outreach.run(d, NOW, dry_run=True).startswith("would send to hi@a.io")
    assert outreach.load_outbox(d)["a::first"]["status"] == "approved"


def test_bounces_trip_the_breaker_and_resume_clears_it(agent):
    d = agent(strong("New", "n.io"), approve=False)
    box = {
        f"x{i}::first": {
            "company": f"x{i}", "kind": "first", "to": f"x@x{i}.io", "status": "bounced",
            "sent_at": f"2026-10-1{i}T10:00:00+00:00", "updated": "2026-10-18T10:00:00+00:00", "queued": "2026-10-10T10:00:00+00:00",
        }
        for i in range(3)
    }
    outreach.save_outbox(box, d)
    mail = Mail()
    assert outreach.run(d, NOW, svc=mail).startswith("paused: more than 2 of the last 20 sends bounced")
    assert mail.sent == []
    outreach.set_paused(False, data_dir=d)
    outreach.save_outbox({k: {**v, "status": "sent"} for k, v in box.items()}, d)  # bounces dealt with
    outreach.run(d, NOW, svc=mail)  # queues "New" for review
    approve_all(d)
    assert outreach.run(d, NOW, svc=mail).startswith("sent to")


def test_complaint_reply_pauses_everything(agent):
    d = agent(strong("A", "a.io"), strong("B", "b.io"))
    mail = Mail()
    outreach.run(d, NOW, svc=mail, rng=random.Random(0))
    mail.thread_messages = [
        {"labelIds": ["SENT"], "snippet": "hi", "payload": {"headers": [{"name": "From", "value": "me"}]}},
        {"labelIds": ["INBOX"], "snippet": "This is spam, I will report you", "payload": {"headers": [{"name": "From", "value": "a@a.io"}]}},
    ]
    out = outreach.run(d, NOW + timedelta(minutes=30), svc=mail)
    assert out.startswith("paused: complaint from hi@a.io") and len(mail.sent) == 1
    assert "hi@a.io" in outreach.load_suppressed(d)


def test_failed_send_pauses_and_is_never_retried_blindly(agent):
    d = agent(strong("A", "a.io"))
    assert outreach.run(d, NOW, svc=Mail(fail=True)).startswith("send failed, agent paused")
    assert outreach.load_outbox(d)["a::first"]["status"] == "sending"
    outreach.set_paused(False, data_dir=d)
    good = Mail()
    assert outreach.run(d, NOW, svc=good).startswith("nothing approved to send") and good.sent == []


def test_follow_up_is_reviewed_too_and_joins_the_thread(agent):
    d = agent(strong("A", "a.io"))
    mail = Mail()
    outreach.run(d, NOW, svc=mail, rng=random.Random(0))
    later = NOW + timedelta(days=8)
    (d / "profiles.json").write_text(json.dumps([strong("A", "a.io", action="follow_up")]))
    assert outreach.run(d, later, svc=mail, rng=random.Random(0)).startswith("nothing approved")  # queued for review only
    outreach.approve("A", "follow_up", d, later)
    assert outreach.run(d, later, svc=mail, rng=random.Random(0)) == "sent to hi@a.io (A, follow_up)"
    sent = mail.sent[1]
    assert sent["threadId"] == "t1"
    m = decoded(sent)
    assert m["In-Reply-To"] == "<first@x>" and m["Subject"].startswith("Re: ")


# ---- the review actions behind the screen -------------------------------------------------------------------------


def test_edit_marks_it_edited_needs_a_fresh_ok_and_can_be_undone(agent):
    d = agent(strong("A", "a.io"))
    before = outreach.load_outbox(d)["a::first"]["body"]
    item = outreach.update_item("A", "first", d, NOW, body=before + "\nP.S. hello", note="edit")
    assert item["edited"] and item["status"] == "queued" and len(item["history"]) == 1  # approved -> must be re-approved
    assert outreach.undo_edit("A", "first", d)["body"] == before
    with pytest.raises(ValueError, match="nothing to undo"):
        outreach.undo_edit("A", "first", d)


def test_edits_survive_a_requeue_but_untouched_drafts_get_the_new_template(agent):
    d = agent(strong("A", "a.io"), strong("B", "b.io"), approve=False)
    outreach.update_item("A", "first", d, NOW, body=f"Mine.\n\n{OPT_OUT}")
    fresh = lambda p: {**p["email_draft"], "subject": "NEW SUBJECT", "body": f"new template\n\n{OPT_OUT}"}  # noqa: E731
    outreach.queue_from_profiles(json.loads((d / "profiles.json").read_text()), d, NOW, draft_fn=fresh)
    box = outreach.load_outbox(d)
    assert box["a::first"]["body"].startswith("Mine.") and box["b::first"]["subject"] == "NEW SUBJECT"


def test_cannot_approve_something_that_would_not_pass(agent):
    d = agent(strong("A", "a.io"), approve=False)
    outreach.update_item("A", "first", d, NOW, body="Hi [proof: fill me]\n" + OPT_OUT)
    with pytest.raises(ValueError, match="fix first.*placeholder"):
        outreach.approve("A", "first", d, NOW)


def test_reject_can_block_the_domain_and_removes_it_from_review(agent):
    d = agent(strong("A", "a.io"), approve=False)
    outreach.reject("A", "first", d, NOW, block_domain=True)
    assert outreach.load_outbox(d)["a::first"]["status"] == "rejected" and "a.io" in outreach.load_suppressed(d)
    with pytest.raises(ValueError):
        outreach.update_item("A", "first", d, NOW, body="x")


def test_send_now_approves_and_sends_immediately_even_outside_the_window(agent):
    d = agent(strong("A", "a.io"), approve=False)
    mail = Mail()
    res = outreach.send_now("A", "first", d, NOW.replace(day=18), svc=mail)  # a Sunday: you are here, so it goes
    assert res == "sent to hi@a.io (A, first)" and outreach.load_outbox(d)["a::first"]["status"] == "sent" and len(mail.sent) == 1


def test_send_now_still_enforces_pause_lint_suppression_and_the_warm_up_cap(agent):
    d = agent(*[strong(f"C{i}", f"c{i}.io", priority=i) for i in range(4)], approve=False)
    mail = Mail()
    outreach.set_paused(True, "test", d)
    with pytest.raises(ValueError, match="paused"):
        outreach.send_now("C0", "first", d, NOW, svc=mail)
    outreach.set_paused(False, data_dir=d)
    outreach.update_item("C0", "first", d, NOW, body="[proof: x]\n" + OPT_OUT)
    with pytest.raises(ValueError, match="fix first"):
        outreach.send_now("C0", "first", d, NOW, svc=mail)
    outreach.suppress("c1.io", d)
    with pytest.raises(ValueError, match="never-contact"):
        outreach.send_now("C1", "first", d, NOW, svc=mail)
    for name in ("C2", "C3"):
        outreach.send_now(name, "first", d, NOW, svc=mail)
    assert len(mail.sent) == 2
    outreach.update_item("C0", "first", d, NOW, body=f"fixed\n\n{OPT_OUT}")
    outreach.suppress("zzz.io", d)
    # two sent so far; a third is allowed (cap 3), a fourth is refused
    outreach.send_now("C0", "first", d, NOW, svc=mail)
    d2 = outreach.load_outbox(d)
    d2["x::first"] = {**d2["c2::first"], "company": "x", "status": "queued", "to": "x@x.io", "sent_at": ""}
    outreach.save_outbox(d2, d)
    with pytest.raises(ValueError, match="warm-up cap"):
        outreach.send_now("x", "first", d, NOW, svc=mail)
    assert len(mail.sent) == 3


def test_send_now_needs_your_name(agent):
    d = agent(strong("A", "a.io"), approve=False)
    (d / "me.json").write_text("{}")
    with pytest.raises(ValueError, match="your name"):
        outreach.send_now("A", "first", d, NOW, svc=Mail())


def test_rehearsal_send_goes_to_your_address_only_and_records_nothing(agent):
    d = agent(strong("A", "a.io"), approve=False)
    mail = Mail()
    res = outreach.send_now("A", "first", d, NOW, svc=mail, to_override="me@mine.io")
    msg = decoded(mail.sent[0])
    assert "test copy sent to me@mine.io" in res and msg["To"] == "me@mine.io" and msg["Subject"].startswith("[TEST] ")
    item = outreach.load_outbox(d)["a::first"]
    assert item["status"] == "queued" and not item["sent_at"] and "a" not in load_outcomes(d)
