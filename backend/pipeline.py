"""Daily scout: plan -> discover -> triage -> crawl -> extract -> quality gates -> store -> export."""

import argparse
import asyncio
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from discovery import Candidate, hn, normalize_url, rss, web, yc
from discovery.planner import make_plan
from discovery.triage import select
from extractor import extract
from memory import DB_DIR, mark_seen, seen_urls, upsert_edges, upsert_people, upsert_profile
from quality import RunReport, check_extraction, evaluate_run
from scraper import scrape_urls


async def discover() -> list[Candidate]:
    plan = make_plan()
    print(f"plan: {plan.model_dump()}")

    async def guarded(name, fn, *args):
        try:
            return await asyncio.to_thread(fn, *args)
        except Exception as e:
            print(f"source {name} failed: {e}", file=sys.stderr)
            return []

    results = await asyncio.gather(
        guarded("hn", hn.fetch, plan.hn_keywords),
        guarded("rss", rss.fetch),
        guarded("yc", yc.fetch),
        guarded("web", web.fetch, plan.web_queries),
    )
    cands = [c for r in results for c in r]
    print("candidates per source:", dict(Counter(c.source for c in cands)))
    return cands


def process(pages, by_url: dict[str, Candidate], report: RunReport):
    """Extract + validate every page. Returns (accepted extractions, their sources)."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    accepted = []
    for page in pages:
        cand = by_url.get(normalize_url(page.url))
        source = cand.source if cand else "unknown"
        try:
            ex = extract(page.markdown)
        except Exception as e:
            print(f"extract failed {page.url}: {e}", file=sys.stderr)
            report.issues["extraction error"] = report.issues.get("extraction error", 0) + 1
            continue
        report.extracted += 1
        ex.startup.source_url = page.url
        ex.startup.discovered_at = now
        checked = check_extraction(ex, page.markdown)
        report.dropped_ungrounded += checked.dropped_people + checked.dropped_edges
        if ex.startup.is_relevant:
            report.relevant += 1
        if checked.accepted:
            report.valid += 1
            report.sources[source] = report.sources.get(source, 0) + 1
            report.people += len(checked.extraction.people)
            report.edges += len(checked.extraction.edges)
            accepted.append((checked.extraction, source))
        for issue in checked.issues:
            report.issues[issue] = report.issues.get(issue, 0) + 1
        if not checked.accepted:
            print(f"reject {page.url}: {checked.issues}", file=sys.stderr)
    return accepted


async def run(data_dir: Path) -> RunReport:
    report = RunReport()
    cands = await discover()
    report.candidates = len(cands)

    chosen = select(cands, seen_urls(data_dir))
    by_url = {normalize_url(c.url): c for c in chosen}
    pages = await scrape_urls([c.url for c in chosen])
    report.crawled = len(pages)
    print(f"selected {len(chosen)}, crawled {len(pages)}")

    accepted = process(pages, by_url, report)
    evaluate_run(report)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    (data_dir / "quality_report.json").write_text(
        json.dumps({"generated_at": now, **report.to_dict()}, indent=2)
    )
    if not report.passed:
        return report  # write nothing else: CI must not commit bad data

    for ex, _ in accepted:
        upsert_profile(ex.startup, db_dir=data_dir)
        upsert_people(ex.people, db_dir=data_dir)
        upsert_edges(ex.edges, db_dir=data_dir)
    mark_seen([normalize_url(c.url) for c in chosen], db_dir=data_dir)

    findings = [
        {
            **ex.startup.model_dump(),
            "source": source,
            "people": [p.model_dump() for p in ex.people],
            "edges": [e.model_dump() for e in ex.edges],
        }
        for ex, source in accepted
    ]
    brief = {"generated_at": now, "findings": findings}
    (data_dir / "daily_brief.json").write_text(json.dumps(brief, indent=2, ensure_ascii=False))
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=DB_DIR)
    args = ap.parse_args()
    args.data_dir.mkdir(parents=True, exist_ok=True)
    rep = asyncio.run(run(args.data_dir))
    print(json.dumps(rep.to_dict(), indent=2))
    if not rep.passed:
        print("QUALITY GATES FAILED: " + "; ".join(rep.failures), file=sys.stderr)
        sys.exit(1)
