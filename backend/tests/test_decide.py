import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from decide import decisions
from decide.jev import JevProvider, ProviderError, build_request, parse_answers
from decide.local import LocalProvider
from decide.policy import decide_lead
from decide.protocol import Answer, choice, noul, score
from decide.registry import STATS, FallbackProvider, get_provider, reset_stats
from discovery import Candidate
from outcomes import load_outcomes, mark

FIX = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 10, 20, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def local():
    return LocalProvider(model_path="/nonexistent")  # zero-shot only (no learned head)


# --- local provider: protocol shape + real separation ---------------------------------------------------


def test_local_answers_have_the_system_one_shape(local):
    qs = [
        choice("kind", "what is it?", {"funding": "a startup raises money", "guide": "a how-to tutorial"}),
        score("urgency", "how urgent?", ["can wait", "this week", "today"]),
        noul("is_startup", "startup?", decisions.STARTUP_TRUE, decisions.STARTUP_FALSE),
    ]
    out = local.decide("Acme raises a $3M seed round to build search for lawyers", qs)
    assert out["kind"].choice == "funding" and abs(sum(out["kind"].probabilities.values()) - 1) < 1e-6
    assert 0 <= out["urgency"].score <= 2 and set(out["urgency"].probabilities) == {"0", "1", "2"}
    assert 0 <= out["is_startup"].noul <= 1 and out["is_startup"].type == "noul"


POS = ["Tako, AI search startup, raises $5.75 million seed round led by A*", "Launch HN: Laminar (YC S24) – RL-trained model that finds errors in agent traces",
       "Chariot raises seed to stop hidden fees and subscriptions", "machine0: Cloud computers for AI agents", "Fini: an AI teammate for your support team"]
NEG = ["10 Best Vector Databases for 2026", "Show HN: The Lion King (SNES, 1994), running as a native PC program", "Show HN: Roadkill – a zombie car game inspired by GTA",
       "Ramp reaches $60B valuation as it pushes deeper into AI", "The Zelda timeline to catch up before the Ocarina of Time remake"]


def test_triage_scores_rank_real_startups_above_junk(local):
    def cand(t, src="rss"):
        return Candidate(url="https://x.com", title=t, snippet="", source=src)

    pos = decisions.triage_scores([cand(t) for t in POS], local)
    neg = decisions.triage_scores([cand(t) for t in NEG], local)
    assert min(pos) > max(neg)  # perfectly separated on this set
    assert min(pos) >= 6 and max(neg) <= 4


def test_source_prior_and_prefix_stripping(local):
    same = "Show HN: Acme – semantic search for contracts"
    hn = decisions.triage_scores([Candidate("u", same, "", "hn")], local)[0]
    launch = decisions.triage_scores([Candidate("u", same, "", "launch_hn")], local)[0]
    assert launch > hn
    assert decisions.candidate_state("Show HN: Foo", "5 points on Hacker News", "hn") == "Foo"  # points aren't content
    assert decisions.candidate_state("Acme raises", "A seed round", "rss") == "Acme raises. A seed round"


def test_page_gate_never_blocks_real_startup_pages(local):
    """The critical property: a false negative loses a lead, so real startup pages must always pass.

    (The local zero-shot decider is weak at *blocking* guides - e.g. it scores a 'pre-seed startups' list page high -
    while Jev blocks them; see CLAUDE.md. Sharp blocking is tested with a fake provider below.)
    """
    for name in ("bw_tako", "tc_cedardb", "yc_machine0"):
        g = decisions.gate_page((FIX / f"{name}.md").read_text(), local)
        assert g.ok, (name, g)
    assert not decisions.gate_page((FIX / "junk_guide2.md").read_text(), local).ok


COOKIE_PAGE = """We respect your right to privacy. You can choose not to allow some types of cookies. Accept all cookies.

* News * Insights * Subscribe to Newsletters * Sign in

Copenhagen-based Plinto has raised EUR 2.9 million in a pre-seed round to help finance teams catch and fix errors with AI agents, the startup announced on Tuesday.

The round was led by Nordic investors and will fund hiring across engineering and go-to-market for the company's product.
"""


def test_gate_judges_the_article_not_cookie_banners_and_menus():
    assert decisions.article_text(COOKIE_PAGE).startswith("Copenhagen-based Plinto has raised EUR 2.9 million")
    assert "cookie" not in decisions.article_text(COOKIE_PAGE).lower() and "Subscribe" not in decisions.article_text(COOKIE_PAGE)

    class Spy:
        name = "spy"
        states: list = []

        def decide(self, state, questions):
            self.states.append(state)
            # a sharp classifier: only says yes when the text really is about a startup raising money
            return {"startup": Answer("noul", noul=0.95 if "raised EUR" in state and "cookie" not in state.lower() else 0.02)}

    spy = Spy()
    g = decisions.gate_page(COOKIE_PAGE, spy, title="Show HN: Plinto raises EUR 2.9M")
    assert g.ok and spy.states[0].startswith("Plinto raises EUR 2.9M.") and "Copenhagen-based Plinto" in spy.states[0]
    # regression: judging the raw top of the page (cookie banner) is what wrongly skipped real funding stories in CI
    assert spy.decide(decisions.page_head("cookie banner " * 50), [decisions.STARTUP])["startup"].noul < 0.1


def test_article_text_falls_back_to_the_raw_top_when_nothing_looks_like_prose():
    assert decisions.page_head("short bits | of | nav") == "short bits | of | nav"


def test_learned_head_blends_in_only_with_enough_labels(tmp_path, local):
    state = "Show HN: My Personal Weather Station"  # zero-shot says hobby project
    e = local.embedding(state)
    base = local.decide(state, [decisions.STARTUP])["startup"].noul
    assert base < 0.3

    p = tmp_path / "m.json"
    p.write_text(json.dumps({"heads": {"startup": {"w": (e * 20).tolist(), "b": 0.0, "n": 200}}}))  # learned: "yes"
    boosted = LocalProvider(model_path=p).decide(state, [decisions.STARTUP])["startup"].noul
    assert boosted > base + 0.4  # 200 labels -> the head gets most of the vote

    p.write_text(json.dumps({"heads": {"startup": {"w": (e * 20).tolist(), "b": 0.0, "n": 3}}}))  # too few labels
    assert LocalProvider(model_path=p).decide(state, [decisions.STARTUP])["startup"].noul == base


# --- Jev provider: request contract, parsing, fallback ---------------------------------------------------


def test_jev_request_matches_documented_system_one_shape():
    req = build_request("jev-latest", "some state", [
        noul("startup", "Is it?", "a || b", "c"), choice("kind", "kind?", {"x": "an x", "y": "a y"}), score("u", "urgent?", ["low", "high"]),
    ])
    assert req["model"] == "jev-latest" and req["state"] == "some state"
    assert req["questions"]["startup"] == {"type": "noul", "instructions": "Is it?", "criteria": {"true": "a; b", "false": "c"}}
    assert req["questions"]["kind"]["criteria"] == {"x": "an x", "y": "a y"}
    assert req["questions"]["u"]["criteria"] == ["low", "high"]


def test_jev_parses_documented_response():
    out = parse_answers({"answers": {
        "c": {"type": "noul", "noul": 0.97},
        "t": {"type": "choice", "choice": "calm", "confidence": 0.7, "probabilities": {"angry": 0.2, "calm": 0.8}},
        "u": {"type": "score", "score": 1.8, "confidence": 0.6, "legend": {"0": "a"}, "probabilities": {"0": 0.05, "1": 0.15, "2": 0.8}},
    }, "usage": {"input_tokens": 120}})
    assert out["c"].noul == 0.97 and out["t"].choice == "calm" and out["u"].score == 1.8


def _jev(handler, key="k"):
    return JevProvider(api_key=key, client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_jev_sends_bearer_key_to_systemone_and_counts_tokens():
    seen = {}

    def handler(request):
        seen["url"], seen["auth"], seen["body"] = str(request.url), request.headers["authorization"], json.loads(request.content)
        return httpx.Response(200, json={"model": "jev-1", "answers": {"startup": {"type": "noul", "noul": 0.9}}, "usage": {"input_tokens": 50, "output_tokens": 1}})

    jev = _jev(handler)
    out = jev.decide("state", [noul("startup", "q", "t", "f")])
    assert seen["url"] == "https://api.typesafe.ai/v1/systemone" and seen["auth"] == "Bearer k"
    assert out["startup"].noul == 0.9 and jev.input_tokens == 50 and seen["body"]["model"] == "jev-latest"


def test_jev_never_calls_out_without_a_key_and_errors_fall_back_to_local(local, monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    calls = []
    keyless = _jev(lambda r: calls.append(r) or httpx.Response(200, json={}), key="")
    with pytest.raises(ProviderError):
        keyless.decide("s", [noul("startup", "q", "t", "f")])
    assert calls == []  # no key -> no network

    reset_stats("jev")
    failing = _jev(lambda r: httpx.Response(503, text="down"))
    fb = FallbackProvider(failing, local)
    ans = fb.decide("Acme raises a seed round", [decisions.STARTUP])
    assert 0 <= ans["startup"].noul <= 1 and STATS["fallbacks"] == 1 and STATS["calls"] == 1

    bad_shape = _jev(lambda r: httpx.Response(200, json={"answers": {}}))
    with pytest.raises(ProviderError):
        bad_shape.decide("s", [noul("startup", "q", "t", "f")])


def test_registry_defaults_to_local_and_jev_is_opt_in(monkeypatch):
    from decide import registry

    registry._cache.clear()
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.delenv("CALI_DECIDER", raising=False)
    assert get_provider().name == "local"
    assert get_provider("auto").name == "local"  # auto without a key stays local
    assert get_provider("jev").name == "local"  # jev requested but no key -> local, nothing paid
    monkeypatch.setenv("TYPESAFE_API_KEY", "secret")
    registry._cache.clear()
    assert get_provider("auto").name == "jev"
    registry._cache.clear()


# --- lead policy --------------------------------------------------------------------------------------


def lead(**kw):
    # every stored address carries its source page (CLAUDE.md), and contact_now needs one on the company's own domain
    base = {"company_name": "Acme", "website": "https://acme.io", "source_url": "https://news.ycombinator.com/item?id=1",
            "score": 80, "gaps": [], "discovered_at": (NOW - timedelta(days=2)).isoformat(),
            "contact": {"emails": [{"value": "hi@acme.io", "kind": "general", "source_url": "https://acme.io/contact"}],
                        "phones": [], "contact_page": "https://acme.io/contact"},
            "people": [{"name": "Jane Roe", "role": "CEO", "linkedin": "https://linkedin.com/in/jane-roe"}]}
    base.update(kw)
    return base


def test_fresh_strong_reachable_lead_is_hot_contact_now():
    d = decide_lead(lead(), now=NOW)
    assert (d["action"], d["urgency"]) == ("contact_now", "hot") and "hi@acme.io" in d["next_step"] and d["priority"] > 80


def test_staleness_and_reachability_change_the_decision():
    assert decide_lead(lead(discovered_at=(NOW - timedelta(days=60)).isoformat()), now=NOW)["action"] == "watch"
    warm = decide_lead(lead(discovered_at=(NOW - timedelta(days=15)).isoformat()), now=NOW)
    assert (warm["action"], warm["urgency"]) == ("contact_now", "warm")
    no_contact = decide_lead(lead(score=50, contact={}, people=[]), now=NOW)
    assert no_contact["action"] == "enrich_more"
    social_only = decide_lead(lead(score=60, contact={}), now=NOW)
    # spec change (2026-11-06): outreach is email-only (CLAUDE.md), so a profile link is never offered as the channel
    assert social_only["action"] != "contact_now" and "LinkedIn" not in social_only["next_step"]
    review = decide_lead(lead(score=60), now=NOW)  # reachable but below the unattended-send bar
    assert review["action"] == "review" and "hi@acme.io" in review["next_step"]
    publisher = decide_lead(lead(website="https://news.ycombinator.com",
                                 contact={"emails": [{"value": "hn@ycombinator.com", "kind": "general", "source_url": "https://news.ycombinator.com/"}]}), now=NOW)
    assert publisher["action"] != "contact_now"
    assert decide_lead(lead(score=20), now=NOW)["action"] == "skip"


def test_priority_orders_fresh_reachable_above_stale():
    a = decide_lead(lead(score=75), now=NOW)["priority"]
    b = decide_lead(lead(score=75, discovered_at=(NOW - timedelta(days=90)).isoformat()), now=NOW)["priority"]
    assert a > b


def test_your_outcomes_override_the_policy(tmp_path):
    mark("Acme", "contacted", "emailed", tmp_path, now=NOW - timedelta(days=3))
    out = load_outcomes(tmp_path)["acme"]
    assert decide_lead(lead(), out, NOW)["action"] == "watch"  # waiting on a reply
    mark("Acme", "contacted", "", tmp_path, now=NOW - timedelta(days=9))
    assert decide_lead(lead(), load_outcomes(tmp_path)["acme"], NOW)["action"] == "follow_up"
    mark("Acme", "passed", "", tmp_path, now=NOW)
    assert decide_lead(lead(), load_outcomes(tmp_path)["acme"], NOW)["action"] == "skip"
    with pytest.raises(ValueError):
        mark("Acme", "maybe", data_dir=tmp_path)


def test_done_or_waiting_leads_sink_below_actionable_ones(tmp_path):
    actionable = decide_lead(lead(score=60), now=NOW)["priority"]
    mark("Acme", "replied", "", tmp_path, now=NOW - timedelta(days=1))
    waiting = decide_lead(lead(score=95), load_outcomes(tmp_path)["acme"], NOW)["priority"]
    mark("Acme", "passed", "", tmp_path, now=NOW)
    done = decide_lead(lead(score=95), load_outcomes(tmp_path)["acme"], NOW)["priority"]
    assert actionable > waiting > done


def test_pass_reason_is_stored_validated_and_shown(tmp_path):
    out = mark("Acme", "passed", "", tmp_path, now=NOW, reason="wrong_stage")
    assert out["reason"] == "wrong_stage"
    assert any("wrong stage" in r for r in decide_lead(lead(), load_outcomes(tmp_path)["acme"], NOW)["reasons"])
    with pytest.raises(ValueError):
        mark("Acme", "passed", data_dir=tmp_path, reason="because")
    with pytest.raises(ValueError):
        mark("Acme", "contacted", data_dir=tmp_path, reason="wrong_stage")
    assert mark("Acme", "contacted", data_dir=tmp_path, now=NOW)["reason"] == ""
