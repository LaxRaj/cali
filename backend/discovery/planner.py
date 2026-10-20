"""Turn the objective into concrete searches (the 'intelligence' in discovery)."""

from pydantic import BaseModel, Field

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from llm import chat_json
from objective import N_WEB_QUERIES, OBJECTIVE, RECENCY_DAYS


class Plan(BaseModel):
    web_queries: list[str] = Field(default_factory=list)
    hn_keywords: list[str] = Field(default_factory=list)


FALLBACK = Plan(
    web_queries=[
        '"seed round" startup AI search launch',
        '"Show HN" retrieval OR RAG OR "semantic search" startup',
        'startup raises pre-seed "vector database" OR "semantic search"',
    ],
    hn_keywords=["RAG", "semantic search", "vector search", "AI agents", "developer tools"],
)

SYSTEM = f"""You plan web research. Given an objective, output ONLY JSON:
{{"web_queries": [...], "hn_keywords": [...]}}
- web_queries: exactly {N_WEB_QUERIES} DIVERSE search-engine queries that surface NEWS about specific startups
  (funding announcements, launches, founder interviews) from the last {RECENCY_DAYS} days. Vary angle: stage,
  technology, vertical, funding wording, investor names. No generic "how to" phrasing. Do not use site: operators.
- hn_keywords: 5 short topical keywords (1-3 words) to search Show HN posts for the objective's technologies/verticals."""


PLAN_TTL_DAYS = 3  # the objective is fixed, so a fresh LLM plan every day mostly re-buys the same queries
PLAN_FILE = "plan_cache.json"


def _cache_path() -> Path:
    return Path(os.environ.get("CALI_DATA_DIR") or Path(__file__).parent.parent / "data") / PLAN_FILE


def _cached_plan() -> Plan | None:
    try:
        row = json.loads(_cache_path().read_text())
        age = datetime.now(timezone.utc) - datetime.fromisoformat(row["at"])
        if age.days < PLAN_TTL_DAYS:
            return Plan.model_validate(row["plan"])
    except (OSError, ValueError, KeyError):
        pass
    return None


def make_plan(client=None) -> Plan:
    if client is None and (cached := _cached_plan()):
        return cached
    try:
        plan = Plan.model_validate(chat_json(SYSTEM, OBJECTIVE, client, purpose="plan"))
        if plan.web_queries:
            if client is None:
                try:
                    _cache_path().write_text(json.dumps({"at": datetime.now(timezone.utc).isoformat(), "plan": plan.model_dump()}))
                except OSError:
                    pass
            return plan
    except Exception as e:
        print(f"planner failed, using fallback: {e}")
    return FALLBACK
