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

    out = []
    for r in rows:
        if r.get("outcome") == "accepted":
            label = 1
        elif r.get("outcome") == "rejected":
            label = 0
        else:
            continue
        if r.get("title"):
            out.append((candidate_state(r["title"], r.get("snippet", ""), r.get("source", "")), label))
    return out
