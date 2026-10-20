"""Turn the objective into concrete searches (the 'intelligence' in discovery)."""

from pydantic import BaseModel, Field

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


def make_plan(client=None) -> Plan:
    try:
        plan = Plan.model_validate(chat_json(SYSTEM, OBJECTIVE, client))
        if plan.web_queries:
            return plan
    except Exception as e:
        print(f"planner failed, using fallback: {e}")
    return FALLBACK
