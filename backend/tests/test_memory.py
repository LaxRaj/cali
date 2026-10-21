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


def test_reupsert_keeps_the_earliest_discovered_at(db_dir):
    from memory import TABLE, _rows

    first = PROFILES[0].model_copy(update={"discovered_at": "2026-10-01T00:00:00+00:00"})
    upsert_profile(first, db_dir=db_dir)
    later = first.model_copy(update={"discovered_at": "2026-10-09T00:00:00+00:00"})
    upsert_profile(later, db_dir=db_dir, extras={"last_seen": "2026-10-09T00:00:00+00:00"})
    row = next(r for r in _rows(TABLE, db_dir) if r["company_name"] == first.company_name)
    assert row["discovered_at"] == "2026-10-01T00:00:00+00:00" and row["last_seen"] == "2026-10-09T00:00:00+00:00"


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


def test_old_tables_gain_new_columns_without_losing_rows(db_dir):
    """Data committed by an older version of the scout must keep working when new fields appear."""
    import lancedb

    from memory import embed, upsert_people, upsert_profile
    from models import Person

    db_dir.mkdir()
    db = lancedb.connect(str(db_dir))
    db.create_table("startups", data=[{
        "company_name": "OldCo", "core_product": "Legacy search", "tech_stack": ["Go"], "likely_bottleneck": "b",
        "value_prop_pitch": "One. Two.", "is_relevant": True, "funding_stage": "seed", "source_url": "u",
        "discovered_at": "2026-10-19", "vector": embed("Legacy search Tech stack: Go"),
    }])
    db.create_table("people", data=[{"name": "Old Person", "role": "CEO", "org": "OldCo", "evidence": "e",
                                      "key": "old person|oldco", "vector": embed("Old Person, CEO at OldCo")}])

    upsert_profile(PROFILES[0], db_dir=db_dir, extras={"score": 77, "score_json": '{"parts": {}, "gaps": []}', "contact_json": "{}"})
    upsert_people([Person(name="New Person", role="CTO", org="DocuMind", evidence="e", linkedin="https://www.linkedin.com/in/new-person")], db_dir=db_dir)

    rows = {r["company_name"]: r for r in db.open_table("startups").to_arrow().to_pylist()}
    assert rows["OldCo"]["score"] == 0 and rows["OldCo"]["website"] == ""  # old row got defaults
    assert rows["DocuMind"]["score"] == 77
    people = {r["name"]: r for r in db.open_table("people").to_arrow().to_pylist()}
    assert people["Old Person"]["linkedin"] == "" and people["New Person"]["linkedin"].endswith("new-person")
    assert search("AI RAG integration", k=1, db_dir=db_dir)[0].company_name == "DocuMind"
