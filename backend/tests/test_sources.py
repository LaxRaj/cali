import json
from pathlib import Path

import httpx
import pytest

from discovery import edgar, hiring, triage
from discovery import Candidate
from enrich import resolve_website
from enrich_github import enrich_people_github, login_of
from models import Person

FIX = Path(__file__).parent / "fixtures"
FORM_D = (FIX / "form_d_nocturnal.xml").read_text()

ATOM = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>D - Nocturnal Inc. (0002042126) (Filer)</title><link href="https://www.sec.gov/Archives/edgar/data/2042126/000204212626000003/0002042126-26-000003-index.htm"/><updated>2026-10-20T13:45:27-04:00</updated></entry>
<entry><title>D/A - Amended Co (0001111111) (Filer)</title><link href="https://www.sec.gov/Archives/edgar/data/1/2/x-index.htm"/><updated>2026-10-20T13:00:00-04:00</updated></entry>
<entry><title>DEF 14A - Some Trust (0002222222) (Filer)</title><link href="https://www.sec.gov/x-index.htm"/><updated>2026-10-20T12:00:00-04:00</updated></entry>
</feed>"""


# --- SEC Form D ---------------------------------------------------------------------------------------


def test_feed_keeps_new_form_d_filings_only():
    entries = edgar.parse_feed(ATOM)
    assert [e["issuer"] for e in entries] == ["Nocturnal Inc."]  # amendments and non-D forms are skipped
    assert entries[0]["folder"] == "https://www.sec.gov/Archives/edgar/data/2042126/000204212626000003"


def test_form_d_parse_extracts_company_amounts_and_officers():
    f = edgar.parse_form_d(FORM_D)
    assert f["issuer"] == "Nocturnal Inc." and f["sold"] == 1_850_000 and f["offering"] == 2_000_000 and f["investors"] == 9
    assert f["city"] == "Cambridge" and f["state"] == "MASSACHUSETTS" and f["year_inc"] == "2024" and f["recent"]
    assert f["people"] == [{"name": "Abhinandan Jain", "roles": ["Executive Officer", "Director"]}, {"name": "Rajeev Surati", "roles": ["Director"]}]


@pytest.mark.parametrize("patch", [
    ("Corporation", "Limited Partnership"), ("Other Technology", "Pooled Investment Fund"), ("Nocturnal Inc.", "Acme Growth Fund LP"),
    ("Nocturnal Inc.", "Duke Capital Partners 2609B, A Series of V360 Holdings LLC"),
])
def test_funds_and_vehicles_are_filtered_out(patch):
    assert edgar.parse_form_d(FORM_D.replace(*patch)) is None
    assert edgar.parse_form_d("<not xml") is None


def test_candidate_is_inline_content_grounded_in_the_filing():
    c = edgar.to_candidate(edgar.parse_form_d(FORM_D), "https://www.sec.gov/Archives/x/", "2026-10-20")
    assert c.source == "edgar" and c.title == "Nocturnal Inc. raises $1.85M (SEC Form D)"
    assert "- Abhinandan Jain — Executive Officer, Director" in c.content and "Cambridge, MASSACHUSETTS" in c.content
    assert "(857) 268-9423" in c.content and "Signed by Abhinandan Jain, President" in c.content
    assert triage.heuristic_filter([c], set()) == [c]  # content-bearing candidates bypass the host blocklist


def test_edgar_is_off_without_a_contact_email_and_sends_a_proper_user_agent(monkeypatch):
    monkeypatch.delenv("CALI_CONTACT_EMAIL", raising=False)
    assert edgar.user_agent() is None and edgar.fetch() == []  # no email -> no request at all

    monkeypatch.setenv("CALI_CONTACT_EMAIL", "ops@example.org")
    seen = []

    def handler(req):
        seen.append((str(req.url), req.headers["user-agent"]))
        return httpx.Response(200, text=ATOM if "browse-edgar" in str(req.url) else FORM_D)

    monkeypatch.setattr(edgar.time, "sleep", lambda s: None)
    out = edgar.fetch(httpx.Client(transport=httpx.MockTransport(handler), headers={"User-Agent": edgar.user_agent()}))
    assert [c.title for c in out] == ["Nocturnal Inc. raises $1.85M (SEC Form D)"]
    assert all("ops@example.org" in ua for _, ua in seen) and seen[1][0].endswith("/primary_doc.xml")


def test_edgar_survives_http_errors(monkeypatch):
    monkeypatch.setenv("CALI_CONTACT_EMAIL", "ops@example.org")
    assert edgar.fetch(httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503)))) == []


# --- HN Who is hiring ---------------------------------------------------------------------------------------


POST = ('Acme Search (YC S24) | Founding Backend Engineer | Remote (US) | $150-200k<p>We build semantic search for legal teams. '
        'Apply at <a href="https:&#x2F;&#x2F;acme.io&#x2F;jobs">https://acme.io/jobs</a> or email jobs@acme.io')


def test_hiring_post_parse_and_candidate():
    post = hiring.parse_post(POST)
    assert post["company"] == "Acme Search" and post["roles"] == "Founding Backend Engineer" and post["url"] == "https://acme.io/jobs"
    c = hiring.to_candidate(post, "123", "2026-10-02")
    assert c.source == "hiring" and c.url == "https://acme.io/jobs" and c.title.startswith("Acme Search is hiring")
    assert "jobs@acme.io" in c.content  # an address the company itself published


def test_hiring_ignores_free_text_and_non_engineering_roles():
    assert hiring.parse_post("Thanks for posting, interesting company!") is None
    sales = hiring.parse_post("BigCo | Regional Sales Manager | NYC")
    assert hiring.to_candidate(sales, "9") is None


def test_hiring_fetch_reads_latest_thread_top_level_comments_only():
    def handler(req):
        if "search_by_date" in str(req.url):
            return httpx.Response(200, json={"hits": [{"objectID": "500", "title": "Ask HN: Who wants to be hired? (October 2026)"},
                                                       {"objectID": "400", "title": "Ask HN: Who is hiring? (October 2026)"}]})
        return httpx.Response(200, json={"hits": [
            {"objectID": "1", "parent_id": 400, "comment_text": POST, "created_at": "2026-10-02"},
            {"objectID": "2", "parent_id": 1, "comment_text": POST},  # a reply, not a post
            {"objectID": "3", "parent_id": 400, "comment_text": "just chatting"},
        ]})

    out = hiring.fetch(httpx.Client(transport=httpx.MockTransport(handler)))
    assert [c.title for c in out] == ["Acme Search is hiring: Founding Backend Engineer"]
    assert hiring.fetch(httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500)))) == []


def test_edgar_and_hiring_candidates_resolve_their_websites():
    # a hiring post's first link IS the company site; an SEC filing is never the company site
    assert resolve_website("Acme Search", "", "https://acme.io/jobs", "hiring", "") == "https://acme.io"
    assert resolve_website("Nocturnal Inc.", "", "https://www.sec.gov/Archives/x/", "edgar", "") == ""


# --- GitHub profile enrichment ------------------------------------------------------------------------------


def _gh(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_github_enrichment_fills_blog_and_twitter_but_never_the_email():
    def handler(req):
        assert req.url.path == "/users/jroe"
        return httpx.Response(200, json={"login": "jroe", "blog": "jane.dev", "twitter_username": "jane_roe", "email": "jane@private.example", "location": "Berlin"})

    p = Person(name="Jane Roe", role="CEO", evidence="e", github="https://github.com/jroe")
    out = enrich_people_github([p], _gh(handler))[0]
    assert out.homepage == "https://jane.dev" and out.twitter == "https://x.com/jane_roe" and out.link_source == "github profile"
    assert "private.example" not in out.model_dump_json()


def test_github_enrichment_budget_errors_and_existing_values():
    calls = []

    def handler(req):
        calls.append(req.url.path)
        return httpx.Response(404) if "gone" in req.url.path else httpx.Response(200, json={"blog": "https://x.dev", "twitter_username": None})

    people = [Person(name="A B", evidence="e", github="https://github.com/gone"), Person(name="C D", evidence="e", github="https://github.com/cd"),
              Person(name="E F", evidence="e", github="https://github.com/ef"), Person(name="G H", evidence="e"),
              Person(name="I J", evidence="e", github="https://github.com/ij", homepage="https://mine.dev", twitter="https://x.com/ij")]
    out = enrich_people_github(people, _gh(handler), budget=[2])
    assert calls == ["/users/gone", "/users/cd"]  # budget of 2: ef is skipped; ij already complete; GH has no github link
    assert out[0].homepage == "" and out[1].homepage == "https://x.dev" and out[2].homepage == "" and out[4].homepage == "https://mine.dev"
    assert login_of("https://github.com/org/repo") == "" and login_of("https://github.com/jroe") == "jroe"


def test_hiring_skips_large_established_employers():
    big_site = hiring.parse_post('Rivian Automotive | Senior ML Engineer | Palo Alto<p>Apply: <a href="https://careers.rivian.com/jobs/1">link</a>')
    assert hiring.to_candidate(big_site, "1") is None  # corporate careers site
    boiler = hiring.parse_post("MegaCorp | Backend Engineer | NYC<p>We are an equal opportunity employer with 25,000+ employees worldwide.")
    assert hiring.to_candidate(boiler, "2") is None
    startup = hiring.parse_post('Tiny AI | Founding ML Engineer | Remote<p><a href="https://jobs.lever.co/tinyai">apply</a> seed-stage, 6 people')
    assert hiring.to_candidate(startup, "3") is not None  # ATS links (lever/greenhouse) are fine


# --- Form D: add the company's own website so the extractor can see what it builds ------------------------------


async def test_materialize_combines_filing_facts_with_the_companys_homepage():
    from enrich import Fetched

    cand = edgar.to_candidate(edgar.parse_form_d(FORM_D), "https://www.sec.gov/Archives/x/", "2026-10-20")
    assert cand.company == "Nocturnal Inc."
    searched, fetched = [], []

    def search(q):
        searched.append(q)
        return [{"href": "https://www.sec.gov/other"}, {"href": "https://www.nocturnal.ai/", "title": "Nocturnal"}]

    async def fetch(urls):
        fetched.extend(urls)
        return [Fetched("https://www.nocturnal.ai/", "<html/>", "# Nocturnal\n\nNocturnal builds night-vision analytics for warehouses. Our cameras and software help operations teams see what is happening on the floor overnight, flag safety issues, and reduce shrinkage across distribution centers.")]

    content = await edgar.materialize(cand, search_fn=search, fetch_fn=fetch)
    assert searched == ['"Nocturnal Inc." official website'] and fetched == ["https://www.nocturnal.ai/"]
    assert "Abhinandan Jain — Executive Officer, Director" in content  # filing facts kept (grounding for people)
    assert "Website: https://www.nocturnal.ai" in content and "night-vision analytics for warehouses" in content  # the product


async def test_materialize_gives_up_without_a_matching_website():
    from enrich import Fetched

    cand = edgar.to_candidate(edgar.parse_form_d(FORM_D), "https://www.sec.gov/Archives/x/")

    async def fetch_ok(urls):
        return [Fetched("https://www.nocturnal.ai/", "<html/>", "A totally different company about gardening.")]

    async def fetch_none(urls):
        return []

    async def fetch_boom(urls):
        raise RuntimeError("timeout")

    site = lambda q: [{"href": "https://www.nocturnal.ai/"}]  # noqa: E731
    assert await edgar.materialize(cand, search_fn=lambda q: [], fetch_fn=fetch_ok) is None  # no website found
    assert await edgar.materialize(cand, search_fn=site, fetch_fn=fetch_ok) is None  # homepage doesn't mention the company
    assert await edgar.materialize(cand, search_fn=site, fetch_fn=fetch_none) is None  # crawl failed
    assert await edgar.materialize(cand, search_fn=site, fetch_fn=fetch_boom) is None  # never raises into the pipeline


async def test_materialize_matches_company_names_written_with_spaces_or_hyphens():
    from enrich import Fetched

    form = edgar.parse_form_d(FORM_D.replace("Nocturnal Inc.", "ReservoirCo, Inc."))
    cand = edgar.to_candidate(form, "https://www.sec.gov/Archives/r/")

    async def fetch(urls):
        return [Fetched("https://reservoir-co.com/", "<html/>", "# Reservoir Co\n\nWe build reservoir monitoring software that helps water utilities track levels, predict shortages, and plan releases across dozens of reservoirs and treatment sites.")]

    out = await edgar.materialize(cand, search_fn=lambda q: [{"href": "https://reservoir-co.com/"}], fetch_fn=fetch)
    assert out and "reservoir monitoring software" in out


async def test_materialize_skips_placeholder_homepages_without_any_prose():
    from enrich import Fetched

    cand = edgar.to_candidate(edgar.parse_form_d(FORM_D), "https://www.sec.gov/Archives/x/")

    async def placeholder(urls):  # a real case: a website-builder stub page for a stealth company
        return [Fetched("https://www.nocturnal.ai/", "<html/>", "top of page\n\nLog In\n\n© 2025 by Nocturnal Inc. All rights reserved.\n\nbottom of page")]

    assert await edgar.materialize(cand, search_fn=lambda q: [{"href": "https://www.nocturnal.ai/"}], fetch_fn=placeholder) is None


def test_duplicate_filings_keep_the_largest_round():
    small = FORM_D.replace("<totalAmountSold>1850000</totalAmountSold>", "<totalAmountSold>1000</totalAmountSold>")
    forms = [edgar.parse_form_d(small), edgar.parse_form_d(FORM_D), edgar.parse_form_d(FORM_D.replace("Nocturnal Inc.", "Other Corp"))]
    cands = [edgar.to_candidate(f, f"https://www.sec.gov/{i}/") for i, f in enumerate(forms)]
    kept = edgar.dedupe(cands, {id(c): f for c, f in zip(cands, forms)})
    assert sorted(c.url for c in kept) == ["https://www.sec.gov/1/", "https://www.sec.gov/2/"]  # the $1.85M filing, not the $1K one
