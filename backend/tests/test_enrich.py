import json

import pytest

import enrich
from enrich import (
    EnrichResult, Fetched, build_contact, classify_social, enrich_startup, match_person_links, name_matches_slug,
    parse_page, pick_pages, resolve_website, search_person_links,
)
from models import Edge, Extraction, Person, StartupProfile

HOME = """<html><head>
<script type="application/ld+json">{"@type":"Organization","name":"Acme","telephone":"+1 415 555 0132",
"email":"mailto:hello@acme.io","sameAs":["https://www.linkedin.com/company/acme-io","https://x.com/acme_io"],
"address":{"@type":"PostalAddress","addressLocality":"Berlin","addressCountry":"Germany"}}</script></head>
<body><nav><a href="/about">About</a><a href="/contact-us">Contact</a><a href="/pricing">Pricing</a></nav>
<a href="https://github.com/acme-io">GitHub</a>
<footer>Questions? <a href="mailto:sales@acme.io?subject=Hi">Sales</a> or write support [at] acme [dot] io.
Call us: +44 20 7946 0958. Image: logo@2x.png. <a href="mailto:noreply@acme.io">x</a></footer></body></html>"""

TEAM = """<html><body><h1>Team</h1>
<div><a href="https://www.linkedin.com/in/jane-roe-1a2b3c">Jane Roe</a> CEO <a href="https://x.com/janeroe">@janeroe</a></div>
<div><a href="https://github.com/bsmith">Bob Smith</a>, CTO</div>
<div><a href="https://www.linkedin.com/in/x9f8e7">Priya Raman</a></div>
<div><a href="https://x.com/share?url=foo">share</a> <a href="https://github.com/features">gh</a></div>
</body></html>"""


def test_parse_page_extracts_emails_phones_and_ignores_junk():
    f = parse_page("https://acme.io/", HOME)
    emails = dict(f.emails)
    assert emails["sales@acme.io"] == "sales"
    assert emails["support@acme.io"] == "support"  # de-obfuscated "[at]/[dot]"
    assert "noreply@acme.io" not in emails and not any("2x.png" in e for e in emails)
    assert "+442079460958" in f.phones


def test_build_contact_uses_jsonld_and_socials_and_orders_by_kind():
    pages = [parse_page("https://acme.io/", HOME)]
    c = build_contact("https://acme.io", pages)
    assert [e.value for e in c.emails][:2] == ["hello@acme.io", "sales@acme.io"]  # general first, then sales
    assert all(e.source_url == "https://acme.io/" for e in c.emails)
    assert {p.value for p in c.phones} == {"+14155550132", "+442079460958"}
    assert c.socials == {"linkedin": "https://www.linkedin.com/company/acme-io", "twitter": "https://x.com/acme_io", "github": "https://github.com/acme-io"}
    assert c.status == "ok" and c.website == "https://acme.io"
    assert enrich.jsonld_hq(pages) == "Berlin, Germany"


def test_never_invents_emails_when_page_has_none():
    c = build_contact("https://x.io", [parse_page("https://x.io/", "<html><body>No contact here</body></html>")])
    assert c.emails == [] and c.phones == []


def test_classify_social():
    assert classify_social("https://www.linkedin.com/in/jane-roe-1a2b3c/") == ("linkedin", "user", "https://www.linkedin.com/in/jane-roe-1a2b3c")
    assert classify_social("https://linkedin.com/company/acme")[1] == "company"
    assert classify_social("https://twitter.com/janeroe")[2] == "https://x.com/janeroe"
    assert classify_social("https://x.com/share?url=1") is None
    assert classify_social("https://github.com/features") is None
    assert classify_social("https://github.com/org/repo") is None  # repo, not a profile


@pytest.mark.parametrize(
    "name,slug,ok",
    [
        ("Jane Roe", "jane-roe-1a2b3c", True),
        ("Jane Roe", "janeroe", True),
        ("Jane Roe", "jroe", True),  # initial + last name
        ("Jane Roe", "x9f8e7", False),
        ("Moritz Sichert", "moritzsichert", True),
        ("Zoë Tanaka", "zoe-tanaka", True),
        ("Cher", "cher", False),  # single token can't be matched safely
    ],
)
def test_name_matches_slug(name, slug, ok):
    assert name_matches_slug(name, slug) is ok


def test_match_person_links_from_team_page_by_slug_or_anchor_text():
    pages = [parse_page("https://acme.io/team", TEAM)]
    jane = match_person_links(Person(name="Jane Roe", evidence="e"), pages)
    assert jane["linkedin"][0] == "https://www.linkedin.com/in/jane-roe-1a2b3c" and jane["twitter"][0] == "https://x.com/janeroe"
    assert jane["linkedin"][1] == "https://acme.io/team"
    bob = match_person_links(Person(name="Bob Smith", evidence="e"), pages)
    assert bob == {"github": ("https://github.com/bsmith", "https://acme.io/team")}
    priya = match_person_links(Person(name="Priya Raman", evidence="e"), pages)  # opaque slug, but anchor text has the name
    assert priya["linkedin"][0] == "https://www.linkedin.com/in/x9f8e7"
    assert match_person_links(Person(name="Someone Else", evidence="e"), pages) == {}


def test_search_person_links_requires_matching_handle():
    results = [
        {"href": "https://www.linkedin.com/in/john-doe-77", "title": "John Doe - Engineer | LinkedIn", "body": ""},
        {"href": "https://www.linkedin.com/in/jane-roe-1a2b3c", "title": "Jane Roe - CEO - Acme | LinkedIn", "body": ""},
    ]
    p = Person(name="Jane Roe", evidence="e")
    assert search_person_links(p, "Acme", lambda q: results, platforms=("linkedin",)) == {"linkedin": ("https://www.linkedin.com/in/jane-roe-1a2b3c", "search")}
    assert search_person_links(Person(name="Max Power", evidence="e"), "Acme", lambda q: results, platforms=("linkedin",)) == {}

    def boom(q):
        raise RuntimeError("blocked")

    assert search_person_links(p, "Acme", boom) == {}  # search failures are non-fatal


def test_resolve_website_priority_and_guards():
    md = "Read more at [CedarDB](https://cedardb.com/) and [TC](https://techcrunch.com/x) https://twitter.com/cedardb"
    assert resolve_website("CedarDB", "", "https://techcrunch.com/a", "rss", md) == "https://cedardb.com"
    assert resolve_website("CedarDB", "https://www.cedardb.com/about", "https://techcrunch.com/a", "rss", "") == "https://www.cedardb.com"
    # the article host / social hosts are never a company site
    assert resolve_website("Acme", "https://techcrunch.com/acme", "https://techcrunch.com/a", "rss", "") == ""
    # a Show HN landing page is the product's own site
    assert resolve_website("Maali", "", "https://maali.app/", "hn", "no links") == "https://maali.app"
    assert resolve_website("Maali", "", "https://github.com/x/y", "hn", "") == ""
    # search fallback only accepts a host that contains the company token
    hits = lambda q: [{"href": "https://blog.example.org/post"}, {"href": "https://www.acmerobotics.com/"}]  # noqa: E731
    assert resolve_website("Acme Robotics", "", "https://tc.com/a", "rss", "", search_fn=hits) == "https://www.acmerobotics.com"


def test_pick_pages_prefers_discovered_team_and_contact_links():
    home = parse_page("https://acme.io/", HOME)
    assert pick_pages("https://acme.io", home) == ["https://acme.io/", "https://acme.io/about", "https://acme.io/contact-us"]
    assert pick_pages("https://x.io", None) == ["https://x.io/", "https://x.io/contact", "https://x.io/about", "https://x.io/team"]


def _ex():
    return Extraction(
        startup=StartupProfile(company_name="Acme", core_product="Search", tech_stack=["Go"], likely_bottleneck="x", value_prop_pitch="One. Two.", is_relevant=True, source_url="https://tc.com/acme"),
        people=[Person(name="Jane Roe", role="CEO", org="Acme", evidence="Jane Roe is CEO")],
        edges=[Edge(src="Jane Roe", rel="founded", dst="Acme", evidence="Jane Roe founded Acme")],
    )


async def test_enrich_startup_end_to_end_with_fakes():
    calls = []

    async def fake_fetch(urls):
        calls.append(urls)
        pages = {"https://acme.io/": HOME, "https://acme.io/about": TEAM, "https://acme.io/contact-us": "<html>contact</html>"}
        return [Fetched(u, pages[u], "# Team\nBob Smith is CTO at Acme.") for u in urls if u in pages]

    def fake_extract(md):
        return Extraction(
            startup=_ex().startup,
            people=[Person(name="Bob Smith", role="CTO", evidence="Bob Smith is CTO at Acme"),
                    Person(name="Ghost Writer", role="CFO", evidence="Ghost Writer is CFO at Acme")],  # not on the page
            edges=[Edge(src="Bob Smith", rel="works_at", dst="Acme", evidence="Bob Smith is CTO at Acme")],
        )

    ex = _ex()
    ex.startup.website = "https://acme.io"
    res = await enrich_startup(ex, "rss", "see https://acme.io", fetch_fn=fake_fetch, extract_fn=fake_extract, team_budget=[1])
    assert isinstance(res, EnrichResult) and res.contact.status == "ok"
    assert res.extraction.startup.website == "https://acme.io" and res.extraction.startup.hq == "Berlin, Germany"
    assert [e.value for e in res.contact.emails][0] == "hello@acme.io"
    names = {p.name: p for p in res.extraction.people}
    assert set(names) == {"Jane Roe", "Bob Smith"}  # ungrounded "Ghost Writer" dropped
    assert names["Bob Smith"].org == "Acme" and names["Bob Smith"].github == "https://github.com/bsmith"
    assert names["Jane Roe"].linkedin.endswith("jane-roe-1a2b3c") and names["Jane Roe"].link_source == "https://acme.io/about"
    assert len(res.extraction.edges) == 2
    assert calls[0] == ["https://acme.io/"]  # homepage first, then the discovered pages


async def test_enrich_startup_without_website_or_with_crawl_failure():
    ex = _ex()
    res = await enrich_startup(ex, "rss", "no site mentioned", fetch_fn=None)
    assert res.contact.status == "no_website" and res.contact.emails == []

    ex.startup.website = "https://acme.io"

    async def empty_fetch(urls):
        return []

    res = await enrich_startup(ex, "rss", "", fetch_fn=empty_fetch)
    assert res.contact.status == "crawl_failed" and res.contact.website == "https://acme.io"


async def test_people_search_budget_is_respected():
    ex = _ex()
    seen = []

    def search(q):
        seen.append(q)
        return []

    budget = [1]
    await enrich_startup(ex, "rss", "no site", search_fn=search, search_budget=budget)
    profile_searches = [q for q in seen if "site:" in q]  # (the first query resolves the website)
    assert len(profile_searches) == 1 and budget == [0]  # one LinkedIn query per leader; never beyond the budget


async def test_redirected_site_is_canonicalised_so_contacts_and_website_agree():
    async def fake_fetch(urls):
        if urls == ["https://trytako.com/"]:
            return [Fetched("https://tako.com/", HOME, "")]  # trytako.com redirects to tako.com
        return []

    ex = _ex()
    ex.startup.website = "https://trytako.com"
    res = await enrich_startup(ex, "rss", "see https://trytako.com", fetch_fn=fake_fetch)
    assert res.extraction.startup.website == "https://tako.com" and res.contact.website == "https://tako.com"
