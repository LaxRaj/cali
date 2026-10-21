from datetime import datetime, timedelta, timezone

import pytest

import gmail_sync
import outreach
from outcomes import load_outcomes

NOW = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)


def lead(name, to="hi@acme.io", action="contact_now", priority=50, source="u"):
    return {
        "company_name": name,
        "decision": {"action": action, "priority": priority},
        "email_draft": {"to": to, "to_source_url": source, "subject": f"{name}: s", "body": "b", "intent": "build_for", "intent_reason": "r"}
        if to
        else {"to": ""},
    }


def test_queues_only_contact_now_with_sourced_address(tmp_path):
    ps = [lead("A"), lead("B", action="watch", to="b@b.io"), lead("C", to=""), lead("D", to="d@d.io", source="")]
    added = outreach.queue_from_profiles(ps, tmp_path, NOW)
    assert [i["company"] for i in added] == ["A"]
    assert added[0]["status"] == "queued"


def test_skips_addresses_scraped_from_the_publisher_that_covered_the_startup(tmp_path):
    press = {**lead("Deeptune", to="writer@fortune.com"), "website": "https://fortune.com", "source_url": "https://www.fortune.com/a/b"}
    own = {**lead("Acme"), "website": "https://acme.io", "source_url": "https://news.ycombinator.com/item?id=1"}
    assert [i["company"] for i in outreach.queue_from_profiles([press, own], tmp_path, NOW)] == ["Acme"]


def test_does_not_requeue_same_company(tmp_path):
    outreach.queue_from_profiles([lead("A")], tmp_path, NOW)
    assert outreach.queue_from_profiles([lead("A")], tmp_path, NOW) == []


def test_daily_cap_takes_highest_priority_first(tmp_path):
    ps = [lead(f"C{i}", to=f"x@d{i}.io", priority=i) for i in range(5)]
    added = outreach.queue_from_profiles(ps, tmp_path, NOW, cap=2)
    assert [i["company"] for i in added] == ["C4", "C3"]


def test_one_contact_per_domain_within_cooldown(tmp_path):
    ps = [lead("A", to="a@shared.io", priority=9), lead("B", to="b@shared.io", priority=1)]
    assert [i["company"] for i in outreach.queue_from_profiles(ps, tmp_path, NOW)] == ["A"]
    later = NOW + timedelta(days=outreach.DOMAIN_COOLDOWN_DAYS + 1)
    assert [i["company"] for i in outreach.queue_from_profiles(ps, tmp_path, later, cap=5)] == ["B"]


def test_suppressed_domain_and_address_are_skipped(tmp_path):
    outreach.suppress("@blocked.io", tmp_path)
    outreach.suppress("c@ok.io", tmp_path)
    ps = [lead("A", to="a@blocked.io"), lead("C", to="c@ok.io"), lead("D", to="d@ok.io")]
    assert [i["company"] for i in outreach.queue_from_profiles(ps, tmp_path, NOW)] == ["D"]


def test_kill_switch(tmp_path, monkeypatch):
    monkeypatch.setenv("CALI_OUTREACH", "0")
    assert outreach.queue_from_profiles([lead("A")], tmp_path, NOW) == []
    assert gmail_sync.push(tmp_path, svc=object()) == "CALI_OUTREACH=0: disabled"


def test_follow_up_only_after_sent_and_only_once(tmp_path):
    outreach.queue_from_profiles([lead("A")], tmp_path, NOW)
    fu = lead("A", action="follow_up")
    assert outreach.queue_from_profiles([fu], tmp_path, NOW + timedelta(days=9)) == []  # not sent yet
    outreach.set_status("A", "first", "sent", tmp_path, now=NOW)
    assert outreach.queue_from_profiles([fu], tmp_path, NOW + timedelta(days=3)) == []  # too soon
    added = outreach.queue_from_profiles([fu], tmp_path, NOW + timedelta(days=8))
    assert [i["kind"] for i in added] == ["follow_up"] and added[0]["subject"] == "Re: A: s"
    assert outreach.queue_from_profiles([fu], tmp_path, NOW + timedelta(days=30)) == []  # then stop


def test_status_changes_feed_outcomes_and_suppression(tmp_path):
    outreach.queue_from_profiles([lead("A")], tmp_path, NOW)
    outreach.set_status("A", "first", "sent", tmp_path, now=NOW)
    assert load_outcomes(tmp_path)["a"]["status"] == "contacted"
    outreach.set_status("A", "first", "opted_out", tmp_path, now=NOW)
    assert load_outcomes(tmp_path)["a"]["status"] == "passed"
    assert "hi@acme.io" in outreach.load_suppressed(tmp_path)


def test_set_status_rejects_unknown(tmp_path):
    outreach.queue_from_profiles([lead("A")], tmp_path, NOW)
    with pytest.raises(ValueError):
        outreach.set_status("A", "first", "wat", tmp_path)


def test_classify_thread():
    me = {"labelIds": ["SENT"], "from": "me@x.io", "snippet": "hi"}
    assert gmail_sync.classify_thread([me]) == "sent"
    assert gmail_sync.classify_thread([me, {"labelIds": ["INBOX"], "from": "Ada <a@acme.io>", "snippet": "Sure, let's talk"}]) == "replied"
    assert gmail_sync.classify_thread([me, {"labelIds": ["INBOX"], "from": "a@acme.io", "snippet": "Please unsubscribe me"}]) == "opted_out"
    assert gmail_sync.classify_thread([me, {"labelIds": ["INBOX"], "from": "Mail Delivery <MAILER-DAEMON@g.com>", "snippet": "failed"}]) == "bounced"
    assert gmail_sync.classify_thread([]) is None


class FakeGmail:
    def __init__(self, thread_messages=None):
        self.created, self.messages = [], thread_messages or []

    def users(self):
        return self

    def drafts(self):
        return self

    def threads(self):
        return self

    def create(self, userId, body):
        self.created.append(body)
        return self._done({"id": "d1", "message": {"threadId": "t1"}})

    def get(self, **kw):
        return self._done({"messages": self.messages})

    @staticmethod
    def _done(value):
        class R:
            def execute(self):
                return value

        return R()


def test_push_creates_drafts_never_sends_then_sync_records_reply(tmp_path):
    outreach.queue_from_profiles([lead("A")], tmp_path, NOW)
    svc = FakeGmail()
    assert "created 1" in gmail_sync.push(tmp_path, svc=svc)
    item = outreach.load_outbox(tmp_path)["a::first"]
    assert item["status"] == "drafted" and item["gmail_thread_id"] == "t1"
    assert not hasattr(svc, "send")

    def msg(labels, sender, snippet):
        return {"labelIds": labels, "snippet": snippet, "payload": {"headers": [{"name": "From", "value": sender}]}}

    svc.messages = [msg(["DRAFT"], "me", "")]
    assert gmail_sync.sync(tmp_path, svc=svc) == "updated 0 item(s)"
    svc.messages = [msg(["SENT"], "me", "hi"), msg(["INBOX"], "a@acme.io", "yes please")]
    assert gmail_sync.sync(tmp_path, svc=svc) == "updated 1 item(s)"
    assert outreach.load_outbox(tmp_path)["a::first"]["status"] == "replied"
    assert load_outcomes(tmp_path)["a"]["status"] == "replied"
