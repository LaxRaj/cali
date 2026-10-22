import http.client
import json
import threading
from datetime import datetime, timedelta, timezone

import pytest

import outreach
import review
from draft import OPT_OUT
from test_outreach_agent import Mail, strong

NOW = datetime(2026, 10, 20, 12, tzinfo=timezone.utc)


@pytest.fixture
def app(tmp_path, monkeypatch):
    for k in ("CALI_OUTREACH", "CALI_SENDER_NAME"):
        monkeypatch.delenv(k, raising=False)
    (tmp_path / "me.json").write_text(json.dumps({"name": "Sam"}))
    ps = [strong("A", "a.io", priority=9), strong("B", "b.io", priority=1)]
    (tmp_path / "profiles.json").write_text(json.dumps(ps))
    outreach.queue_from_profiles(ps, tmp_path, NOW)
    mail = Mail()

    def reviser(item, feedback):
        return {"subject": item["subject"], "body": f"Rewritten ({feedback}).\n\n{OPT_OUT}\n\nSam"}

    a = review.ReviewApp(tmp_path, svc=mail, reviser=reviser)
    a.mail = mail
    return a


def key(c):
    return f"{c}::first"


def test_lists_waiting_emails_best_lead_first_with_why_and_lint(app):
    items = app.items()["items"]
    assert [i["company"] for i in items] == ["A", "B"]
    assert items[0]["status"] == "queued" and items[0]["reasons"] == ["lead score 80"] and items[0]["lint"] == [] and items[0]["to_source_url"]
    assert app.status()["cap"] == 3 and app.status()["sent_today"] == 0 and not app.status()["paused"]


def test_save_then_rewrite_with_feedback_is_undoable(app):
    original = app.items()["items"][0]["body"]
    app.save(key("A"), "New subject", original + "\nP.S.")
    app.revise(key("A"), "New subject", original + "\nP.S.", "shorter please")
    it = app.items()["items"][0]
    assert it["body"].startswith("Rewritten (shorter please).") and it["subject"] == "New subject" and it["can_undo"]
    app.undo(key("A"))
    assert app.items()["items"][0]["body"].endswith("P.S.")
    app.undo(key("A"))
    assert app.items()["items"][0]["body"] == original


def test_a_failed_rewrite_changes_nothing_but_keeps_what_you_typed(app):
    app.reviser = lambda item, fb: (_ for _ in ()).throw(ValueError("the rewrite breaks a rule"))
    with pytest.raises(ValueError, match="breaks a rule"):
        app.revise(key("A"), "S", "my typed text\n" + OPT_OUT, "x")
    assert app.items()["items"][0]["body"].startswith("my typed text")


def test_reject_removes_it_and_can_block_the_domain(app):
    app.reject(key("B"), block_domain=True)
    assert [i["company"] for i in app.items()["items"]] == ["A"] and "b.io" in outreach.load_suppressed(app.data_dir)


def test_send_sends_exactly_the_text_on_screen(app):
    out = app.send(key("A"), "My subject", f"Hi A,\n\nExactly this.\n\n{OPT_OUT}\n\nSam")
    assert out["result"] == "sent to hi@a.io (A, first)"
    assert len(app.mail.sent) == 1 and outreach.load_outbox(app.data_dir)["a::first"]["subject"] == "My subject"
    assert [i["company"] for i in app.items()["items"]] == ["B"] and app.items()["sent"][0]["company"] == "A"


def test_send_refusals_are_explained_not_swallowed(app):
    with pytest.raises(ValueError, match="fix first"):
        app.send(key("A"), "S", "Hi [proof: fill me]\n" + OPT_OUT)
    assert app.mail.sent == []
    outreach.set_paused(True, "bounces", app.data_dir)
    with pytest.raises(ValueError, match="paused"):
        app.send(key("B"), "S", f"ok\n{OPT_OUT}")


def test_rehearsal_mode_sends_a_test_copy_to_you_only(app):
    app.test_to = "me@mine.io"
    out = app.send(key("A"), "S", f"Hi A,\n\nbody\n\n{OPT_OUT}\n\nSam")
    assert "test copy sent to me@mine.io" in out["result"]
    assert app.mail.sent and outreach.load_outbox(app.data_dir)["a::first"]["status"] == "queued"


def test_find_new_emails_queues_fresh_drafts(app):
    app.reject(key("A"))
    ps = json.loads((app.data_dir / "profiles.json").read_text()) + [strong("C", "c.io")]
    (app.data_dir / "profiles.json").write_text(json.dumps(ps))
    app.draft_fn = lambda p: p["email_draft"]
    assert app.queue() == {"added": 1} and "C" in [i["company"] for i in app.items()["items"]]


# ---- HTTP: the security properties that stop other websites from sending mail through your localhost ---------------


@pytest.fixture
def server(app):
    srv = review.serve(app, 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield app, srv.server_address[1]
    srv.shutdown()


def call(port, method, path, token=None, body=None, host=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Token"] = token
    if host:
        headers["Host"] = host
    conn.request(method, path, json.dumps(body) if body is not None else None, headers)
    r = conn.getresponse()
    data = r.read().decode()
    return r.status, data


def test_http_requires_token_and_a_local_host_header(server):
    app, port = server
    status, page = call(port, "GET", "/")
    assert status == 200 and app.token in page and "Outreach review" in page
    assert call(port, "GET", "/api/items")[0] == 403
    assert call(port, "GET", "/api/items", token="wrong")[0] == 403
    assert call(port, "GET", "/api/items", token=app.token, host="evil.example.com")[0] == 403  # DNS-rebinding style request
    assert call(port, "GET", "/", host="evil.example.com")[0] == 403
    assert call(port, "POST", "/api/send", body={"key": key("A"), "subject": "s", "body": "b"})[0] == 403
    assert app.mail.sent == []


def test_http_round_trip_edit_and_send(server):
    app, port = server
    t = app.token
    status, data = call(port, "GET", "/api/items", t)
    assert status == 200 and len(json.loads(data)["items"]) == 2
    status, data = call(port, "POST", "/api/send", t, {"key": key("A"), "subject": "S", "body": f"Hi\n\n{OPT_OUT}\n\nSam"})
    assert status == 200 and json.loads(data)["result"].startswith("sent to hi@a.io")
    status, data = call(port, "POST", "/api/send", t, {"key": key("A"), "subject": "S", "body": "x"})
    assert status == 400 and "error" in json.loads(data)  # already sent
    assert call(port, "POST", "/api/nope", t, {})[0] == 404
    assert call(port, "POST", "/api/save", t, {"key": key("B")})[0] == 400  # missing fields


def test_the_page_never_renders_scraped_text_as_html():
    assert "innerHTML" not in review.PAGE and "outerHTML" not in review.PAGE and "document.write" not in review.PAGE
