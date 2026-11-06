"""Run telemetry: a per-run log (stages, sources, funnel, tokens, rejections) the dashboard reads."""

import json
import time
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path

INDEX_FILE = "runs_index.json"
RUNS_DIR = "runs"
MAX_INDEX = 90

_current: ContextVar["RunLog | None"] = ContextVar("current_run_log", default=None)


def current() -> "RunLog | None":
    """The active RunLog (lets deep code such as discovery log without parameter threading)."""
    return _current.get()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class RunLog:
    def __init__(self) -> None:
        self.started = _now()
        self.run_id = self.started.strftime("%Y%m%dT%H%M%SZ")
        self._t0 = time.monotonic()
        self.stages: list[dict] = []
        self.sources: dict[str, dict] = {}
        self.errors: list[str] = []
        self.rejections: list[dict] = []
        self.accepted: list[dict] = []
        self.plan: dict = {}
        self.feedback: dict = {}
        self.decisions: dict = {}  # decision-engine stats (provider, calls, latency, gated pages, tokens saved)
        self.candidate_log: list[dict] = []  # per-candidate features + outcome: training data for the decider
        self.funnel: dict[str, int] = {}
        self.usage: dict[str, int] = {}
        self.quality: dict = {}
        self.passed = False
        self.quota_exhausted = False  # a Groq daily token limit ended or blocked this run: not a quality failure
        self.token_budget = 0  # tokens/day across all configured Groq keys (0 = unknown)
        self.failures: list[str] = []
        self.diff: dict = {}  # what this run changed in the store: {"added": [...], "updated": [...]}
        self._token = _current.set(self)

    # --- recording -------------------------------------------------------------------------
    @contextmanager
    def stage(self, name: str):
        """Time a pipeline stage. The yielded dict collects `counts` and `notes` for the stage."""
        entry = {
            "name": name,
            "started_at": _now().isoformat(timespec="seconds"),
            "offset_s": round(time.monotonic() - self._t0, 2),
            "duration_s": 0.0,
            "status": "ok",
            "counts": {},
            "notes": [],
        }
        self.stages.append(entry)
        t = time.monotonic()
        try:
            yield entry
        except Exception as e:
            entry["status"] = "error"
            entry["notes"].append(f"{type(e).__name__}: {e}"[:300])
            self.error(f"stage {name} failed: {e}")
            raise
        finally:
            entry["duration_s"] = round(time.monotonic() - t, 2)

    def error(self, message: str) -> None:
        self.errors.append(message[:400])

    def source(self, name: str, candidates: int, seconds: float, error: str = "") -> None:
        self.sources[name] = {"candidates": candidates, "seconds": round(seconds, 2), "error": error[:200]}

    def rejection(self, url: str, source: str, reasons: list[str]) -> None:
        self.rejections.append({"url": url, "source": source, "reasons": reasons})

    def candidate(self, url: str, source: str, title: str, snippet: str, triage: float, outcome: str, score: int | None = None,
                  gate_p: float | None = None, lane: bool = False) -> None:
        row = {"url": url, "source": source, "title": title, "snippet": snippet[:160],
               "triage": triage, "outcome": outcome, "score": score, "gate_p": gate_p}
        if lane:
            row["lane"] = True  # hiring-lane row: not LLM-validated, so it is not a training label
        self.candidate_log.append(row)

    def accept(self, company: str, url: str, source: str, people: int, edges: int) -> None:
        self.accepted.append({"company": company, "url": url, "source": source, "people": people, "edges": edges})

    @property
    def status(self) -> str:
        """passed | failed | quota. A run that did not pass because the Groq quota ran out is `quota`, not `failed`."""
        if self.passed:
            return "passed"
        return "quota" if self.quota_exhausted else "failed"

    # --- output ----------------------------------------------------------------------------
    def summary(self) -> dict:
        return {
            "run_id": self.run_id,
            "started_at": self.started.isoformat(timespec="seconds"),
            "duration_s": round(time.monotonic() - self._t0, 1),
            "passed": self.passed,
            "status": self.status,
            "funnel": self.funnel,
            "tokens": self.usage.get("total_tokens", 0),
            "token_budget": self.token_budget,
            "sources": {k: v["candidates"] for k, v in self.sources.items()},
            "failures": self.failures,
        }

    def to_dict(self) -> dict:
        return {
            **self.summary(),
            "plan": self.plan,
            "feedback": self.feedback,
            "decisions": self.decisions,
            "stages": self.stages,
            "source_health": self.sources,
            "usage": self.usage,
            "quality": self.quality,
            "accepted": self.accepted,
            "rejections": self.rejections,
            "errors": self.errors,
            "diff": self.diff,
        }

    def write(self, data_dir: Path) -> None:
        """Write runs/<id>.json and update the rolling runs_index.json."""
        data_dir = Path(data_dir)
        (data_dir / RUNS_DIR).mkdir(parents=True, exist_ok=True)
        (data_dir / RUNS_DIR / f"{self.run_id}.json").write_text(json.dumps(self.to_dict(), indent=2))

        index_path = data_dir / INDEX_FILE
        try:
            runs = json.loads(index_path.read_text())["runs"]
        except (OSError, ValueError, KeyError):
            runs = []
        runs = [r for r in runs if r["run_id"] != self.run_id] + [self.summary()]
        runs = sorted(runs, key=lambda r: r["run_id"])[-MAX_INDEX:]
        index_path.write_text(json.dumps({"runs": runs}, indent=2))

    def close(self) -> None:
        _current.reset(self._token)


def backfill_index(data_dir: Path) -> int:
    """Add `status` to index entries written before that field existed, from each run's own file.
    Returns how many entries changed."""
    data_dir = Path(data_dir)
    index_path = data_dir / INDEX_FILE
    runs = json.loads(index_path.read_text())["runs"]
    changed = 0
    for r in runs:
        if "status" in r:
            continue
        try:
            detail = json.loads((data_dir / RUNS_DIR / f"{r['run_id']}.json").read_text())
        except (OSError, ValueError):
            detail = {}
        quota = bool((detail.get("quality") or {}).get("quota_exhausted"))
        r["status"] = "passed" if r.get("passed") else ("quota" if quota else "failed")
        changed += 1
    index_path.write_text(json.dumps({"runs": runs}, indent=2))
    return changed
