from pathlib import Path

from models import Edge, Extraction, Person, StartupProfile
from quality import (
    RunReport, check_extraction, evaluate_run, grounded, is_placeholder, sentence_count, validate_profile,
)

FIX = Path(__file__).parent / "fixtures"
PAGE = (FIX / "bw_tako.md").read_text()
GOOD_PITCH = "Your search is the bottleneck. I can ship Next.js with vector semantic search."


def profile(**kw) -> StartupProfile:
    base = dict(company_name="Tako", core_product="AI search engine", tech_stack=["AI"],
                likely_bottleneck="Retrieval over structured data", value_prop_pitch=GOOD_PITCH, is_relevant=True)
    return StartupProfile(**{**base, **kw})


def test_placeholders():
    assert all(is_placeholder(x) for x in ["", "N/A", " none ", "Unknown", "Unnamed"])
    assert not is_placeholder("Tako")


def test_sentence_count():
    assert sentence_count(GOOD_PITCH) == 2
    assert sentence_count("One sentence only.") == 1
    assert sentence_count("Uses Next.js here. And vectors. And more.") == 3
    assert sentence_count("") == 0


def test_grounding_is_verbatim_but_ignores_markdown_and_case():
    assert grounded("Co-founded by Alex Rosenberg, former Amazon leader", PAGE)
    assert grounded("co-founded   by ALEX Rosenberg", PAGE)  # whitespace/case-insensitive
    assert not grounded("Co-founded by Elon Musk, former Tesla leader", PAGE)
    assert not grounded("hi", PAGE)  # too short to be evidence


def test_grounding_handles_ellipses_and_unicode_hyphens():
    # non-breaking hyphen in the page vs plain hyphen in the quote
    assert grounded("Co-founded by Alex Rosenberg", "Co\u2011founded by Alex Rosenberg, former Amazon leader")
    # elided quote: all fragments present, in order
    assert grounded("participation from ... Naval Ravikant", "with participation from Gokul Rajaram, Naval Ravikant and more")
    assert not grounded("Naval Ravikant ... participation from", "with participation from Gokul Rajaram, Naval Ravikant and more")
    assert not grounded("participation from ... Elon Musk", "with participation from Gokul Rajaram, Naval Ravikant and more")


def test_validate_profile_flags_each_problem():
    assert validate_profile(profile()) == []
    bad = validate_profile(profile(company_name="N/A", core_product="", likely_bottleneck="n/a",
                                   value_prop_pitch="Only one sentence.", tech_stack=[]))
    assert {"missing company_name", "missing core_product", "missing likely_bottleneck"} <= set(bad)
    assert any("pitch has 1 sentences" in i for i in bad)
    assert "warn: empty tech_stack" in bad


def test_check_extraction_rejects_irrelevant_and_blank_names():
    irrelevant = Extraction(startup=profile(is_relevant=False))
    assert not check_extraction(irrelevant, PAGE).accepted
    blank = Extraction(startup=profile(company_name="N/A"))
    assert not check_extraction(blank, PAGE).accepted


def test_missing_tech_stack_is_only_a_warning():
    c = check_extraction(Extraction(startup=profile(tech_stack=[])), PAGE)
    assert c.accepted and "warn: empty tech_stack" in c.issues


def test_ungrounded_people_and_edges_are_dropped():
    ex = Extraction(
        startup=profile(),
        people=[
            Person(name="Alex Rosenberg", role="co-founder", org="Tako", evidence="Co-founded by Alex Rosenberg"),
            Person(name="Elon Musk", role="investor", org="Tako", evidence="Elon Musk invested in Tako"),
        ],
        edges=[
            Edge(src="Alex Rosenberg", rel="cofounded", dst="Tako", evidence="Co-founded by Alex Rosenberg"),
            Edge(src="Elon Musk", rel="invested_in", dst="Tako", evidence="Elon Musk invested in Tako"),
            Edge(src="Tako", rel="competitor_of", dst="tako", evidence="Co-founded by Alex Rosenberg"),
        ],
    )
    c = check_extraction(ex, PAGE)
    assert c.accepted
    assert [p.name for p in c.extraction.people] == ["Alex Rosenberg"]
    assert [e.src for e in c.extraction.edges] == ["Alex Rosenberg"]  # fake + self-edge dropped
    assert c.dropped_people == 1 and c.dropped_edges == 2


def test_run_gates():
    ok = RunReport(relevant=5, valid=4, sources={"hn": 2, "rss": 2})
    assert evaluate_run(ok).passed

    few = evaluate_run(RunReport(relevant=2, valid=2, sources={"hn": 1, "rss": 1}))
    assert not few.passed and any("valid startups" in f for f in few.failures)

    sloppy = evaluate_run(RunReport(relevant=10, valid=4, sources={"hn": 2, "rss": 2}))
    assert any("validity rate" in f for f in sloppy.failures)

    single = evaluate_run(RunReport(relevant=4, valid=4, sources={"hn": 4}))
    assert any("discovery sources" in f for f in single.failures)

    assert not evaluate_run(RunReport()).passed  # empty run never passes


def test_tidy_removes_org_people_and_redundant_edges():
    from models import Edge, Extraction, Person, StartupProfile
    from quality import tidy

    sp = StartupProfile(company_name="Acme", core_product="p", likely_bottleneck="b", value_prop_pitch="x. y.", is_relevant=True)
    P = lambda n, r: Person(name=n, role=r, org="Acme", evidence="e")  # noqa: E731
    E_ = lambda a, r, b: Edge(src=a, rel=r, dst=b, evidence="e")  # noqa: E731
    ex = Extraction(
        startup=sp,
        people=[P("Jane Roe", "co-founder"), P("People Ventures", "investor"), P("Peakon", "former employer"), P("Emblem", "investor")],
        edges=[E_("Jane Roe", "founded", "Acme"), E_("Jane Roe", "cofounded", "Acme"), E_("Jane Roe", "works_at", "Acme"),
               E_("People Ventures", "invested_in", "Acme")],
    )
    out = tidy(ex)
    assert [p.name for p in out.people] == ["Jane Roe"]
    assert [(e.src, e.rel) for e in out.edges] == [("Jane Roe", "cofounded"), ("People Ventures", "invested_in")]


def test_tidy_merges_first_names_and_drops_unidentifiable_people():
    from models import Edge, Extraction, Person, StartupProfile
    from quality import tidy

    sp = StartupProfile(company_name="Axel", core_product="p", likely_bottleneck="b", value_prop_pitch="x. y.", is_relevant=True)
    P = lambda n, r: Person(name=n, role=r, org="Axel", evidence="e")  # noqa: E731
    ex = Extraction(
        startup=sp,
        people=[P("Stephen", "Founder & CEO"), P("Stephen Grabowski", ""), P("Festus", "Engineer")],
        edges=[Edge(src="Stephen", rel="founded", dst="Axel", evidence="e"), Edge(src="Festus", rel="works_at", dst="Axel", evidence="e")],
    )
    soft = tidy(ex, drop_incomplete=False)
    assert [(p.name, p.role) for p in soft.people] == [("Stephen Grabowski", "Founder & CEO"), ("Festus", "Engineer")]
    final = tidy(ex)
    assert [p.name for p in final.people] == ["Stephen Grabowski"]
    assert [(e.src, e.rel) for e in final.edges] == [("Stephen Grabowski", "founded")]
