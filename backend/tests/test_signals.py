import re
from datetime import datetime, timedelta, timezone

import ats
from decide.policy import decide_lead
from discovery.hiring import parse_post, to_candidate
from draft import build_draft
from enrich import parse_page, post_emails, product_access
from signals import hiring_extraction, make_signal, merge_signals, parse_roles, role_kind, signal_strength
from whynow import why_now

NOW = datetime(2026, 10, 21, tzinfo=timezone.utc)
POST = ('Acme | Founding Engineer, Product Designer | Remote | <a href="https://acme.io">acme.io</a>'
        '<p>We build vector search for legal teams and just launched. Email jobs@acme.io to apply, we read everything.</p>')


def test_role_kind_and_parse_roles():
    assert role_kind("Founding Engineer") == "founding"
    assert role_kind("Customer Success Manager") == "customer"
    assert role_kind("Senior Backend Engineer") == "eng"
    assert role_kind("Product Designer") == "design"
    assert parse_roles("Founding Engineer, Product Designer & GTM Lead") == ["Founding Engineer", "Product Designer", "GTM Lead"]


def test_hiring_post_becomes_a_candidate_with_meta_and_a_profile_without_the_llm():
    cand = to_candidate(parse_post(POST), "123", "2026-10-20T00:00:00Z")
    assert cand.company == "Acme" and cand.meta["website"] == "https://acme.io" and "Founding" in cand.meta["roles"]
    ex = hiring_extraction(cand.company, cand.meta["roles"], cand.meta["text"], cand.meta["website"])
    assert ex.startup.company_name == "Acme" and "vector search" in ex.startup.core_product
    items = post_emails(cand.meta["text"], "https://news.ycombinator.com/item?id=123")
    assert [(i.value, i.source_url.endswith("123")) for i in items] == [("jobs@acme.io", True)]


def test_merge_signals_unions_roles_per_type_and_source():
    a = make_signal("hiring", "greenhouse", "u", ["Backend Engineer"], now=NOW)
    b = make_signal("hiring", "greenhouse", "u", ["Product Designer"], now=NOW)
    out = merge_signals([a], [b, make_signal("launch", "yc", "v", now=NOW)])
    assert len(out) == 2 and sorted(next(s for s in out if s["type"] == "hiring")["role_kinds"]) == ["design", "eng"]


def test_strength_ranks_freelancer_over_founding_hiring_over_old_launch():
    fresh = (NOW - timedelta(days=2)).isoformat()
    old = (NOW - timedelta(days=60)).isoformat()
    f = signal_strength([make_signal("seeking_freelancer", "hn", "u", ["Dev"], fresh)], NOW)
    h = signal_strength([make_signal("hiring", "hn", "u", ["Founding Engineer"], fresh)], NOW)
    plain = signal_strength([make_signal("hiring", "hn", "u", ["Engineer"], fresh)], NOW)
    launch_old = signal_strength([make_signal("launch", "rss", "u", [], old)], NOW)
    assert f > h > plain > launch_old


def test_policy_lifts_thin_hiring_leads_that_would_otherwise_be_skipped():
    base = {"company_name": "Acme", "score": 30, "discovered_at": NOW.isoformat(), "contact": {"emails": [{"value": "jobs@acme.io", "kind": "general"}]}, "people": []}
    assert decide_lead(base, None, NOW)["action"] == "skip"
    sig = make_signal("hiring", "hn", "u", ["Founding Engineer", "Designer", "GTM"], NOW.isoformat(), NOW)
    out = decide_lead({**base, "signals": [sig]}, None, NOW)
    assert out["action"] != "skip" and any("signal strength" in r for r in out["reasons"])


def test_why_now_and_draft_cite_the_signal_and_never_claim_to_have_used_the_product():
    sig = make_signal("hiring", "greenhouse", "https://boards.greenhouse.io/acme", ["Backend Engineer"], NOW.isoformat(), NOW)
    prof = {"company_name": "Acme", "core_product": "Vector search for legal teams.", "signals": [sig], "people": [], "contact": {"emails": []}}
    assert why_now(prof, NOW)[0]["text"].startswith("Hiring") and why_now(prof, NOW)[0]["source_url"].endswith("/acme")
    body = build_draft(prof)["body"]
    assert "I saw you're hiring (Backend Engineer)" in body
    # spec change (2026-11-06): no "[after trying it: ...]" placeholder, which outreach.lint always rejected, so no draft
    # could ever be sent; the angle is built from scouted facts, and it still never claims the sender used the product
    assert "[" not in body and not re.search(r"\bI (tried|used|tested|played with)\b", body)


def test_ats_detect_and_parse():
    assert ats.detect_board(["https://example.com", "https://boards.greenhouse.io/acme/jobs/1"]) == ("greenhouse", "acme")
    assert ats.detect_board(["https://jobs.lever.co/acme"]) == ("lever", "acme")
    assert ats.detect_board(["https://jobs.ashbyhq.com/acme/abc"]) == ("ashby", "acme")
    assert ats.detect_board(["https://example.com/careers"]) is None
    gh = ats.parse_jobs("greenhouse", {"jobs": [{"title": "SRE", "absolute_url": "u", "updated_at": "2026-10-01"}]})
    lv = ats.parse_jobs("lever", [{"text": "ML Eng", "hostedUrl": "u", "createdAt": 1760000000000}])
    ab = ats.parse_jobs("ashby", {"jobs": [{"title": "Designer", "jobUrl": "u", "publishedAt": "2026-10-02"}]})
    assert gh[0]["title"] == "SRE" and lv[0]["posted_at"].startswith("2025") and ab[0]["posted_at"] == "2026-10-02"
    ld = ats.jsonld_jobs([{"@type": "JobPosting", "title": "PM", "datePosted": "2026-10-03"}], "https://acme.io/jobs")
    assert ld == [{"title": "PM", "url": "https://acme.io/jobs", "posted_at": "2026-10-03"}]


def test_parse_roles_keeps_parenthesised_commas_together():
    assert parse_roles("Engineering Manager, Data Platform (NYC, Hybrid) · Software Engineer") == [
        "Engineering Manager", "Data Platform (NYC, Hybrid) · Software Engineer"]


def test_draft_prefers_the_address_published_in_the_signal_post():
    sig = make_signal("hiring", "hn", "https://news.ycombinator.com/item?id=1", ["Engineer"], NOW.isoformat(), NOW)
    prof = {"company_name": "Acme", "signals": [sig], "people": [], "contact": {"emails": [
        {"value": "abdullah@acme.io", "kind": "person", "source_url": "https://acme.io/contact"},
        {"value": "careers@acme.io", "kind": "general", "source_url": "https://news.ycombinator.com/item?id=1"}]}}
    d = build_draft(prof)
    assert d["to"] == "careers@acme.io" and d["to_source_url"].endswith("id=1")


def test_product_access_finds_try_and_docs_links_only():
    html = '<a href="/signup">Get started</a><a href="https://docs.acme.io">Docs</a><a href="https://x.com/acme">Try X</a><a href="/blog">Blog</a>'
    pg = parse_page("https://acme.io/", html)
    got = product_access([pg], "https://acme.io")
    assert [g["label"] for g in got] == ["Get started", "Docs"]
