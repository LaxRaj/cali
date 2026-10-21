from draft import build_draft, pick_email, pick_intent

P = {
    "company_name": "Acme",
    "core_product": "Semantic search for contracts. Built in Rust.",
    "likely_bottleneck": "Keyword search misses clauses at scale.",
    "value_prop_pitch": "We cut review time. Happy to show how.",
    "people": [{"name": "Ada Lovelace", "role": "CEO"}],
    "contact": {"emails": [
        {"value": "press@acme.io", "kind": "press", "source_url": "u1"},
        {"value": "info@acme.io", "kind": "general", "source_url": "u2"},
        {"value": "sales@acme.io", "kind": "sales", "source_url": "u3"},
    ]},
}


def test_prefers_sales_over_general_and_skips_press():
    assert pick_email(P["contact"]["emails"])["value"] == "sales@acme.io"


def test_draft_uses_only_published_email_with_source():
    d = build_draft(P)
    assert d["to"] == "sales@acme.io" and d["to_source_url"] == "u3"
    assert d["body"].startswith("Hi Ada,") and "Semantic search for contracts." in d["body"]
    assert d["mailto"].startswith("mailto:sales%40acme.io?subject=")


def test_no_published_email_means_no_recipient():
    d = build_draft({**P, "contact": {}})
    assert d["to"] == "" and d["mailto"] == ""


def test_intent_follows_scout_signals(monkeypatch):
    monkeypatch.delenv("CALI_OUTREACH_INTENT", raising=False)
    assert pick_intent({**P, "why_now": [{"signal": "hn", "text": "x"}]})[0] == "work_for"
    assert pick_intent({**P, "tech_stack": ["Rust"]})[0] == "build_for"
    assert pick_intent(P)[0] == "build_with"
    assert pick_intent({**P, "tech_stack": ["Rust"]}, override="work_for") == ("work_for", "set by you")
    monkeypatch.setenv("CALI_OUTREACH_INTENT", "build_with")
    assert pick_intent({**P, "tech_stack": ["Rust"]})[0] == "build_with"


def test_each_intent_has_its_own_ask_and_an_opt_out(monkeypatch):
    monkeypatch.delenv("CALI_OUTREACH_INTENT", raising=False)
    sender = {"name": "Sam", "bio": "Backend engineer", "links": "github.com/sam"}
    p = {**P, "tech_stack": ["Rust", "Postgres"]}
    work = build_draft({**p, "why_now": [{"signal": "hn", "text": "Posted on Hacker News 2d ago"}]}, sender=sender)
    build = build_draft(p, sender=sender)
    assert work["intent"] == "work_for" and "role, or a small project" in work["body"]
    assert "Saw the recent news (posted on Hacker News 2d ago)." in work["body"]
    assert build["intent"] == "build_for" and "trial project" in build["body"]
    for d in (work, build):
        assert 'reply "no"' in d["body"] and d["body"].endswith("Backend engineer\ngithub.com/sam")


def test_no_sender_means_no_signature():
    assert build_draft(P, sender={"name": "", "bio": "", "links": ""})["body"].endswith("won't follow up.")


def test_warm_path_leads_the_email():
    d = build_draft(P, {"summary": "We both know Stripe"})
    assert d["body"].splitlines()[2] == "We both know Stripe."
