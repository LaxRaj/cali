from investors import investor_clusters

E = [
    {"src": "Sequoia", "rel": "invested_in", "dst": "Acme", "evidence": "e"},
    {"src": "Beta", "rel": "backed_by", "dst": "sequoia", "evidence": "e"},
    {"src": "Acme", "rel": "backed_by", "dst": "YC", "evidence": "e"},
    {"src": "Beta", "rel": "backed_by", "dst": "YC", "evidence": "e"},
    {"src": "Gamma", "rel": "backed_by", "dst": "Solo", "evidence": "e"},
    {"src": "Sequoia", "rel": "invested_in", "dst": "NotInPool", "evidence": "e"},
    {"src": "Acme", "rel": "competitor_of", "dst": "Beta", "evidence": "e"},
]


def test_clusters_need_two_pool_companies_and_merge_directions():
    out = investor_clusters(E, ["Acme", "Beta", "Gamma"])
    assert [(c["investor"], c["companies"]) for c in out] == [("Sequoia", ["Acme", "Beta"]), ("YC", ["Acme", "Beta"])]


def test_co_investors_count_shared_companies():
    out = investor_clusters(E, ["Acme", "Beta", "Gamma"])
    assert out[0]["co_investors"] == [{"name": "YC", "shared": 2}]


def test_min_companies_and_empty():
    assert investor_clusters([], ["Acme"]) == []
    assert len(investor_clusters(E, ["Acme", "Beta", "Gamma"], min_companies=1)) == 3  # Sequoia, YC, Solo
