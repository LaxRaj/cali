from datetime import datetime, timezone

from gtm import run_gtm
from gtm.hn_check import hn_check, parse_launch
from gtm.score import decay, score_checks
from gtm.webapp_check import webapp_check
from models import Person
from whynow import why_now

NOW = datetime(2026, 10, 20, tzinfo=timezone.utc)


def hit(title="Launch HN: Acme (YC S26)", url="https://acme.io/x", created="2026-10-10T00:00:00Z", ts=1760054400, pts=120, com=40):
    return {"title": title, "url": url, "created_at": created, "created_at_i": ts, "points": pts, "num_comments": com, "objectID": "42"}


def test_decay_halves_each_half_life():
    assert decay(60, 60) == 0.5 and decay(0, 60) == 1.0


def test_hn_launch_by_domain_is_hot_and_full_strength():
    [c] = parse_launch([hit()], "acme.io", "Acme", NOW)
    assert c["band"] == "hot" and c["age_days"] == 10 and c["strength"] == 1.0
    assert c["evidence_url"].endswith("id=42")


def test_hn_name_only_match_is_lower_confidence_and_other_domains_ignored():
    [c] = parse_launch([hit(url="https://other.dev")], "acme.io", "Acme", NOW)
    assert c["strength"] == 0.6
    assert parse_launch([hit(title="Ask HN: acme.io?", url="https://acme.io")], "acme.io", "Acme", NOW) == []
    assert parse_launch([hit(title="Show HN: Zed", url="https://zed.dev")], "acme.io", "Acme", NOW) == []


def test_recent_launch_outscores_old_launch():
    fresh = parse_launch([hit()], "acme.io", "Acme", NOW)
    old = parse_launch([hit(created="2024-01-01T00:00:00Z")], "acme.io", "Acme", NOW)
    assert score_checks(fresh) > score_checks(old) * 5
    assert old[0]["band"] == "cold"


def test_hn_check_never_fatal():
    class Boom:
        def get(self, *a, **k):
            raise RuntimeError("down")

    assert hn_check("https://acme.io", "Acme", NOW, client=Boom()) == []


LIVE = '<a href="/login">Log in</a><a href="/pricing">Pricing</a><footer>© 2026 Acme</footer>'
WAIT = "<h1>Coming soon</h1><p>Join the waitlist</p>"
NO_PRICE = '<a href="/signup">Get started</a><a href="https://app.acme.io">App</a>'


def test_webapp_stages():
    assert webapp_check([("https://acme.io/", LIVE)], NOW)[0] == "live_pricing"
    assert webapp_check([("https://acme.io/", WAIT)], NOW)[0] == "pre_launch"
    assert webapp_check([("https://acme.io/", NO_PRICE)], NOW)[0] == "live_no_pricing"
    assert webapp_check([], NOW)[0] == "unknown"


def test_stale_footer_zeroes_the_live_credit():
    _, [c] = webapp_check([("https://acme.io/", LIVE.replace("2026", "2019"))], NOW)
    assert c["strength"] == 0.0 and "stale" in c["value"]


def test_router_skips_webapp_probe_for_cold_leads():
    out = run_gtm("https://acme.io", "Acme", [("https://acme.io/", LIVE)], {}, [], [], hn_fn=lambda *a: [], now=NOW)
    assert out["stage"] == "unknown" and not any(c["name"] == "webapp_live" for c in out["checks"])


def test_router_escalates_on_hn_launch_and_scores_every_check_with_evidence():
    out = run_gtm(
        "https://acme.io", "Acme", [("https://acme.io/", NO_PRICE)], {"linkedin": "https://linkedin.com/company/acme"},
        [Person(name="Jane Roe", evidence="e", linkedin="https://linkedin.com/in/jane-roe", link_source="https://acme.io/team")],
        [{"type": "hiring", "url": "https://boards.greenhouse.io/acme", "roles": ["Account Executive"], "role_kinds": ["sales"], "posted_at": "2026-10-15T00:00:00Z"}],
        hn_fn=lambda *a: parse_launch([hit()], "acme.io", "Acme", NOW), now=NOW,
    )
    assert out["stage"] == "live_no_pricing" and out["score"] > 4
    assert {c["name"] for c in out["checks"]} == {"hiring", "linkedin", "hn_launch", "webapp_live"}
    assert all(c["evidence_url"] for c in out["checks"])


def test_why_now_uses_gtm_checks():
    gtm = run_gtm("https://acme.io", "Acme", [("https://acme.io/", NO_PRICE)], {}, [], [],
                  hn_fn=lambda *a: parse_launch([hit()], "acme.io", "Acme", NOW), now=NOW)
    kinds = [s["signal"] for s in why_now({"gtm": gtm, "source_url": "", "discovered_at": "2020-01-01"}, NOW)]
    assert kinds == ["hn_launch", "live_product"]
