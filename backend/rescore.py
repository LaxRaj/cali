"""Re-rate every stored startup from data we already hold (no crawling, no LLM).

    uv run python rescore.py [--data-dir DIR]

Keeps stored scores in step with the rubric in rating.py: rows are otherwise only re-rated when the scout or the
enrich backlog touches them, so a rubric change would take weeks to show up.
"""

import argparse
import json
from pathlib import Path

from backfill import _contact_state, _extraction_from_rows, _prev_signals
from export import export_all
from memory import DB_DIR, EDGES, PEOPLE, TABLE, _rows, upsert_profile
from models import Contact
from rating import rate


def rescore(data_dir: Path) -> dict:
    rows = _rows(TABLE, data_dir)
    people_rows, edge_rows = _rows(PEOPLE, data_dir), _rows(EDGES, data_dir)
    changed, scores, good = 0, [], []
    for row in rows:
        ex = _extraction_from_rows(row, people_rows, edge_rows)
        state = _contact_state(row)
        contact = Contact(**state) if state else None
        roles = [r for sg in _prev_signals(rows, row["company_name"]) if sg.get("type") == "hiring" for r in sg.get("roles", [])]
        rt = rate(ex.startup, ex.people, ex.edges, contact, hiring_roles=roles or None)
        scores.append(rt.score)
        if rt.qualified:
            good.append(rt.score)
        sj = json.dumps({"parts": rt.parts, "gaps": rt.gaps, "axes": rt.axes, "qualified": rt.qualified})
        if int(row.get("score") or 0) == rt.score and row.get("score_json") == sj:
            continue
        upsert_profile(ex.startup, db_dir=data_dir, extras={"score": rt.score, "score_json": sj})  # other columns carry over
        changed += 1
    if changed:
        export_all(data_dir)
    mean = lambda xs: round(sum(xs) / len(xs), 1) if xs else 0.0  # noqa: E731
    return {"rows": len(rows), "changed": changed, "avg_score": mean(scores), "qualified": len(good), "avg_qualified_score": mean(good)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=DB_DIR)
    print(json.dumps(rescore(ap.parse_args().data_dir), indent=2))
