"""Ingestion: DuckDuckGo search -> crawl4ai Markdown extraction."""

import asyncio
import re
import sys
import time
from dataclasses import dataclass

import tiktoken
from crawl4ai import AsyncWebCrawler, CacheMode, CrawlerRunConfig
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from ddgs import DDGS  # successor of duckduckgo-search

QUERY = '"Show HN" OR site:techcrunch.com "seed round"'
TOP_N = 5
MAX_TOKENS = 6000

_ENC = tiktoken.get_encoding("cl100k_base")


@dataclass
class Page:
    url: str
    markdown: str


_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_DATA_URI = re.compile(r"\(data:[^)]*\)")


def clean_markdown(md: str) -> str:
    md = _IMAGE.sub("", md)
    md = _DATA_URI.sub("()", md)
    return re.sub(r"\n{3,}", "\n\n", md).strip()


def count_tokens(text: str) -> int:
    return len(_ENC.encode(text, disallowed_special=()))


def truncate_tokens(text: str, max_tokens: int = MAX_TOKENS) -> str:
    tokens = _ENC.encode(text, disallowed_special=())
    if len(tokens) <= max_tokens:
        return text
    return _ENC.decode(tokens[:max_tokens])


BACKENDS = ["duckduckgo", "brave", "yahoo", "mojeek", "startpage"]


def search_results(query: str = QUERY, n: int = TOP_N, attempts: int = 3) -> list[dict]:
    """Search DuckDuckGo first, then fall back to other engines.

    DDG intermittently returns nothing and blocks datacenter IPs (e.g. CI runners), and
    sometimes returns a single blank result. Returns dicts with title/href/body.
    """
    for attempt in range(attempts):
        for backend in BACKENDS:
            try:
                results = DDGS().text(query, max_results=n, backend=backend)
            except Exception as e:
                print(f"search[{backend}] failed: {e}", file=sys.stderr)
                continue
            usable = [r for r in results if r.get("href", "").startswith("http")][:n]
            if usable:
                print(f"search[{backend}]: {len(usable)} urls", file=sys.stderr)
                return usable
            print(f"search[{backend}]: no usable results ({results!r:.200})", file=sys.stderr)
        time.sleep(2**attempt)
    return []


def search_urls(query: str = QUERY, n: int = TOP_N, attempts: int = 3) -> list[str]:
    return [r["href"] for r in search_results(query, n, attempts)]


async def scrape_urls(urls: list[str], max_tokens: int = MAX_TOKENS) -> list[Page]:
    """Crawl URLs and return clean Markdown, each capped at max_tokens. robots.txt is respected and login-gated
    hosts (LinkedIn, ...) are never fetched (CLAUDE.md enrichment policy)."""
    from enrich import host_of, is_crawlable_host

    skipped = [u for u in urls if not is_crawlable_host(host_of(u))]
    for u in skipped:
        print(f"scrape skipped (no-crawl host) {u}", file=sys.stderr)
    urls = [u for u in urls if u not in skipped]
    if not urls:
        return []
    config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        check_robots_txt=True,
        markdown_generator=DefaultMarkdownGenerator(
            content_filter=PruningContentFilter(threshold=0.45, threshold_type="dynamic")
        ),
    )
    pages: list[Page] = []
    async with AsyncWebCrawler() as crawler:
        results = await crawler.arun_many(urls, config=config)
        for res in results:
            if not res.success or not res.markdown:
                print(f"scrape failed {res.url}: {res.error_message}", file=sys.stderr)
                continue
            md = clean_markdown(res.markdown.fit_markdown or res.markdown.raw_markdown)
            if md:
                pages.append(Page(res.url, truncate_tokens(md, max_tokens)))
    return pages


async def scrape(query: str = QUERY, n: int = TOP_N) -> list[Page]:
    return await scrape_urls(search_urls(query, n))


if __name__ == "__main__":
    for p in asyncio.run(scrape()):
        print(f"## {p.url} ({count_tokens(p.markdown)} tokens)")
