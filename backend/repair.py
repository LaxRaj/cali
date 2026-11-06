"""One-shot, idempotent repair of stored data under the current integrity rules (safe to re-run).

    uv run python repair.py [--data-dir DIR] [--dry-run] [--no-compact]

For every stored startup it:
  * normalises funding_stage ("pre‑Seed" -> "pre-seed"),
  * clears a website that is a publisher / job board / other company's domain (falls back to the enriched one if valid),
  * drops contact emails that are not on the company's own domain (publisher, DPO service, template addresses),
  * resets the enrichment state of rows whose website was cleared, so the backlog job re-enriches them,
  * re-rates the row (fills axes/qualified for rows rated before those existed).
It also de-duplicates decisions.jsonl by URL (last row wins) and compacts the lance tables (old versions pruned).
"""

import argparse
import json
from datetime import timedelta
from pathlib import Path

from backfill import _extraction_from_rows, _prev_signals
from enrich import _valid_email, email_on_company_domain, host_matches_company, host_of, is_company_host, origin_of
from entities import normalize_stage
from memory import DB_DIR, EDGES, PEOPLE, TABLE, _rows, connect, update_profile_columns
from models import Contact
from rating import rate

DECISIONS = "decisions.jsonl"


def good_website(url: str, company: str, source_url: str = "") -> bool:
    """Conservative for stored data: a site is wrong when it is a publisher / job board / login host, or when it is just
    the host of the source page (the faulty "the page itself" fallback) on a domain that does not match the name."""
    if not url or not url.startswith(("http://", "https://")):
        return False
    host = host_of(url)
    if not is_company_host(host):
        return False
    if source_url and host == host_of(source_url) and not host_matches_company(host, company):
        return False
    return True


def repair_row(row: dict, people_rows: list[dict], edge_rows: list[dict], all_rows: list[dict]) -> tuple[dict, list[str]]:
    """-> (changed columns, human-readable notes). Pure: does not write."""
    name = row["company_name"]
    notes: list[str] = []
    upd: dict = {}

    stage = normalize_stage(row.get("funding_stage") or "")
    if stage != (row.get("funding_stage") or ""):
        upd["funding_stage"] = stage
        notes.append(f"stage {row.get('funding_stage')!r} -> {stage!r}")

    try:
        contact = Contact(**json.loads(row.get("contact_json") or "{}"))
    except (ValueError, TypeError):
        contact = Contact()
    website = row.get("website") or ""
    src = row.get("source_url") or ""
    if website and not good_website(website, name, src):
        fallback = origin_of(contact.website) if good_website(contact.website, name, src) else ""
        upd["website"] = fallback
        notes.append(f"website {website} -> {fallback or '(cleared)'}")
        website = fallback
    contact_changed = False
    if contact.website and not good_website(contact.website, name, src):
        notes.append(f"contact website {contact.website} cleared; queued for re-enrichment")
        contact = Contact(status="", attempts=0)  # everything in it came from the wrong site
        contact_changed = True
    kept = [e for e in contact.emails if _valid_email(e.value) and email_on_company_domain(e.value, contact.website or website, name)]
    if len(kept) != len(contact.emails):
        dropped = sorted({e.value for e in contact.emails} - {e.value for e in kept})
        notes.append(f"dropped off-domain emails {dropped}")
        contact = contact.model_copy(update={"emails": kept})
        contact_changed = True
    if contact_changed:
        upd["contact_json"] = contact.model_dump_json()

    merged = {**row, **upd}
    ex = _extraction_from_rows(merged, people_rows, edge_rows)
    roles = [r for sg in _prev_signals(all_rows, name) if sg.get("type") == "hiring" for r in sg.get("roles", [])]
    rt = rate(ex.startup, ex.people, ex.edges, contact, hiring_roles=roles or None)
    score_json = json.dumps({"parts": rt.parts, "gaps": rt.gaps, "axes": rt.axes, "qualified": rt.qualified})
    try:
        old = json.loads(row.get("score_json") or "{}")
    except ValueError:
        old = {}
    if int(row.get("score") or 0) != rt.score or old.get("qualified") != rt.qualified or "axes" not in old:
        upd["score"], upd["score_json"] = rt.score, score_json
        notes.append(f"rescored {row.get('score')} -> {rt.score} (qualified={rt.qualified})")
    return upd, notes


def dedupe_decisions(data_dir: Path, dry_run: bool) -> tuple[int, int]:
    path = Path(data_dir) / DECISIONS
    if not path.exists():
        return 0, 0
    rows = [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
    last: dict[str, dict] = {}
    for r in rows:
        last.pop(r.get("url", ""), None)  # re-insert so order follows the latest occurrence
        last[r.get("url", "")] = r
    if not dry_run and len(last) != len(rows):
        path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in last.values()) + "\n")
    return len(rows), len(last)


def compact(data_dir: Path) -> dict[str, int]:
    """Merge small fragments and prune versions older than a day. Returns table -> versions before."""
    db = connect(data_dir)
    out = {}
    for name in db.list_tables().tables:
        tbl = db.open_table(name)
        out[name] = len(tbl.list_versions())
        tbl.optimize(cleanup_older_than=timedelta(days=1))
    return out


def repair(data_dir: Path = DB_DIR, dry_run: bool = False, do_compact: bool = True) -> dict:
    rows = _rows(TABLE, data_dir)
    people_rows, edge_rows = _rows(PEOPLE, data_dir), _rows(EDGES, data_dir)
    changed: list[dict] = []
    for row in rows:
        upd, notes = repair_row(row, people_rows, edge_rows, rows)
        if not upd:
            continue
        changed.append({"company": row["company_name"], "notes": notes})
        if not dry_run:
            update_profile_columns(row["company_name"], upd, data_dir)
    before, after = dedupe_decisions(data_dir, dry_run)
    versions = compact(data_dir) if do_compact and not dry_run else {}
    if changed and not dry_run:
        from export import export_all

        export_all(data_dir)
    return {"rows": len(rows), "changed": changed, "decisions": {"before": before, "after": after}, "compacted": versions}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=DB_DIR)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-compact", action="store_true")
    args = ap.parse_args()
    res = repair(args.data_dir, args.dry_run, not args.no_compact)
    for c in res["changed"]:
        print(f"- {c['company']}: " + "; ".join(c["notes"]))
    print(f"{len(res['changed'])}/{res['rows']} rows {'would change' if args.dry_run else 'changed'}; "
          f"decisions {res['decisions']['before']} -> {res['decisions']['after']}; compacted {res['compacted']}")
