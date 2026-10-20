import json
from types import SimpleNamespace

import feedparser

from discovery import Candidate, normalize_url
from discovery import hn, rss, web, yc
from discovery.planner import FALLBACK, make_plan
from discovery.triage import heuristic_filter, select


class FakeClient:
    def __init__(self, payload=None, error=None):
        self.payload, self.error = payload, error
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        if self.error:
            raise self.error
        msg = SimpleNamespace(content=json.dumps(self.payload))
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def test_normalize_url():
    assert normalize_url("https://www.Example.com/a/b/?utm_source=x&id=3#frag") == "example.com/a/b?id=3"
    assert normalize_url("http://example.com/a") == normalize_url("https://www.example.com/a/")


def test_hn_parse_skips_text_posts():
    payload = {"hits": [
        {"title": "Show HN: Foo", "url": "https://foo.dev", "points": 12, "created_at": "2026-10-19"},
        {"title": "Show HN: Ask-ish", "url": None, "points": 9},
    ]}
    cands = hn.parse_hits(payload)
    assert [c.url for c in cands] == ["https://foo.dev"] and cands[0].source == "hn"


RSS = """<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Acme raises $5M seed round</title><link>https://tc.com/acme</link><description>&lt;p&gt;Search startup&lt;/p&gt;</description></item>
<item><title>Why the market is volatile</title><link>https://tc.com/market</link><description>Opinion</description></item>
</channel></rss>"""


def test_rss_keeps_only_funding_items():
    cands = rss.parse_feed(feedparser.parse(RSS))
    assert [c.url for c in cands] == ["https://tc.com/acme"]
    assert cands[0].snippet == "Search startup"


def test_yc_listing_parse_dedupes():
    html = '<a href="/launches/AbC-foo-ai">x</a><a href="/launches/AbC-foo-ai">y</a><a href="/launches/Xyz-bar">z</a>'
    cands = yc.parse_listing(html)
    assert [c.title for c in cands] == ["foo ai", "bar"]
    assert cands[0].url == "https://www.ycombinator.com/launches/AbC-foo-ai"


def test_web_fetch_maps_search_results(monkeypatch):
    monkeypatch.setattr(web, "search_results", lambda q, n, attempts: [{"href": "https://x.io", "title": "T", "body": "B"}])
    c = web.fetch(["q1"])[0]
    assert (c.url, c.title, c.snippet, c.source) == ("https://x.io", "T", "B", "web")


def test_planner_uses_llm_plan_and_falls_back_on_error():
    plan = make_plan(FakeClient({"web_queries": ["a", "b"], "hn_keywords": ["rag"]}))
    assert plan.web_queries == ["a", "b"] and plan.hn_keywords == ["rag"]
    assert make_plan(FakeClient(error=RuntimeError("boom"))) == FALLBACK
    assert make_plan(FakeClient({"web_queries": []})) == FALLBACK


def cand(url, title="Acme launches", source="hn"):
    return Candidate(url=url, title=title, snippet="", source=source)


def test_heuristic_filter_drops_seen_dupes_blocked_and_listicles():
    cands = [
        cand("https://a.com/x"),
        cand("https://www.a.com/x/?utm_source=z"),  # duplicate after normalising
        cand("https://youtube.com/watch?v=1"),
        cand("https://b.com/p", title="How to launch on Hacker News: a guide"),
        cand("https://seen.com/p"),
        cand("https://c.com/p"),
    ]
    out = heuristic_filter(cands, seen={normalize_url("https://seen.com/p")})
    assert [c.url for c in out] == ["https://a.com/x", "https://c.com/p"]


def test_select_ranks_by_llm_score_and_drops_low(monkeypatch):
    cands = [cand("https://a.com", source="hn"), cand("https://b.com", source="rss"), cand("https://c.com", source="yc")]
    client = FakeClient({"scores": [{"i": 0, "score": 3}, {"i": 1, "score": 9}, {"i": 2, "score": 6}]})
    assert [c.url for c in select(cands, set(), client)] == ["https://b.com", "https://c.com"]


def test_select_caps_per_source(monkeypatch):
    monkeypatch.setattr("discovery.triage.PER_SOURCE_CAP", 2)
    cands = [cand(f"https://s{i}.com") for i in range(5)]
    client = FakeClient({"scores": [{"i": i, "score": 8} for i in range(5)]})
    assert len(select(cands, set(), client)) == 2


def test_select_survives_llm_failure():
    cands = [cand("https://a.com"), cand("https://b.com")]
    assert len(select(cands, set(), FakeClient(error=RuntimeError("down")))) == 2


def test_launch_hn_posts_become_inline_candidates_without_crawling():
    payload = {"hits": [
        {"objectID": "1", "title": "Launch HN: Laminar (YC S24) – agent observability", "points": 55,
         "story_text": "Hi HN, we&#x27;re Robert and Din from Laminar (<a href=\"https://laminar.sh\">https://laminar.sh</a>).<p>We build X.",
         "created_at": "2026-10-19"},
        {"objectID": "2", "title": "Launch HN: No text", "story_text": ""},
        {"objectID": "3", "title": "Show HN: not a launch", "story_text": "hello"},
    ]}
    cands = hn.parse_launch(payload)
    assert [c.url for c in cands] == ["https://news.ycombinator.com/item?id=1"]
    c = cands[0]
    assert c.source == "launch_hn" and c.content.startswith("# Launch HN: Laminar")
    assert "[https://laminar.sh](https://laminar.sh)" in c.content and "we're Robert and Din" in c.content


def test_shortlist_round_robins_sources_and_caps():
    from discovery.triage import shortlist

    cands = [cand(f"https://a{i}.com", source="rss") for i in range(10)] + [cand(f"https://b{i}.com", source="hn") for i in range(2)]
    out = shortlist(cands, n=5)
    assert [c.source for c in out] == ["rss", "hn", "rss", "hn", "rss"]  # the small source isn't crowded out
    assert len(shortlist(cands, n=100)) == 12


def test_select_honours_per_source_caps_from_feedback():
    cands = [cand(f"https://r{i}.com", source="rss") for i in range(4)] + [cand(f"https://h{i}.com", source="hn") for i in range(4)]
    client = FakeClient({"scores": [{"i": i, "score": 8} for i in range(8)]})
    picked = select(cands, set(), client, caps={"rss": 3, "hn": 1})
    assert sorted(c.source for c in picked) == ["hn", "rss", "rss", "rss"]
