import json

from paths import find_path, load_known

E = [
    {"src": "Ada", "rel": "previously_at", "dst": "Stripe", "evidence": "Ada ex-Stripe"},
    {"src": "Ada", "rel": "founded", "dst": "Acme", "evidence": "Ada founded Acme"},
    {"src": "Acme", "rel": "competitor_of", "dst": "Rival", "evidence": "rival"},
    {"src": "Bob", "rel": "founded", "dst": "Far", "evidence": "x"},
]


def test_two_hop_path_through_shared_employer():
    p = find_path(E, {"stripe"}, "Acme")
    assert [h["rel"] for h in p["hops"]] == ["previously_at", "founded"]
    assert p["via"] == "Stripe" and "2 steps" in p["summary"]
    assert p["hops"][0]["evidence"] == "Ada ex-Stripe"


def test_competitor_edges_are_not_intro_routes():
    assert find_path(E, {"rival"}, "Acme") is None


def test_no_known_or_unreachable_gives_none():
    assert find_path(E, set(), "Acme") is None
    assert find_path(E, {"stripe"}, "Far") is None


def test_hop_limit():
    chain = [{"src": f"n{i}", "rel": "works_at", "dst": f"n{i+1}", "evidence": "e"} for i in range(5)]
    assert find_path(chain, {"n0"}, "n3") is not None
    assert find_path(chain, {"n0"}, "n4") is None


def test_load_known(tmp_path):
    assert load_known(tmp_path) == set()
    (tmp_path / "me.json").write_text(json.dumps({"known": [" Stripe ", "", 3]}))
    assert load_known(tmp_path) == {"stripe"}
