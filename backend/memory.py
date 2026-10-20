"""Embedded vector store for StartupProfiles (LanceDB + all-MiniLM-L6-v2)."""

from functools import lru_cache
from pathlib import Path

import lancedb
from sentence_transformers import SentenceTransformer

from models import StartupProfile

DB_DIR = Path(__file__).parent / "data"  # table "startups" -> data/startups.lance
TABLE = "startups"
EMBED_MODEL = "all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def _encoder() -> SentenceTransformer:
    return SentenceTransformer(EMBED_MODEL)


def embed(text: str) -> list[float]:
    return _encoder().encode(text, normalize_embeddings=True).tolist()


def profile_text(p: StartupProfile) -> str:
    return f"{p.core_product} Tech stack: {', '.join(p.tech_stack)}"


def connect(db_dir: str | Path = DB_DIR) -> lancedb.DBConnection:
    Path(db_dir).mkdir(parents=True, exist_ok=True)
    return lancedb.connect(str(db_dir))


def upsert_profile(profile: StartupProfile, db_dir: str | Path = DB_DIR) -> None:
    """Insert the profile, or replace the existing row with the same company_name."""
    row = {**profile.model_dump(), "vector": embed(profile_text(profile))}
    db = connect(db_dir)
    if TABLE not in db.list_tables().tables:
        db.create_table(TABLE, data=[row])
        return
    (
        db.open_table(TABLE)
        .merge_insert("company_name")
        .when_matched_update_all()
        .when_not_matched_insert_all()
        .execute([row])
    )


def search(query: str, k: int = 3, db_dir: str | Path = DB_DIR) -> list[StartupProfile]:
    """Return the k profiles closest to the query, best first."""
    db = connect(db_dir)
    if TABLE not in db.list_tables().tables:
        return []
    rows = db.open_table(TABLE).search(embed(query)).limit(k).to_list()
    return [StartupProfile(**{f: r[f] for f in StartupProfile.model_fields}) for r in rows]
