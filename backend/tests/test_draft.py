import outreach
from draft import ASK, OPT_OUT, build_draft, load_sender, pick_email, pick_intent

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
ME = {
    "name": "Sam", "bio": "builder", "links": "github.com/sam",
    "offer": "I build Next.js products with semantic search on top.",
    "proof": "a vector-search front end for a 2M-document archive", "proof_url": "github.com/sam/demo",
}


def test_prefers_sales_over_general_and_skips_press():
    assert pick_email(P["contact"]["emails"])["value"] == "sales@acme.io"


def test_draft_uses_only_published_email_with_source():
    d = build_draft(P, sender=ME)
    assert d["to"] == "sales@acme.io" and d["to_source_url"] == "u3"
    assert d["body"].startswith("Hi Ada,") and "semantic search for contracts" in d["body"]
    assert d["mailto"].startswith("mailto:sales%40acme.io?subject=")


def test_no_published_email_means_no_recipient():
    d = build_draft({**P, "contact": {}}, sender=ME)
    assert d["to"] == "" and d["mailto"] == ""


def test_founder_to_founder_email_is_short_has_one_ask_and_an_opt_out():
    d = build_draft(P, sender=ME)
    body = d["body"]
    assert "I'm Sam. I build Next.js products with semantic search on top." in body
    assert "I built a vector-search front end for a 2M-document archive (github.com/sam/demo)." in body
    assert body.count("?") == 1 and ASK in body and OPT_OUT in body
    assert body.endswith("Sam\ngithub.com/sam") and len(body.split()) < 110
    assert outreach.lint({**d, "kind": "first", "company": "Acme"}) == []  # ready to send as is


def test_nothing_the_scout_found_is_presented_as_news():
    d = build_draft({**P, "why_now": [{"signal": "early_stage", "text": "Newly found at seed stage"}]}, sender=ME)
    assert "newly found" not in d["body"].lower() and "recent news" not in d["body"].lower()


def test_missing_offer_or_proof_leaves_a_placeholder_that_blocks_sending():
    d = build_draft(P, sender={"name": "Sam", "bio": "", "links": ""})
    assert "[offer:" in d["body"] and "[proof:" in d["body"]
    assert any("placeholder" in p for p in outreach.lint({**d, "kind": "first", "company": "Acme"}))


def test_the_scouts_pitch_is_never_pasted_so_its_own_greeting_cannot_double_up():
    d = build_draft({**P, "value_prop_pitch": "Hi Zaky, I can build a fast interface."}, sender=ME)
    assert "Hi Zaky" not in d["body"] and "fast interface" not in d["body"]


def test_subject_is_short_and_never_cut_mid_word():
    long = {**P, "likely_bottleneck": "Scaling AI agent integration and data pipelines to handle high-volume claim workloads."}
    d = build_draft(long, sender=ME)
    assert d["subject"] == "Quick call about Acme?"
    assert build_draft(P, sender=ME, polish={"observation": "", "subject": "Contract search at scale"})["subject"] == "Contract search at scale"
    for bad in ("WOW BIG DEAL", "Act now!", "one two three four five six seven eight nine"):
        assert build_draft(P, sender=ME, polish={"observation": "", "subject": bad})["subject"] == "Quick call about Acme?"


def test_observation_uses_plain_text_and_company_prefixed_products_read_naturally():
    p = {**P, "company_name": "Plinto", "core_product": "Plinto builds AI‑agents that monitor payments in real‑time.",
         "likely_bottleneck": "Real‑time retrieval over massive streams of transaction data for anomaly detection and"}
    body = build_draft(p, sender=ME)["body"]
    assert "I've been reading about Plinto, which builds AI-agents that monitor payments in real-time." in body
    assert "‑" not in body and "The hard part looks like real-time retrieval over massive streams" in body


def test_polish_replaces_the_observation_only():
    body = build_draft(P, sender=ME, polish={"observation": "Acme makes contract search work at scale.", "subject": ""})["body"]
    assert "Acme makes contract search work at scale." in body and "I've been" not in body and ASK in body


def test_signal_hook_has_no_url_and_keeps_the_human_fill_in_placeholder():
    sig = {"type": "hiring", "roles": ["Backend Engineer"], "url": "https://jobs.acme.io/1", "role_kinds": ["eng"]}
    body = build_draft({**P, "signals": [sig]}, sender=ME)["body"]
    assert "I saw you're hiring (Backend Engineer)." in body and "jobs.acme.io" not in body
    assert "[after trying it:" in body  # only you can truthfully fill this in; lint blocks sending until you do


def test_intent_follows_scout_signals(monkeypatch):
    monkeypatch.delenv("CALI_OUTREACH_INTENT", raising=False)
    assert pick_intent({**P, "why_now": [{"signal": "hn", "text": "x"}]})[0] == "work_for"
    assert pick_intent({**P, "tech_stack": ["Rust"]})[0] == "build_for"
    assert pick_intent(P)[0] == "build_with"
    assert pick_intent({**P, "tech_stack": ["Rust"]}, override="work_for") == ("work_for", "set by you")
    monkeypatch.setenv("CALI_OUTREACH_INTENT", "build_with")
    assert pick_intent({**P, "tech_stack": ["Rust"]})[0] == "build_with"


def test_intent_changes_one_clause_but_the_ask_is_always_the_short_call(monkeypatch):
    monkeypatch.delenv("CALI_OUTREACH_INTENT", raising=False)
    work = build_draft({**P, "why_now": [{"signal": "hn", "text": "x"}]}, sender=ME)
    build = build_draft({**P, "tech_stack": ["Rust"]}, sender=ME)
    partner = build_draft(P, sender=ME)
    assert "as a hire or a project" in work["body"] and "I could help on that side" in build["body"] and "build on that together" in partner["body"]
    assert all(ASK in d["body"] for d in (work, build, partner))


def test_no_sender_name_means_no_signature():
    body = build_draft(P, sender={"name": "", "bio": "", "links": ""})["body"]
    assert body.endswith("won't follow up.") and "I'm " not in body.split("\n")[2]


def test_warm_path_leads_the_email():
    d = build_draft(P, {"summary": "We both know Stripe"}, sender=ME)
    assert d["body"].splitlines()[2] == "We both know Stripe."


def test_load_sender_reads_me_json_and_env_wins(tmp_path, monkeypatch):
    (tmp_path / "me.json").write_text('{"name": "Sam", "offer": "I build things.", "proof": "x"}')
    assert load_sender(tmp_path)["offer"] == "I build things." and load_sender(tmp_path)["proof_url"] == ""
    monkeypatch.setenv("CALI_SENDER_NAME", "Override")
    assert load_sender(tmp_path)["name"] == "Override"
    assert load_sender(tmp_path / "missing")["name"] == "Override"


def test_conftest_isolates_tests_from_the_real_me_json():
    assert load_sender()["name"] == ""  # not the developer's data/me.json
