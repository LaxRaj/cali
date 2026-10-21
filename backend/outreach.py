"""Outreach outbox: scout-informed drafts queued for YOUR review. Nothing here ever sends an email.

Flow: `queue` (from data/profiles.json + decisions) -> `push` (Gmail Drafts, you press send) -> `sync` (replies,
bounces, opt-outs flow back into outcomes.py). Stored in data/outbox.json and data/suppressed.json.

    uv run python outreach.py queue
    uv run python outreach.py push        # needs the optional Gmail setup (see gmail_sync.py)
    uv run python outreach.py sync
    uv run python outreach.py list
    uv run python outreach.py sent CedarDB    # you sent it by hand
    uv run python outreach.py suppress example.com

Guardrails (enforced here): only a company-published, sourced address; daily cap; one contact per domain per
cooldown; one follow-up then stop; suppression list; CALI_OUTREACH=0 disables everything.
"""

import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from outcomes import mark as mark_outcome
from outcomes import load_outcomes

DB_DIR = Path(__file__).parent / "data"
OUTBOX, SUPPRESSED = "outbox.json", "suppressed.json"
STATUSES = ("queued", "drafted", "sent", "replied", "bounced", "opted_out")
DAILY_CAP = int(os.environ.get("CALI_OUTREACH_DAILY_CAP", "15"))
DOMAIN_COOLDOWN_DAYS = 30
FOLLOW_UP_DAYS = 7


def enabled() -> bool:
    return os.environ.get("CALI_OUTREACH", "1") != "0"


def _read(path: Path, default):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def load_outbox(data_dir: Path = DB_DIR) -> dict[str, dict]:
    return _read(Path(data_dir) / OUTBOX, {})


def save_outbox(outbox: dict, data_dir: Path = DB_DIR) -> None:
    _write(Path(data_dir) / OUTBOX, outbox)


def load_suppressed(data_dir: Path = DB_DIR) -> list[str]:
    return _read(Path(data_dir) / SUPPRESSED, [])


def suppress(entry: str, data_dir: Path = DB_DIR) -> list[str]:
    """Add a domain or exact address to the never-contact list."""
    entries = load_suppressed(data_dir)
    entry = entry.strip().lower().removeprefix("@")
    if entry and entry not in entries:
        entries.append(entry)
        _write(Path(data_dir) / SUPPRESSED, entries)
    return entries


def domain_of(address: str) -> str:
    return address.rsplit("@", 1)[-1].strip().lower()


def is_suppressed(address: str, suppressed: list[str]) -> bool:
    return address.lower() in suppressed or domain_of(address) in suppressed


def _host(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def _found_on_publisher(profile: dict) -> bool:
    """The "website" is the same host the lead was discovered on (a news site, SEC, HN): the address isn't the company's."""
    site, found = _host(profile.get("website", "")), _host(profile.get("source_url", ""))
    return bool(site) and site == found


def item_key(company: str, kind: str) -> str:
    return f"{company.strip().lower()}::{kind}"


def follow_up_draft(first: dict, profile: dict, sender: dict) -> dict:
    """One short nudge in the same thread of thought; no new claims."""
    company = profile["company_name"]
    body = [
        f"Hi {company} team,",
        "",
        "Following up on my note last week in case it got buried. Still keen to explore working together.",
        "",
        'If now isn\'t the time, just reply "no" and I won\'t write again.',
    ]
    if sender.get("name"):
        body += ["", sender["name"]]
    return {**first, "subject": f"Re: {first['subject']}", "body": "\n".join(body)}


def queue_from_profiles(
    profiles: list[dict],
    data_dir: Path = DB_DIR,
    now: datetime | None = None,
    cap: int | None = None,
    sender: dict | None = None,
) -> list[dict]:
    """Enqueue drafts for leads the decider says to contact (or follow up). Returns the newly queued items."""
    if not enabled():
        return []
    now = now or datetime.now(timezone.utc)
    cap = DAILY_CAP if cap is None else cap
    sender = sender if sender is not None else {}
    outbox = load_outbox(data_dir)
    suppressed = load_suppressed(data_dir)
    today = now.date().isoformat()
    queued_today = sum(1 for i in outbox.values() if i["queued"][:10] == today)
    recent_domains = {
        domain_of(i["to"])
        for i in outbox.values()
        if now - datetime.fromisoformat(i["queued"]) < timedelta(days=DOMAIN_COOLDOWN_DAYS)
    }
    added: list[dict] = []
    ranked = sorted(profiles, key=lambda p: (p.get("decision") or {}).get("priority", 0), reverse=True)
    for p in ranked:
        action = (p.get("decision") or {}).get("action")
        draft = p.get("email_draft") or {}
        if action not in ("contact_now", "follow_up") or not draft.get("to") or not draft.get("to_source_url"):
            continue
        company, to = p["company_name"], draft["to"]
        if is_suppressed(to, suppressed) or _found_on_publisher(p):
            continue
        kind = "follow_up" if action == "follow_up" else "first"
        key = item_key(company, kind)
        first = outbox.get(item_key(company, "first"))
        if key in outbox:
            continue  # already queued/sent: one first email, one follow-up, then stop
        if kind == "follow_up":
            if not first or first["status"] != "sent":
                continue
            if now - datetime.fromisoformat(first["updated"]) < timedelta(days=FOLLOW_UP_DAYS):
                continue
            draft = follow_up_draft(first, p, sender)
        elif domain_of(to) in recent_domains:
            continue
        if queued_today >= cap:
            break
        outbox[key] = {
            "company": company,
            "kind": kind,
            "to": to,
            "to_source_url": draft["to_source_url"],
            "subject": draft["subject"],
            "body": draft["body"],
            "intent": draft.get("intent", ""),
            "intent_reason": draft.get("intent_reason", ""),
            "status": "queued",
            "queued": now.isoformat(timespec="seconds"),
            "updated": now.isoformat(timespec="seconds"),
            "gmail_draft_id": "",
            "gmail_thread_id": "",
        }
        recent_domains.add(domain_of(to))
        queued_today += 1
        added.append(outbox[key])
    save_outbox(outbox, data_dir)
    return added


def set_status(company: str, kind: str, status: str, data_dir: Path = DB_DIR, now: datetime | None = None, **extra) -> dict:
    """Move one item along and mirror it into outcomes.py (sent -> contacted, replied -> replied, opted_out -> passed)."""
    if status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}")
    outbox = load_outbox(data_dir)
    item = outbox[item_key(company, kind)]
    now = now or datetime.now(timezone.utc)
    item.update(status=status, updated=now.isoformat(timespec="seconds"), **extra)
    save_outbox(outbox, data_dir)
    outcome = {"sent": "contacted", "replied": "replied", "opted_out": "passed", "bounced": "passed"}.get(status)
    if outcome and (load_outcomes(data_dir).get(company.strip().lower()) or {}).get("status") not in ("meeting", "won"):
        mark_outcome(company, outcome, note=f"outreach {status}", data_dir=data_dir, now=now)
    if status in ("opted_out", "bounced"):
        suppress(item["to"], data_dir)
    return item


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=DB_DIR)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("queue", "push", "sync", "list"):
        sub.add_parser(name)
    s = sub.add_parser("sent")
    s.add_argument("company")
    s.add_argument("--kind", default="first", choices=("first", "follow_up"))
    x = sub.add_parser("suppress")
    x.add_argument("entry")
    a = ap.parse_args()

    if a.cmd == "queue":
        from draft import load_sender

        profiles = _read(a.data_dir / "profiles.json", [])
        added = queue_from_profiles(profiles, a.data_dir, sender=load_sender(a.data_dir))
        print(f"queued {len(added)}" + ("" if enabled() else " (CALI_OUTREACH=0: disabled)"))
        for i in added:
            print(f"  {i['company']:<24} {i['kind']:<9} {i['intent']:<11} -> {i['to']}")
    elif a.cmd in ("push", "sync"):
        import gmail_sync

        print(getattr(gmail_sync, a.cmd)(a.data_dir))
    elif a.cmd == "sent":
        set_status(a.company, a.kind, "sent", a.data_dir)
    elif a.cmd == "suppress":
        suppress(a.entry, a.data_dir)
    else:
        for i in sorted(load_outbox(a.data_dir).values(), key=lambda i: i["updated"], reverse=True):
            print(f"{i['updated'][:10]}  {i['status']:<9} {i['kind']:<9} {i['company']:<24} {i['to']}")


if __name__ == "__main__":
    main()
