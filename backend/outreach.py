"""Outreach log: every touch you make on a lead, append-only (data/outreach.jsonl), folded into a current state.

    uv run python outreach.py log CedarDB sent --subject "Quick thought" --to hi@cedardb.com
    uv run python outreach.py import ~/Downloads/cali-outreach.json   # events exported from the dashboard
    uv run python outreach.py show CedarDB

Events: sent | replied | bounced | meeting | won | passed | note | snooze. The older data/outcomes.json (one record per
company, written by outcomes.py) is read as legacy events, so nothing recorded before the log existed is lost.
`fold` is mirrored in frontend/lib/outreach.ts; both are tested against tests/fixtures/outreach_cases.json.
"""

import argparse
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from memory import DB_DIR

FILE = "outreach.jsonl"
EVENT_TYPES = ("sent", "replied", "bounced", "meeting", "won", "passed", "note", "snooze")
EVENT_FIELDS = ("id", "company", "type", "at", "channel", "subject", "to", "to_source_url", "thread_id", "note", "reason", "until")
CADENCE_DAYS = (7, 7)  # days to wait after the 1st and 2nd touch before following up
MAX_TOUCHES = 3  # after this many sends with no reply, stop suggesting follow-ups
REPLY_DAYS = 3  # how long a reply may sit before it is overdue
LEGACY_TYPE = {"contacted": "sent", "replied": "replied", "meeting": "meeting", "won": "won", "passed": "passed"}


def _key(company: str) -> str:
    return company.strip().lower()


def parse_time(iso: str) -> datetime | None:
    try:
        t = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError):
        return None
    return (t if t.tzinfo else t.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


def fmt_time(t: datetime) -> str:
    return t.astimezone(timezone.utc).isoformat(timespec="seconds")


def new_event(company: str, type: str, at: datetime | None = None, **fields) -> dict:
    if type not in EVENT_TYPES:
        raise ValueError(f"type must be one of {EVENT_TYPES}")
    extra = {k: v for k, v in fields.items() if k in EVENT_FIELDS and v}
    return {"id": uuid.uuid4().hex, "company": company.strip(), "type": type, "at": fmt_time(at or datetime.now(timezone.utc)), **extra}


def _legacy_events(data_dir: Path) -> list[dict]:
    try:
        outcomes = json.loads((Path(data_dir) / "outcomes.json").read_text())
    except (OSError, ValueError):
        return []
    out = []
    for key, o in outcomes.items():
        etype = LEGACY_TYPE.get(o.get("status", ""))
        if etype:
            out.append({k: v for k, v in {"id": f"legacy-{key}-{o['status']}", "company": o.get("company", key), "type": etype,
                                          "at": o.get("updated", ""), "note": o.get("note", ""), "reason": o.get("reason", "")}.items() if v})
    return out


def _log_events(data_dir: Path) -> list[dict]:
    out = []
    try:
        lines = (Path(data_dir) / FILE).read_text().splitlines()
    except OSError:
        return out
    for line in lines:
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if isinstance(e, dict) and e.get("type") in EVENT_TYPES and e.get("company") and parse_time(e.get("at", "")):
            out.append(e)
    return out


def load_events(data_dir: Path = DB_DIR) -> list[dict]:
    """Log events plus legacy outcomes, de-duplicated by id."""
    seen, out = set(), []
    for e in _log_events(data_dir) + _legacy_events(data_dir):
        if e["id"] not in seen and parse_time(e.get("at", "")):
            seen.add(e["id"])
            out.append(e)
    return out


def append(event: dict, data_dir: Path = DB_DIR) -> dict:
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    with (Path(data_dir) / FILE).open("a") as f:
        f.write(json.dumps({k: v for k, v in event.items() if k in EVENT_FIELDS}, ensure_ascii=False) + "\n")
    return event


def import_events(path: Path, data_dir: Path = DB_DIR) -> int:
    """Merge events exported from the dashboard (a JSON list, or {"events": [...]}); returns how many were new."""
    raw = json.loads(Path(path).read_text())
    incoming = raw.get("events", []) if isinstance(raw, dict) else raw
    known = {e["id"] for e in _log_events(data_dir)}
    added = 0
    for e in incoming:
        ok = isinstance(e, dict) and e.get("id") and e.get("type") in EVENT_TYPES and e.get("company") and parse_time(e.get("at", ""))
        if ok and e["id"] not in known:
            append(e, data_dir)
            known.add(e["id"])
            added += 1
    return added


def by_company(events: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for e in events:
        out.setdefault(_key(e["company"]), []).append(e)
    return out


def fold(events: list[dict], now: datetime | None = None) -> dict:
    """Current outreach state of one lead from its events (any order)."""
    now = now or datetime.now(timezone.utc)
    status, touches, last_sent, replied_at, last_to, last_subject, pass_reason = "none", 0, None, None, "", "", ""
    snooze_until: datetime | None = None
    timed = sorted(((parse_time(e["at"]), i, e) for i, e in enumerate(events) if parse_time(e.get("at", ""))), key=lambda x: (x[0], x[1]))
    for t, _, e in timed:
        kind = e["type"]
        if kind == "sent":
            touches += 1
            last_sent, last_to, last_subject = t, e.get("to", "") or last_to, e.get("subject", "") or last_subject
            if status in ("none", "bounced", "passed"):
                status = "contacted"
            snooze_until = None
        elif kind == "replied":
            replied_at = t
            if status not in ("meeting", "won"):
                status = "replied"
            snooze_until = None
        elif kind == "meeting":
            if status != "won":
                status = "meeting"
        elif kind == "won":
            status = "won"
        elif kind == "passed":
            status, pass_reason = "passed", e.get("reason", "")
        elif kind == "bounced":
            if status in ("none", "contacted"):
                status = "bounced"
        elif kind == "snooze":
            snooze_until = parse_time(e.get("until", ""))

    next_due, exhausted = None, False
    if status == "contacted" and last_sent:
        if touches >= MAX_TOUCHES:
            exhausted = True
        else:
            next_due = last_sent + timedelta(days=CADENCE_DAYS[min(touches, len(CADENCE_DAYS)) - 1])
    elif status == "replied":
        ref = max(t for t in (last_sent, replied_at) if t)
        next_due = ref + timedelta(days=REPLY_DAYS)
    snoozed = bool(snooze_until and snooze_until > now and status in ("contacted", "replied", "none"))
    if snoozed:
        next_due = max(next_due, snooze_until) if next_due else snooze_until
    return {
        "status": status,
        "touches": touches,
        "last_contact": fmt_time(last_sent) if last_sent else "",
        "replied_at": fmt_time(replied_at) if replied_at else "",
        "next_due": fmt_time(next_due) if next_due else "",
        "overdue": bool(next_due and next_due <= now and not snoozed),
        "snoozed": snoozed,
        "exhausted": exhausted,
        "last_to": last_to,
        "last_subject": last_subject,
        "pass_reason": pass_reason if status == "passed" else "",
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=DB_DIR)
    sub = ap.add_subparsers(dest="cmd", required=True)
    lg = sub.add_parser("log")
    lg.add_argument("company")
    lg.add_argument("type", choices=EVENT_TYPES)
    for opt in ("subject", "to", "to-source-url", "channel", "note", "reason", "until", "thread-id"):
        lg.add_argument(f"--{opt}", default="")
    im = sub.add_parser("import")
    im.add_argument("file", type=Path)
    sh = sub.add_parser("show")
    sh.add_argument("company")
    a = ap.parse_args()
    if a.cmd == "log":
        fields = {k: getattr(a, k) for k in ("subject", "to", "to_source_url", "channel", "note", "reason", "until", "thread_id")}
        print(json.dumps(append(new_event(a.company, a.type, **fields), a.data_dir), indent=2))
    elif a.cmd == "import":
        print(f"imported {import_events(a.file, a.data_dir)} new event(s)")
    else:
        evs = by_company(load_events(a.data_dir)).get(_key(a.company), [])
        print(json.dumps(fold(evs), indent=2))
        for e in sorted(evs, key=lambda e: e["at"]):
            print(f"{e['at'][:16]}  {e['type']:<8} {e.get('subject', '') or e.get('note', '')}")
