import re

import pytest

from scraper import MAX_TOKENS, count_tokens, scrape_urls, search_urls

YC_LAUNCH_URL = "https://www.ycombinator.com/launches/SBD-machine0-cloud-computers-for-ai-agents"


@pytest.mark.live
async def test_scrape_yc_launch_post_is_valid_markdown_under_limit():
    pages = await scrape_urls([YC_LAUNCH_URL])
    assert len(pages) == 1
    md = pages[0].markdown

    assert "machine0" in md.lower()  # real post content, not a redirect/homepage
    assert md.strip()
    assert count_tokens(md) < MAX_TOKENS
    # Valid Markdown: no raw HTML document scaffolding, and some Markdown structure.
    assert not re.search(r"<(html|head|body|script)\b", md, re.I)
    assert re.search(r"^#{1,6} |\[[^\]]+\]\([^)]+\)|^[-*] ", md, re.M)


@pytest.mark.live
def test_search_returns_up_to_five_urls():
    urls = search_urls()
    assert 1 <= len(urls) <= 5
    assert all(u.startswith("http") for u in urls)
