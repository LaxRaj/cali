"""Re-enrich startups stored before enrichment existed (or whose enrichment never completed).

    uv run --env-file .env.local python backfill.py [--data-dir DIR] [--limit 3] [--only "CedarDB,Theo"]

Same first-party policy as enrich.py. Re-reads each startup's source page to find its own website.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

import llm
from enrich import EnrichResult, enrich_startup, fetch_pages, host_of, is_company_host
from export import export_all
from extractor import extract_people
from memory import DB_DIR, EDGES, PEOPLE, TABLE, _rows, upsert_edges, upsert_people, upsert_profile
from models import Contact, Edge, Extraction, Person, StartupProfile
from quality import _norm
from rating import rate
from scraper import scrape_urls, search_results

DEFAULT_LIMIT = 3


def needs_enrichment(row: dict) -> bool:
    """Never enriched, or the last attempt found no website/crawl."""
    raw = row.get("contact_json") or ""
    if not raw:
        return True
    try:
        return json.loads(raw).get("status") in ("", "no_website", "crawl_failed")
    except ValueError:
        return True


def _extraction_from_rows(row: dict, people_rows: list[dict], edge_rows: list[dict]) -> Extraction:
    name = row["company_name"].strip().lower()
    people = [Person(**{f: p.get(f, "") for f in Person.model_fields}) for p in people_rows if p["org"].strip().lower() == name]
    names = {name, *(p.name.strip().lower() for p in people)}
    edges = [Edge(**{f: e[f] for f in Edge.model_fields}) for e in edge_rows if e["src"].strip().lower() in names or e["dst"].strip().lower() in names]
    startup = StartupProfile(**{f: row[f] for f in StartupProfile.model_fields if f in row})
    return Extraction(startup=startup, people=people, edges=edges)


async def backfill(
    data_dir: Path,
    limit: int = DEFAULT_LIMIT,
    only: list[str] | None = None,
    *,
    search_fn=None,
    scrape_fn=scrape_urls,
    fetch_fn=fetch_pages,
    extract_fn=extract_people,
) -> list[dict]:
    """Enrich up to `limit` stored startups; returns a summary per startup."""
    rows = [r for r in _rows(TABLE, data_dir) if needs_enrichment(r)]
    if only:
        wanted = {_norm(o) for o in only}
        rows = [r for r in rows if _norm(r["company_name"]) in wanted]
    rows = sorted(rows, key=lambda r: r.get("discovered_at", ""), reverse=True)[:limit]
    people_rows, edge_rows = _rows(PEOPLE, data_dir), _rows(EDGES, data_dir)
    search_budget, team_budget = [6], [limit]
    out = []
    for row in rows:
        ex = _extraction_from_rows(row, people_rows, edge_rows)
        src_url = ex.startup.source_url
        # The source page is the best place to find the company's own link (and grounds the people we keep).
        try:
            pages = await scrape_fn([src_url]) if src_url else []
        except Exception:
            pages = []
        md = pages[0].markdown if pages else ""
        source = "hn" if src_url and is_company_host(host_of(src_url)) else "rss"
        try:
            res = await enrich_startup(
                ex, source, md, search_fn=search_fn, fetch_fn=fetch_fn, extract_fn=extract_fn,
                search_budget=search_budget, team_budget=team_budget,
            )
        except Exception as e:
            res = EnrichResult(ex, Contact(status="crawl_failed"), [f"error: {e}"])
        s, people, edges = res.extraction.startup, res.extraction.people, res.extraction.edges
        rt = rate(s, people, edges, res.contact)
        upsert_profile(
            s, db_dir=data_dir,
            extras={"score": rt.score, "score_json": json.dumps({"parts": rt.parts, "gaps": rt.gaps}),
                    "contact_json": res.contact.model_dump_json()},
        )
        upsert_people(people, db_dir=data_dir)
        upsert_edges(edges, db_dir=data_dir)
        out.append({
            "company": s.company_name, "score": rt.score, "gaps": rt.gaps, "website": res.contact.website,
            "status": res.contact.status, "emails": len(res.contact.emails), "phones": len(res.contact.phones),
            "people": len(people), "edges": len(edges), "notes": res.notes,
        })
    if out:
        export_all(data_dir)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=DB_DIR)
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    ap.add_argument("--only", default="", help="comma-separated company names")
    args = ap.parse_args()

    def search_fn(q):
        return search_results(q, 5, attempts=1)

    llm.reset_usage()
    results = asyncio.run(
        backfill(args.data_dir, args.limit, [o for o in args.only.split(",") if o.strip()] or None, search_fn=search_fn)
    )
    print(json.dumps(results, indent=2))
    print(f"tokens used: {llm.USAGE['total_tokens']}", file=sys.stderr)
