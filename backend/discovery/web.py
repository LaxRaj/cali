"""LLM-planned web search through ddgs."""

from discovery import Candidate
from scraper import search_results


def fetch(queries: list[str], per_query: int = 6) -> list[Candidate]:
    out: list[Candidate] = []
    for q in queries:
        for r in search_results(q, per_query, attempts=2):
            out.append(
                Candidate(url=r["href"], title=r.get("title", ""), snippet=r.get("body", "")[:300], source="web")
            )
    return out
