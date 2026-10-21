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


_SQL_DEFAULT = {str: "cast('' as string)", bool: "cast(false as boolean)", int: "cast(0 as bigint)", float: "cast(0 as double)"}


def _ensure_columns(tbl, row: dict) -> None:
    """Schema evolution: add columns that newer code writes but an older table lacks (existing rows get defaults)."""
    have = set(tbl.schema.names)
    missing = {k: _SQL_DEFAULT[type(v)] for k, v in row.items() if k not in have and type(v) in _SQL_DEFAULT}
    if missing:
        tbl.add_columns(missing)


def _upsert(table: str, key: str, rows: list[dict], db_dir) -> None:
    """Insert rows, replacing existing rows that share the same `key` value."""
    if not rows:
        return
    db = connect(db_dir)
    if table not in db.list_tables().tables:
        db.create_table(table, data=rows)
        return
    tbl = db.open_table(table)
    _ensure_columns(tbl, rows[0])
    (
        tbl
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


def _first_discovered(company: str, db_dir) -> str:
    """Earliest discovered_at already stored for this exact company name ("" if new). ISO strings sort chronologically."""
    return next((r.get("discovered_at", "") for r in _rows(TABLE, db_dir) if r["company_name"] == company), "")


def upsert_profile(profile: StartupProfile, db_dir: str | Path = DB_DIR, extras: dict | None = None) -> None:
    """Insert the profile, or replace the existing row with the same company_name.

    `extras` are additional flat columns (score, score_json, contact_json) kept beside the profile fields.
    """
    first = _first_discovered(profile.company_name, db_dir)
    if first and (not profile.discovered_at or first < profile.discovered_at):
        profile = profile.model_copy(update={"discovered_at": first})  # re-finding a company must not reset when we found it
    row = {**profile.model_dump(), **(extras or {}), "vector": embed(profile_text(profile))}
    # a partial update (e.g. a backfill without signals) must not drop columns other stages wrote earlier
    prev = next((r for r in _rows(TABLE, db_dir) if r["company_name"] == profile.company_name), None)
    for k, v in (prev or {}).items():
        if k not in row and k != "vector":
            row[k] = v
    _upsert(TABLE, "company_name", [row], db_dir)


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
    return [StartupProfile(**{f: r[f] for f in StartupProfile.model_fields if f in r}) for r in rows]


def search_people(query: str, k: int = 3, db_dir: str | Path = DB_DIR) -> list[Person]:
    db = connect(db_dir)
    if PEOPLE not in db.list_tables().tables:
        return []
    rows = db.open_table(PEOPLE).search(embed(query)).limit(k).to_list()
    return [Person(**{f: r.get(f, "") for f in Person.model_fields}) for r in rows]


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
