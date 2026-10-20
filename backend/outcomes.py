"""Your real-world results per lead, the strongest signal we have. Stored in data/outcomes.json (static, committed).

    uv run python outcomes.py mark CedarDB contacted --note "emailed contact@"
    uv run python outcomes.py list
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from memory import DB_DIR

STATUSES = ("contacted", "replied", "meeting", "won", "passed")
FILE = "outcomes.json"


def load_outcomes(data_dir: Path = DB_DIR) -> dict[str, dict]:
    try:
        return json.loads((Path(data_dir) / FILE).read_text())
    except (OSError, ValueError):
        return {}


def mark(company: str, status: str, note: str = "", data_dir: Path = DB_DIR, now: datetime | None = None) -> dict:
    if status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}")
    data = load_outcomes(data_dir)
    key = company.strip().lower()
    data[key] = {
        "company": company.strip(),
        "status": status,
        "note": note,
        "updated": (now or datetime.now(timezone.utc)).isoformat(timespec="seconds"),
    }
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    (Path(data_dir) / FILE).write_text(json.dumps(data, indent=2))
    return data[key]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("mark")
    m.add_argument("company")
    m.add_argument("status", choices=STATUSES)
    m.add_argument("--note", default="")
    sub.add_parser("list")
    ap.add_argument("--data-dir", type=Path, default=DB_DIR)
    a = ap.parse_args()
    if a.cmd == "mark":
        print(json.dumps(mark(a.company, a.status, a.note, a.data_dir), indent=2))
    else:
        for v in load_outcomes(a.data_dir).values():
            print(f"{v['updated'][:10]}  {v['status']:<10} {v['company']}  {v['note']}")
