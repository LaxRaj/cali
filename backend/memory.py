"""Embedded store (LanceDB + all-MiniLM-L6-v2) for startups, people, connections and seen URLs."""

from functools import lru_cache
from pathlib import Path

import lancedb
from sentence_transformers import SentenceTransformer

from models import Edge, Person, StartupProfile

DB_DIR = Path(__file__).parent / "data"  # tables -> data/<name>.lance
TABLE = "startups"
PEOPLE = "people"
EDGES = "edges"
SEEN = "seen_urls"
EMBED_MODEL = "all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def _encoder() -> SentenceTransformer:
    return SentenceTransformer(EMBED_MODEL)


def embed(text: str) -> list[float]:
    return _encoder().encode(text, normalize_embeddings=True).tolist()


def profile_text(p: StartupProfile) -> str:
    return f"{p.core_product} Tech stack: {', '.join(p.tech_stack)}"


def person_text(p: Person) -> str:
    return f"{p.name}, {p.role} at {p.org}".strip(", ")


def connect(db_dir: str | Path = DB_DIR) -> lancedb.DBConnection:
    Path(db_dir).mkdir(parents=True, exist_ok=True)
    return lancedb.connect(str(db_dir))


def _upsert(table: str, key: str, rows: list[dict], db_dir) -> None:
    """Insert rows, replacing existing rows that share the same `key` value."""
    if not rows:
        return
    db = connect(db_dir)
    if table not in db.list_tables().tables:
        db.create_table(table, data=rows)
        return
    (
        db.open_table(table)
        .merge_insert(key)
        .when_matched_update_all()
        .when_not_matched_insert_all()
        .execute(rows)
    )


def _rows(table: str, db_dir) -> list[dict]:
    db = connect(db_dir)
    if table not in db.list_tables().tables:
        return []
    return db.open_table(table).to_arrow().to_pylist()


def upsert_profile(profile: StartupProfile, db_dir: str | Path = DB_DIR) -> None:
    """Insert the profile, or replace the existing row with the same company_name."""
    _upsert(TABLE, "company_name", [{**profile.model_dump(), "vector": embed(profile_text(profile))}], db_dir)


def upsert_people(people: list[Person], db_dir: str | Path = DB_DIR) -> None:
    rows = [
        {**p.model_dump(), "key": f"{p.name.strip().lower()}|{p.org.strip().lower()}", "vector": embed(person_text(p))}
        for p in people
    ]
    _upsert(PEOPLE, "key", rows, db_dir)


def upsert_edges(edges: list[Edge], db_dir: str | Path = DB_DIR) -> None:
    rows = [{**e.model_dump(), "key": f"{e.src.strip().lower()}|{e.rel}|{e.dst.strip().lower()}"} for e in edges]
    _upsert(EDGES, "key", rows, db_dir)


def search(query: str, k: int = 3, db_dir: str | Path = DB_DIR) -> list[StartupProfile]:
    """Return the k startup profiles closest to the query, best first."""
    db = connect(db_dir)
    if TABLE not in db.list_tables().tables:
        return []
    rows = db.open_table(TABLE).search(embed(query)).limit(k).to_list()
    return [StartupProfile(**{f: r[f] for f in StartupProfile.model_fields}) for r in rows]


def search_people(query: str, k: int = 3, db_dir: str | Path = DB_DIR) -> list[Person]:
    db = connect(db_dir)
    if PEOPLE not in db.list_tables().tables:
        return []
    rows = db.open_table(PEOPLE).search(embed(query)).limit(k).to_list()
    return [Person(**{f: r[f] for f in Person.model_fields}) for r in rows]


def neighbors(entity: str, db_dir: str | Path = DB_DIR) -> list[Edge]:
    """All connections that touch the named person/company (case-insensitive)."""
    name = entity.strip().lower()
    return [
        Edge(**{f: r[f] for f in Edge.model_fields})
        for r in _rows(EDGES, db_dir)
        if r["src"].strip().lower() == name or r["dst"].strip().lower() == name
    ]


def seen_urls(db_dir: str | Path = DB_DIR) -> set[str]:
    return {r["url"] for r in _rows(SEEN, db_dir)}


def mark_seen(urls: list[str], db_dir: str | Path = DB_DIR) -> None:
    _upsert(SEEN, "url", [{"url": u} for u in urls], db_dir)
