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
    assert better.score - base.score == 10 + 20  # investor + contact (general email 9 + page 4 + socials 4 + phone 4, capped at 20)


def test_perfect_contact_does_not_need_a_phone():
    no_phone = Contact(website="https://acme.io", emails=[ContactItem(value="a@acme.io", kind="person", source_url="u")],
                       socials={"linkedin": "l"}, contact_page="c")
    assert rate(prof(), [], [], no_phone).parts["contact"] == 20


def test_person_email_outranks_generic_inbox():
    def c(kind):
        return Contact(emails=[ContactItem(value="x@acme.io", kind=kind, source_url="u")])
    assert rate(prof(), [], [], c("person")).parts["contact"] > rate(prof(), [], [], c("general")).parts["contact"] \
        > rate(prof(), [], [], c("support")).parts["contact"]


def test_stage_matches_unicode_hyphen_and_series_b_gets_partial_fit():
    assert rate(prof(funding_stage="pre‑seed"), [], [], None).parts["fit"] == 25
    assert rate(prof(funding_stage="Series B"), [], [], None).parts["fit"] == 21
    assert "funding stage" in rate(prof(funding_stage="Series D"), [], [], None).gaps


def test_yc_listing_implies_an_accelerator_stage():
    yc = prof(funding_stage="", source_url="https://www.ycombinator.com/launches/abc-acme")
    assert rate(yc, [], [], None).parts["fit"] == 25 and "funding stage" not in rate(yc, [], [], None).gaps
    hn = prof(funding_stage="", source_url="https://news.ycombinator.com/item?id=1")
    assert "funding stage" in rate(hn, [], [], None).gaps


def test_open_roles_stand_in_for_a_stated_bottleneck():
    thin = prof(likely_bottleneck="")
    assert rate(thin, [], [], None).parts["fit"] == 20
    assert rate(thin, [], [], None, hiring_roles=["Backend Engineer"]).parts["fit"] == 25


def test_qualified_needs_stage_leader_and_a_way_in():
    ceo = [Person(name="A B", role="CEO", evidence="e")]
    assert rate(prof(), ceo, [], FULL_CONTACT).qualified
    assert not rate(prof(funding_stage=""), ceo, [], FULL_CONTACT).qualified  # unknown stage
    assert not rate(prof(), [], [], FULL_CONTACT).qualified  # nobody to address
    assert not rate(prof(), ceo, [], Contact()).qualified  # unreachable
    r = rate(prof(), ceo, [], FULL_CONTACT)
    assert set(r.axes) == {"fit", "reach", "evidence"} and all(0 <= v <= 100 for v in r.axes.values())


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
