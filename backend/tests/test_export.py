import json

import pytest

from export import build_graph, build_profiles, export_all, slugify
from memory import upsert_edges, upsert_people, upsert_profile
from models import Edge, Person, StartupProfile


def prof(name):
    return StartupProfile(company_name=name, core_product="Search", tech_stack=["Python"],
                          likely_bottleneck="Retrieval", value_prop_pitch="One. Two.", is_relevant=True,
                          source_url=f"https://{name.lower()}.com", discovered_at="2026-10-20T00:00:00+00:00")


@pytest.fixture
def db(tmp_path):
    d = tmp_path / "db"
    upsert_profile(prof("Acme"), db_dir=d)
    upsert_profile(prof("Beta"), db_dir=d)
    upsert_people([Person(name="Jane Roe", role="CEO", org="Acme", evidence="Jane Roe is CEO")], db_dir=d)
    upsert_edges(
        [
            Edge(src="Jane Roe", rel="founded", dst="Acme", evidence="Jane Roe founded Acme"),
            Edge(src="Seed Fund", rel="invested_in", dst="Acme", evidence="Seed Fund invested in Acme"),
        ],
        db_dir=d,
    )
    return d


def test_slugify():
    assert slugify("Cedar DB, Inc.") == "cedar-db-inc"
    assert slugify("???") == "unnamed"


def test_profiles_join_people_and_edges_without_vectors(db):
    profiles = {p["company_name"]: p for p in build_profiles(db)}
    acme = profiles["Acme"]
    assert "vector" not in acme and acme["slug"] == "acme"
    assert [p["name"] for p in acme["people"]] == ["Jane Roe"]
    assert {e["rel"] for e in acme["edges"]} == {"founded", "invested_in"}
    assert profiles["Beta"]["people"] == [] and profiles["Beta"]["edges"] == []


def test_graph_types_degrees_and_unknown_endpoints_become_orgs(db):
    g = build_graph(db)
    nodes = {n["id"]: n for n in g["nodes"]}
    assert nodes["acme"]["type"] == "startup" and nodes["acme"]["degree"] == 2
    assert nodes["jane roe"]["type"] == "person" and nodes["jane roe"]["degree"] == 1
    assert nodes["seed fund"]["type"] == "org"
    assert nodes["beta"]["degree"] == 0
    assert g["nodes"][0]["id"] == "acme"  # sorted by degree
    assert {(e["source"], e["target"]) for e in g["edges"]} == {("jane roe", "acme"), ("seed fund", "acme")}


def test_export_all_writes_both_files(db):
    export_all(db)
    assert len(json.loads((db / "profiles.json").read_text())) == 2
    assert "nodes" in json.loads((db / "graph.json").read_text())


def test_empty_db_exports_empty_structures(tmp_path):
    export_all(tmp_path / "empty")
    assert json.loads((tmp_path / "empty" / "profiles.json").read_text()) == []
    assert json.loads((tmp_path / "empty" / "graph.json").read_text()) == {"nodes": [], "edges": [], "investors": []}


def test_profiles_expose_score_contact_gaps_and_person_links_sorted_by_score(tmp_path):
    import json as _json

    d = tmp_path / "db2"
    upsert_profile(prof("Low"), db_dir=d, extras={"score": 30, "score_json": _json.dumps({"parts": {"fit": 30}, "gaps": ["email"]}), "contact_json": "{}"})
    contact = {"website": "https://hi.io", "emails": [{"value": "hi@hi.io", "kind": "general", "source_url": "https://hi.io/"}], "phones": [], "socials": {}}
    upsert_profile(prof("High"), db_dir=d, extras={"score": 90, "score_json": _json.dumps({"parts": {"fit": 25}, "gaps": []}), "contact_json": _json.dumps(contact)})
    upsert_people([Person(name="Jane Roe", role="CEO", org="High", evidence="e", linkedin="https://www.linkedin.com/in/jane-roe", link_source="https://hi.io/team")], db_dir=d)

    profiles = build_profiles(d)
    assert [p["company_name"] for p in profiles] == ["High", "Low"]  # best lead first
    high = profiles[0]
    assert high["score"] == 90 and high["contact"]["emails"][0]["value"] == "hi@hi.io" and high["gaps"] == []
    assert high["people"][0]["linkedin"].endswith("jane-roe") and high["people"][0]["link_source"] == "https://hi.io/team"
    assert profiles[1]["gaps"] == ["email"] and "contact_json" not in high
    node = {n["id"]: n for n in build_graph(d)["nodes"]}["jane roe"]
    assert node["links"] == {"linkedin": "https://www.linkedin.com/in/jane-roe"}


def test_profiles_carry_a_decision_and_your_outcome(tmp_path):
    import json as _json
    from datetime import datetime, timedelta, timezone

    from outcomes import mark

    d = tmp_path / "db3"
    for name in ("Fresh", "Told"):
        # a sourced address on the company's own domain (contact_now requires one)
        contact = _json.dumps({"website": f"https://{name.lower()}.com", "phones": [], "socials": {},
                               "emails": [{"value": f"hi@{name.lower()}.com", "kind": "general", "source_url": f"https://{name.lower()}.com/contact"}]})
        upsert_profile(prof(name), db_dir=d, extras={"score": 85, "score_json": _json.dumps({"parts": {}, "gaps": []}), "contact_json": contact})
    mark("Told", "passed", "not a fit", d)

    now = datetime(2026, 10, 20, tzinfo=timezone.utc)
    got = {p["company_name"]: p for p in build_profiles(d, now=now)}
    assert got["Fresh"]["decision"]["action"] == "contact_now" and got["Fresh"]["outcome"] is None
    assert got["Told"]["decision"]["action"] == "skip" and got["Told"]["outcome"]["status"] == "passed"


def test_profiles_and_graph_edges_carry_ledger_trackbacks(tmp_path):
    import ledger

    d = tmp_path / "db4"
    s = prof("Acme")
    upsert_profile(s, db_dir=d, extras={"score": 80, "score_json": json.dumps({"parts": {}, "gaps": []}), "contact_json": "{}"})
    edge = Edge(src="Fund", rel="invested_in", dst="Acme", evidence="Fund backed Acme")
    upsert_edges([edge], db_dir=d)
    ledger.record(ledger.observations_for(s, [], [edge], None, "https://n.example/a"), "r1", "2026-10-01T00:00:00", d)
    ledger.record(ledger.observations_for(s, [], [edge], None, "https://n.example/b"), "r2", "2026-10-09T00:00:00", d)

    p = build_profiles(d)[0]
    assert {t["source_url"] for t in p["trackbacks"] if t["entity_type"] == "edge"} == {"https://n.example/a", "https://n.example/b"}
    assert p["trackbacks"][0]["last_seen"] == "2026-10-09T00:00:00"  # newest first
    ge = build_graph(d)["edges"][0]
    assert [x["source_url"] for x in ge["sources"]] == ["https://n.example/a", "https://n.example/b"]
