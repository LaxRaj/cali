from datetime import datetime

from discovery.feedback import allocate, source_stats
from models import Contact, ContactItem, Edge, Person, StartupProfile
from rating import rate


def prof(**kw):
    base = dict(company_name="Acme", core_product="Semantic search for legal contracts and filings", tech_stack=["Python"],
                likely_bottleneck="Keyword search misses relevant clauses at scale", value_prop_pitch="One. Two.", is_relevant=True,
                funding_stage="seed", funding_amount="$5M", hq="Berlin", website="https://acme.io")
    return StartupProfile(**{**base, **kw})


FULL_CONTACT = Contact(website="https://acme.io", emails=[ContactItem(value="hi@acme.io", kind="general", source_url="u")],
                       phones=[ContactItem(value="+14155550132", kind="main", source_url="u")], socials={"linkedin": "l"}, contact_page="c")


def test_complete_lead_scores_100_with_no_gaps():
    people = [Person(name="A B", role="CEO", evidence="e", linkedin="x"), Person(name="C D", role="CTO", evidence="e")]
    edges = [Edge(src="Fund", rel="invested_in", dst="Acme", evidence="e"), Edge(src="A B", rel="previously_at", dst="G", evidence="e"),
             Edge(src="A B", rel="founded", dst="Acme", evidence="e")]
    r = rate(prof(), people, edges, FULL_CONTACT)
    assert r.score == 100 and r.gaps == [] and sum(r.parts.values()) == 100


def test_sparse_lead_lists_what_is_missing():
    r = rate(prof(funding_stage="", funding_amount="", hq="", website="", tech_stack=[]), [], [], None)
    assert r.score < 30
    assert {"funding stage", "website", "location", "funding amount", "tech stack", "founder", "people profiles", "investors", "email", "phone"} <= set(r.gaps)


def test_contact_and_investors_raise_the_score():
    base = rate(prof(), [Person(name="A B", role="CEO", evidence="e")], [], Contact())
    better = rate(prof(), [Person(name="A B", role="CEO", evidence="e")], [Edge(src="F", rel="backed_by", dst="Acme", evidence="e")], FULL_CONTACT)
    assert better.score - base.score == 10 + 10 + 4 + 3 + 3  # investor + email + phone + socials + contact page


def _run(tmp_path, name, accepted, rejected):
    d = tmp_path / "runs"
    d.mkdir(exist_ok=True)
    (d / f"{name}.json").write_text(__import__("json").dumps({
        "accepted": [{"source": s, "score": sc} for s, sc in accepted],
        "rejections": [{"source": s, "reasons": [r]} for s, r in rejected],
    }))


def test_source_stats_ignores_infrastructure_errors(tmp_path):
    _run(tmp_path, "a", [("rss", 80), ("rss", 60), ("hn", 40)], [("hn", "not a relevant startup page")] * 3 + [("yc", "extraction error")])
    st = source_stats(tmp_path)
    assert st["rss"] == {"crawled": 2, "accepted": 2, "score_sum": 140, "yield": 1.0, "avg_score": 70.0}
    assert st["hn"]["yield"] == 0.25 and "yc" not in st  # rate-limit failures don't count against a source


def test_allocate_shifts_budget_to_productive_sources_but_keeps_exploring():
    stats = {"rss": {"crawled": 10, "accepted": 8, "yield": 0.8, "avg_score": 70.0}, "hn": {"crawled": 10, "accepted": 0, "yield": 0.0, "avg_score": 0.0}}
    caps = allocate(stats, ["rss", "hn", "yc"], total=12)
    assert caps["rss"] > caps["yc"] >= caps["hn"] >= 2  # unseen source (yc) gets a fair prior; the dud keeps a floor
    assert allocate({}, ["a", "b"], total=12) == {"a": 6, "b": 6}
    assert allocate({}, ["only"], total=12)["only"] == 7  # per-source maximum
