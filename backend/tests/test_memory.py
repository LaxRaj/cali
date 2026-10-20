import pytest

from memory import search, upsert_profile
from models import StartupProfile


def make(name, product, stack):
    return StartupProfile(
        company_name=name,
        core_product=product,
        tech_stack=stack,
        likely_bottleneck="n/a",
        value_prop_pitch="n/a",
        is_relevant=True,
    )


PROFILES = [
    make("DocuMind", "AI assistant that answers questions over company documents using retrieval-augmented generation",
         ["Python", "LangChain", "OpenAI", "Pinecone"]),
    make("FleetPulse", "Fleet telematics dashboard for tracking trucks and fuel usage",
         ["Go", "Kafka", "TimescaleDB"]),
    make("PixelForge", "Browser-based 3D game engine for multiplayer games",
         ["Rust", "WebGL", "WebAssembly"]),
]


@pytest.fixture
def db_dir(tmp_path):
    return tmp_path / "startups_db"


def test_ingest_and_retrieve_most_relevant(db_dir):
    for p in PROFILES:
        upsert_profile(p, db_dir=db_dir)

    results = search("AI RAG integration", k=3, db_dir=db_dir)

    assert len(results) == 3
    assert results[0].company_name == "DocuMind"
    assert results[0] == PROFILES[0]
    assert search("real-time vehicle tracking", k=1, db_dir=db_dir)[0].company_name == "FleetPulse"


def test_upsert_replaces_existing_company(db_dir):
    for p in PROFILES:
        upsert_profile(p, db_dir=db_dir)
    updated = PROFILES[1].model_copy(update={"core_product": "Fleet telematics with AI route optimization"})
    upsert_profile(updated, db_dir=db_dir)

    results = search("fleet", k=10, db_dir=db_dir)
    assert len(results) == 3
    assert next(r for r in results if r.company_name == "FleetPulse").core_product == updated.core_product


def test_search_empty_db_returns_nothing(db_dir):
    assert search("anything", db_dir=db_dir) == []


def test_people_edges_and_seen_urls(db_dir):
    from memory import mark_seen, neighbors, search_people, seen_urls, upsert_edges, upsert_people
    from models import Edge, Person

    upsert_people(
        [
            Person(name="Jane Roe", role="CEO and co-founder", org="DocuMind", evidence="e"),
            Person(name="Bob Lee", role="General partner, venture capital investor", org="Seed Fund", evidence="e"),
            Person(name="Sam Ng", role="game engine programmer", org="PixelForge", evidence="e"),
        ],
        db_dir=db_dir,
    )
    assert search_people("venture capital investor", k=1, db_dir=db_dir)[0].name == "Bob Lee"

    upsert_edges(
        [
            Edge(src="Jane Roe", rel="founded", dst="DocuMind", evidence="e"),
            Edge(src="Seed Fund", rel="invested_in", dst="DocuMind", evidence="e"),
            Edge(src="Sam Ng", rel="works_at", dst="PixelForge", evidence="e"),
        ],
        db_dir=db_dir,
    )
    upsert_edges([Edge(src="Jane Roe", rel="founded", dst="DocuMind", evidence="e2")], db_dir=db_dir)  # upsert
    links = neighbors("documind", db_dir=db_dir)
    assert {(e.src, e.rel) for e in links} == {("Jane Roe", "founded"), ("Seed Fund", "invested_in")}

    assert seen_urls(db_dir) == set()
    mark_seen(["a.com/x", "b.com/y"], db_dir=db_dir)
    mark_seen(["a.com/x"], db_dir=db_dir)
    assert seen_urls(db_dir) == {"a.com/x", "b.com/y"}
