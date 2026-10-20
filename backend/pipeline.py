"""Daily scout: plan -> discover -> triage -> crawl -> extract -> quality gates -> store -> export."""

import argparse
import asyncio
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import llm
import telemetry
from discovery import Candidate, hn, normalize_url, rss, web, yc
from discovery.planner import make_plan
from discovery.triage import select
from export import export_all
from extractor import extract
from memory import DB_DIR, mark_seen, seen_urls, upsert_edges, upsert_people, upsert_profile
from quality import RunReport, check_extraction, evaluate_run
from scraper import scrape_urls


async def discover() -> list[Candidate]:
    log = telemetry.current()
    plan = make_plan()
    print(f"plan: {plan.model_dump()}")
    if log:
        log.plan = plan.model_dump()

    async def guarded(name, fn, *args):
        t = time.monotonic()
        try:
            out = await asyncio.to_thread(fn, *args)
            err = ""
        except Exception as e:
            print(f"source {name} failed: {e}", file=sys.stderr)
            out, err = [], str(e)
            if log:
                log.error(f"source {name} failed: {e}")
        if log:
            log.source(name, len(out), time.monotonic() - t, err)
        return out

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
    log = telemetry.current()
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
            if log:
                log.error(f"extract failed {page.url}: {e}")
                log.rejection(page.url, source, ["extraction error"])
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
            if log:
                log.accept(ex.startup.company_name, page.url, source,
                           len(checked.extraction.people), len(checked.extraction.edges))
        for issue in checked.issues:
            report.issues[issue] = report.issues.get(issue, 0) + 1
        if not checked.accepted:
            print(f"reject {page.url}: {checked.issues}", file=sys.stderr)
            if log:
                log.rejection(page.url, source, checked.issues)
    return accepted


async def run(data_dir: Path) -> RunReport:
    log = telemetry.RunLog()
    llm.reset_usage()
    report = RunReport()
    try:
        with log.stage("discover") as st:
            cands = await discover()
            report.candidates = len(cands)
            st["counts"] = {"candidates": len(cands), **{f"src_{k}": v for k, v in Counter(c.source for c in cands).items()}}

        with log.stage("triage") as st:
            chosen = select(cands, seen_urls(data_dir))
            by_url = {normalize_url(c.url): c for c in chosen}
            st["counts"] = {"in": len(cands), "selected": len(chosen)}

        with log.stage("crawl") as st:
            pages = await scrape_urls([c.url for c in chosen])
            report.crawled = len(pages)
            st["counts"] = {"requested": len(chosen), "crawled": len(pages)}
            print(f"selected {len(chosen)}, crawled {len(pages)}")

        with log.stage("extract") as st:
            accepted = process(pages, by_url, report)
            st["counts"] = {"extracted": report.extracted, "relevant": report.relevant, "valid": report.valid}

        with log.stage("gates") as st:
            evaluate_run(report)
            st["counts"] = {"passed": int(report.passed)}
            st["notes"] = report.failures

        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        (data_dir / "quality_report.json").write_text(
            json.dumps({"generated_at": now, **report.to_dict()}, indent=2)
        )

        if report.passed:
            with log.stage("store") as st:
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
                (data_dir / "daily_brief.json").write_text(
                    json.dumps({"generated_at": now, "findings": findings}, indent=2, ensure_ascii=False)
                )
                export_all(data_dir)
                st["counts"] = {"startups": len(accepted), "people": report.people, "edges": report.edges}
        return report
    finally:
        log.funnel = {
            "candidates": report.candidates,
            "selected": len(locals().get("chosen", [])),
            "crawled": report.crawled,
            "extracted": report.extracted,
            "relevant": report.relevant,
            "valid": report.valid,
        }
        log.usage = dict(llm.USAGE)
        log.quality = report.to_dict()
        log.passed, log.failures = report.passed, report.failures
        log.write(data_dir)  # always: failed runs are exactly what the dashboard must show
        log.close()


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
