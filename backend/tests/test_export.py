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
    assert json.loads((tmp_path / "empty" / "graph.json").read_text()) == {"nodes": [], "edges": []}
