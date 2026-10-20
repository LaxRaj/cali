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
