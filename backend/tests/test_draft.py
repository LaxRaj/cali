from draft import build_draft, pick_email

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


def test_warm_path_leads_the_email():
    d = build_draft(P, {"summary": "We both know Stripe"})
    assert d["body"].splitlines()[2] == "We both know Stripe."
