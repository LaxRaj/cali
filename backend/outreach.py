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
import random
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from draft import OPT_OUT
from outcomes import mark as mark_outcome
from outcomes import load_outcomes

DB_DIR = Path(__file__).parent / "data"
OUTBOX, SUPPRESSED, STATE = "outbox.json", "suppressed.json", "outreach_state.json"
STATUSES = ("queued", "drafted", "sending", "sent", "replied", "bounced", "opted_out", "complaint", "skipped")
DAILY_CAP = int(os.environ.get("CALI_OUTREACH_DAILY_CAP", "15"))
DOMAIN_COOLDOWN_DAYS = 30
FOLLOW_UP_DAYS = 7
# Autonomous sending: warm-up ramp, human-like timing, content lint, quality gate, circuit breaker.
RAMP_START, RAMP_STEP = 3, 2  # sends allowed on day 0, then +RAMP_STEP per day, up to DAILY_CAP
SEND_WEEKDAYS, SEND_HOURS = (1, 2, 3), (9, 16)  # Tue-Thu, 09:00-15:59 local
GAP_MINUTES = (4, 15)
SEND_MIN_SCORE = 70
MAX_WORDS = 120
BREAKER_WINDOW, BREAKER_MAX_BOUNCES = 20, 2
SPAM_PHRASES = re.compile(
    r"\b(free|guaranteed?|act now|limited time|click here|buy now|risk[- ]free|winner|100%|no obligation)\b|\$\$", re.I
)


def enabled() -> bool:
    return os.environ.get("CALI_OUTREACH", "1") != "0"


def send_enabled() -> bool:
    """Autonomous sending is opt-in per machine: without CALI_OUTREACH_SEND=1 the agent only makes Gmail drafts."""
    return enabled() and os.environ.get("CALI_OUTREACH_SEND") == "1"


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
            "gmail_thread_id": first.get("gmail_thread_id", "") if kind == "follow_up" else "",
            "reply_to_message_id": first.get("gmail_message_id", "") if kind == "follow_up" else "",
            "gmail_message_id": "",
            "sent_at": "",
            "score": int(p.get("score") or 0),
            "specific": bool(p.get("likely_bottleneck", "").strip() or p.get("tech_stack")),
            "priority": (p.get("decision") or {}).get("priority", 0),
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
    if status == "sent" and not item.get("sent_at"):
        extra.setdefault("sent_at", now.isoformat(timespec="seconds"))
    item.update(status=status, updated=now.isoformat(timespec="seconds"), **extra)
    save_outbox(outbox, data_dir)
    outcome = {"sent": "contacted", "replied": "replied", "opted_out": "passed", "bounced": "passed", "complaint": "passed"}.get(status)
    if outcome and (load_outcomes(data_dir).get(company.strip().lower()) or {}).get("status") not in ("meeting", "won"):
        mark_outcome(company, outcome, note=f"outreach {status}", data_dir=data_dir, now=now)
    if status in ("opted_out", "bounced", "complaint"):
        suppress(item["to"], data_dir)
    if status == "complaint":
        set_paused(True, f"complaint from {item['to']}", data_dir)
    return item


def load_state(data_dir: Path = DB_DIR) -> dict:
    return {"paused": False, "reason": "", "next_send_at": "", "last_sent": "", **_read(Path(data_dir) / STATE, {})}


def save_state(state: dict, data_dir: Path = DB_DIR) -> None:
    _write(Path(data_dir) / STATE, state)


def set_paused(paused: bool, reason: str = "", data_dir: Path = DB_DIR) -> dict:
    state = load_state(data_dir)
    state.update(paused=paused, reason=reason if paused else "")
    save_state(state, data_dir)
    return state


def ramp_cap(outbox: dict, now: datetime, max_cap: int | None = None) -> int:
    """Warm-up: RAMP_START sends on the first sending day, +RAMP_STEP each day after, never above the daily cap."""
    max_cap = DAILY_CAP if max_cap is None else max_cap
    firsts = [i["sent_at"] for i in outbox.values() if i.get("sent_at")]
    if not firsts:
        return min(RAMP_START, max_cap)
    days = (now.date() - datetime.fromisoformat(min(firsts)).date()).days
    return min(max_cap, RAMP_START + RAMP_STEP * max(days, 0))


def sent_today(outbox: dict, now: datetime) -> int:
    return sum(1 for i in outbox.values() if i.get("sent_at", "")[:10] == now.date().isoformat())


def in_send_window(now: datetime) -> bool:
    """`now` is wall-clock time for the sender (callers pass local time)."""
    return now.weekday() in SEND_WEEKDAYS and SEND_HOURS[0] <= now.hour < SEND_HOURS[1]


def breaker_tripped(outbox: dict) -> bool:
    """Too many of the most recent sends bounced: stop before the sending reputation suffers."""
    sent = sorted((i for i in outbox.values() if i.get("sent_at")), key=lambda i: i["sent_at"])[-BREAKER_WINDOW:]
    return sum(1 for i in sent if i["status"] == "bounced") > BREAKER_MAX_BOUNCES


def lint(item: dict) -> list[str]:
    """Reasons this email looks like bulk mail. Empty means fine to send."""
    body, problems = item["body"], []
    if len(body.split()) > MAX_WORDS:
        problems.append(f"over {MAX_WORDS} words")
    if SPAM_PHRASES.search(item["subject"] + "\n" + body):
        problems.append("spam phrase")
    if re.search(r"\b[A-Z]{5,}\b", (item["subject"] + " " + body).replace(item["company"], "")):
        problems.append("ALL CAPS word")
    if (item["subject"] + body).count("!") > 1:
        problems.append("too many exclamation marks")
    if len(re.findall(r"https?://|www\.", body)) > 1:
        problems.append("more than one link")
    if re.search(r"\[[^\]]+\]", body):
        problems.append("unfilled [placeholder] (a human must complete this draft)")
    if re.search(r"<[a-z/][^>]*>", body, re.I):
        problems.append("HTML in body")
    if OPT_OUT not in body and item["kind"] == "first":
        problems.append("missing opt-out line")
    return problems


def gate(item: dict) -> list[str]:
    """Quality gate for unattended sending: strong fit and something specific to say."""
    problems = []
    if item.get("score", 0) < SEND_MIN_SCORE:
        problems.append(f"score {item.get('score', 0)} < {SEND_MIN_SCORE}")
    if not item.get("specific"):
        problems.append("nothing specific to say (no bottleneck or stack)")
    return problems


def run(
    data_dir: Path = DB_DIR,
    now: datetime | None = None,
    dry_run: bool = False,
    svc=None,
    rng: random.Random | None = None,
) -> str:
    """One scheduler tick: sync replies, queue new leads, then send at most ONE vetted email if timing allows.

    Without CALI_OUTREACH_SEND=1 (or with dry_run) nothing is sent: it makes Gmail drafts / reports instead.
    Call it every ~20 minutes from cron; the ramp, window and random gaps decide whether this tick sends.
    """
    import gmail_sync
    from draft import load_sender

    if not enabled():
        return "CALI_OUTREACH=0: disabled"
    now = now or datetime.now().astimezone()  # local wall-clock for the send window
    rng = rng or random.Random()
    data_dir = Path(data_dir)
    sending = send_enabled() and not dry_run
    if svc is None and not dry_run:
        svc = gmail_sync.service()

    if svc is not None:
        gmail_sync.sync(data_dir, svc=svc)
    outbox = load_outbox(data_dir)
    if breaker_tripped(outbox):
        set_paused(True, f"more than {BREAKER_MAX_BOUNCES} of the last {BREAKER_WINDOW} sends bounced", data_dir)
    state = load_state(data_dir)
    if state["paused"]:
        return f"paused: {state['reason']} (fix it, then: outreach.py resume)"

    sender = load_sender(data_dir)
    queue_from_profiles(_read(data_dir / "profiles.json", []), data_dir, now, sender=sender)
    if not sending and not dry_run:
        return gmail_sync.push(data_dir, svc=svc) + " (CALI_OUTREACH_SEND!=1: drafts only)"

    if not sender["name"]:
        return "not sending: set CALI_SENDER_NAME or data/me.json so every email is signed"
    outbox = load_outbox(data_dir)
    if not in_send_window(now):
        return "outside the send window (Tue-Thu 09:00-16:00)"
    if state["next_send_at"] and now < datetime.fromisoformat(state["next_send_at"]):
        return f"waiting until {state['next_send_at'][11:16]} (random gap between sends)"
    if sent_today(outbox, now) >= ramp_cap(outbox, now):
        return f"today's ramp cap reached ({ramp_cap(outbox, now)})"

    suppressed = load_suppressed(data_dir)
    for item in sorted((i for i in outbox.values() if i["status"] == "queued"), key=lambda i: i.get("priority", 0), reverse=True):
        problems = lint(item) + gate(item) + (["suppressed"] if is_suppressed(item["to"], suppressed) else [])
        if problems:
            if not dry_run:
                set_status(item["company"], item["kind"], "skipped", data_dir, now, skip_reason="; ".join(problems))
            continue
        if dry_run:
            return f"would send to {item['to']} ({item['company']}, {item['kind']}, {item['intent']})"
        set_status(item["company"], item["kind"], "sending", data_dir, now)  # persisted BEFORE the API call: no double-send
        try:
            sent = gmail_sync.send_item(svc, item)
        except Exception as e:  # unknown whether Gmail accepted it: stop and let a human check
            set_paused(True, f"send to {item['to']} failed ({type(e).__name__}); check Gmail Sent, then fix the item", data_dir)
            return f"send failed, paused: {e}"
        set_status(item["company"], item["kind"], "sent", data_dir, now, gmail_message_id=sent["id"], gmail_thread_id=sent["threadId"])
        state = load_state(data_dir)
        state.update(last_sent=now.isoformat(timespec="seconds"), next_send_at=(now + timedelta(minutes=rng.uniform(*GAP_MINUTES))).isoformat(timespec="seconds"))
        save_state(state, data_dir)
        return f"sent to {item['to']} ({item['company']}, {item['kind']})"
    return "nothing eligible to send"


def status_line(data_dir: Path = DB_DIR, now: datetime | None = None) -> str:
    now = now or datetime.now().astimezone()
    outbox, state = load_outbox(data_dir), load_state(data_dir)
    counts: dict[str, int] = {}
    for i in outbox.values():
        counts[i["status"]] = counts.get(i["status"], 0) + 1
    return (
        f"{'PAUSED: ' + state['reason'] if state['paused'] else 'running'} | sending={'on' if send_enabled() else 'off (drafts only)'} | "
        f"today {sent_today(outbox, now)}/{ramp_cap(outbox, now)} | window={'open' if in_send_window(now) else 'closed'} | {counts}"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=DB_DIR)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("queue", "push", "sync", "list"):
        sub.add_parser(name)
    r = sub.add_parser("run")
    r.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("pause")
    p.add_argument("reason", nargs="?", default="paused by you")
    sub.add_parser("resume")
    sub.add_parser("status")
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
    elif a.cmd == "run":
        print(run(a.data_dir, dry_run=a.dry_run))
    elif a.cmd == "pause":
        set_paused(True, a.reason, a.data_dir)
    elif a.cmd == "resume":
        set_paused(False, data_dir=a.data_dir)
    elif a.cmd == "status":
        print(status_line(a.data_dir))
    elif a.cmd == "sent":
        set_status(a.company, a.kind, "sent", a.data_dir)
    elif a.cmd == "suppress":
        suppress(a.entry, a.data_dir)
    else:
        for i in sorted(load_outbox(a.data_dir).values(), key=lambda i: i["updated"], reverse=True):
            print(f"{i['updated'][:10]}  {i['status']:<9} {i['kind']:<9} {i['company']:<24} {i['to']}")


if __name__ == "__main__":
    main()
