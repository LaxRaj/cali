"""Ingestion: DuckDuckGo search -> crawl4ai Markdown extraction."""

import asyncio
import re
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


def search_urls(query: str = QUERY, n: int = TOP_N) -> list[str]:
    results = DDGS().text(query, max_results=n)
    return [r["href"] for r in results][:n]


async def scrape_urls(urls: list[str], max_tokens: int = MAX_TOKENS) -> list[Page]:
    """Crawl URLs and return clean Markdown, each capped at max_tokens."""
    config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        markdown_generator=DefaultMarkdownGenerator(
            content_filter=PruningContentFilter(threshold=0.45, threshold_type="dynamic")
        ),
    )
    pages: list[Page] = []
    async with AsyncWebCrawler() as crawler:
        results = await crawler.arun_many(urls, config=config)
        for res in results:
            if not res.success or not res.markdown:
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
