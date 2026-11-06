"""Training data for the local decider: every crawled candidate with its features and what happened to it."""

import json
from pathlib import Path

FILE = "decisions.jsonl"
MAX_ROWS = 5000


def append_decisions(data_dir: Path, run_id: str, rows: list[dict]) -> None:
    if not rows:
        return
    path = Path(data_dir) / FILE
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    old = path.read_text().splitlines() if path.exists() else []
    new = [json.dumps({"run_id": run_id, **r}, ensure_ascii=False) for r in rows]
    path.write_text("\n".join((old + new)[-MAX_ROWS:]) + "\n")


def load_decisions(data_dir: Path) -> list[dict]:
    path = Path(data_dir) / FILE
    try:
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    except (OSError, ValueError):
        return []


def labelled(rows: list[dict]) -> list[tuple[str, int]]:
    """(state, label) pairs we can learn from: accepted = 1, judged-not-a-startup = 0. Gated/errors are excluded
    (the gate is the model's own guess, and errors say nothing about the page)."""
    from decide.decisions import candidate_state

    latest: dict[str, dict] = {}
    for r in rows:  # one label per page: the most recent judgement wins (re-crawls must not multiply a label)
        if r.get("lane") or r.get("source") == "hiring":
            continue  # hiring posts are accepted without LLM validation: not evidence about what a startup page looks like
        latest.pop(r.get("url") or id(r), None)
        latest[r.get("url") or id(r)] = r
    out = []
    for r in latest.values():
        if r.get("outcome") == "accepted":
            label = 1
        elif r.get("outcome") == "rejected":
            label = 0
        else:
            continue
        if r.get("title"):
            out.append((candidate_state(r["title"], r.get("snippet", ""), r.get("source", "")), label))
    return out


POSITIVE_OUTCOMES = {"replied", "meeting", "won"}
UNINFORMATIVE_REASONS = {"no_contact", "other"}  # 'passed' for these says nothing about whether the lead was a fit


def lead_state(profile: dict) -> str:
    """What the 'lead' head reads: the company as we understood it, not how reachable it was."""
    stack = ", ".join((profile.get("tech_stack") or [])[:5])
    return ". ".join(x for x in (
        profile.get("core_product", ""), profile.get("likely_bottleneck", ""),
        f"Stage: {profile['funding_stage']}" if profile.get("funding_stage") else "", f"Stack: {stack}" if stack else "",
    ) if x)


def outcome_labels(profiles: list[dict], outcomes: dict[str, dict]) -> list[tuple[str, int]]:
    """Real-world results as labels for the 'lead' head: replied / meeting / won = 1, passed (for a fit reason) = 0.
    'contacted' alone is not a label yet (no answer either way)."""
    by_key = {p["company_name"].strip().lower(): p for p in profiles}
    out = []
    for key, o in outcomes.items():
        p = by_key.get(key)
        status = o.get("status")
        if not p or not lead_state(p):
            continue
        if status in POSITIVE_OUTCOMES and o.get("intent") not in ("unsubscribe", "complaint"):
            out.append((lead_state(p), 1))
        elif status == "passed" and o.get("reason") not in UNINFORMATIVE_REASONS:
            out.append((lead_state(p), 0))
    return out
