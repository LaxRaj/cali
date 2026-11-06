"""Weekly digest and health alerts as Markdown, for a GitHub issue (free: the workflow's own GITHUB_TOKEN + `gh`).

    uv run python digest.py weekly [--out digest.md]   # new strong leads, who to contact, watchlist hits, replies, run health
    uv run python digest.py alerts [--out alerts.md]   # stale data (no run in 26h) or two UTC days ending on the quota

`alerts` prints nothing (and writes an empty file) when everything is healthy, so the workflow only posts real problems.
Reads only the static exports (profiles.json, runs_index.json, outcomes.json): no network, no LLM.
"""

import argparse
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from memory import DB_DIR

STALE_HOURS = 26
STRONG = 70
DASHBOARD_URL_ENV = "CALI_DASHBOARD_URL"


def _read(path: Path, default):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return default


def _ts(iso: str) -> datetime | None:
    try:
        t = datetime.fromisoformat((iso or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def _runs(data_dir: Path) -> list[dict]:
    return _read(Path(data_dir) / "runs_index.json", {}).get("runs", [])


def _status(run: dict) -> str:
    return run.get("status") or ("passed" if run.get("passed") else "failed")


def alerts(data_dir: Path = DB_DIR, now: datetime | None = None) -> list[str]:
    now = now or datetime.now(timezone.utc)
    runs = _runs(data_dir)
    out = []
    if not runs:
        return ["No scout runs recorded yet."]
    last = max((_ts(r.get("started_at", "")) for r in runs), default=None, key=lambda t: t or datetime.min.replace(tzinfo=timezone.utc))
    if last is None or now - last > timedelta(hours=STALE_HOURS):
        age = f"{(now - last).total_seconds() / 3600:.0f} h" if last else "unknown"
        out.append(f"**Stale data:** the newest scout run is {age} old (limit {STALE_HOURS} h). Check the scout workflow.")
    by_day: dict[str, list[str]] = {}
    for r in runs:
        if t := _ts(r.get("started_at", "")):
            by_day.setdefault(t.date().isoformat(), []).append(_status(r))
    days = sorted(by_day)[-2:]
    if len(days) == 2 and all(by_day[d] and all(s == "quota" for s in by_day[d]) for d in days):
        out.append(f"**Groq quota:** every run on {days[0]} and {days[1]} stopped on the daily token limit. "
                   "Add another free key (GROQ_API_KEY_2) or lower CALI_TOKEN_BUDGET.")
    return out


def weekly(data_dir: Path = DB_DIR, now: datetime | None = None, days: int = 7) -> str:
    import os

    now = now or datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    profiles = _read(Path(data_dir) / "profiles.json", [])
    outcomes = _read(Path(data_dir) / "outcomes.json", {})
    runs = [r for r in _runs(data_dir) if (t := _ts(r.get("started_at", ""))) and t >= since]
    base = os.environ.get(DASHBOARD_URL_ENV, "").rstrip("/")

    def link(p: dict) -> str:
        return f"[{p['company_name']}]({base}/startups/{p['slug']})" if base else f"**{p['company_name']}**"

    new = [p for p in profiles if (t := _ts(p.get("discovered_at", ""))) and t >= since]
    strong = sorted((p for p in new if int(p.get("score") or 0) >= STRONG), key=lambda p: -int(p.get("score") or 0))
    contact = sorted((p for p in profiles if (p.get("decision") or {}).get("action") == "contact_now"),
                     key=lambda p: -(p.get("decision") or {}).get("priority", 0))
    review = [p for p in profiles if (p.get("decision") or {}).get("action") == "review"]
    watched = [p for p in profiles if p.get("watch")]
    status = Counter(_status(r) for r in runs)
    tokens = sum(int(r.get("tokens") or 0) for r in runs)
    valid = sum(int((r.get("funnel") or {}).get("valid") or 0) for r in runs)
    replies = [o for o in outcomes.values() if o.get("status") == "replied" and (t := _ts(o.get("updated", ""))) and t >= since]

    lines = [f"# Cali weekly digest ({since.date()} to {now.date()})", ""]
    lines += [f"**{len(new)}** new startups, **{len(strong)}** scoring {STRONG}+. **{len(contact)}** ready to contact, "
              f"**{len(review)}** to review.", ""]
    if strong:
        lines += ["## New strong leads", ""]
        lines += [f"- {link(p)} ({p.get('score')}): {(p.get('core_product') or '')[:110]}" for p in strong[:10]] + [""]
    if contact:
        lines += ["## Contact next", ""]
        lines += [f"- {link(p)}: {(p.get('decision') or {}).get('next_step', '')}" for p in contact[:10]] + [""]
    if watched:
        lines += ["## Watchlist", ""] + [f"- {link(p)}: {', '.join(p['watch'])}" for p in watched[:10]] + [""]
    if replies:
        intents = Counter(o.get("intent") or "other" for o in replies)
        lines += ["## Replies", "", f"{len(replies)} repl{'y' if len(replies) == 1 else 'ies'}: "
                  + ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in intents.most_common()), ""]
    lines += ["## Scout health", "",
              f"{len(runs)} runs: {status.get('passed', 0)} passed, {status.get('failed', 0)} failed, {status.get('quota', 0)} quota. "
              f"{tokens:,} tokens for {valid} valid startups" + (f" ({tokens // valid:,} per startup)." if valid else "."), ""]
    if problems := alerts(data_dir, now):
        lines += ["## Alerts", ""] + [f"- {a}" for a in problems] + [""]
    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=("weekly", "alerts"))
    ap.add_argument("--data-dir", type=Path, default=DB_DIR)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    text = weekly(a.data_dir) if a.kind == "weekly" else "\n\n".join(alerts(a.data_dir))
    if a.out:
        a.out.write_text(text)
    print(text)
