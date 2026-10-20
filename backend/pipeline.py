"""Daily scout: plan -> discover -> triage -> crawl -> extract -> enrich -> rate -> gates -> store -> export."""

import argparse
import asyncio
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import llm
import telemetry
from decide.decisions import gate_page
from decide.registry import STATS as DECIDER_STATS, get_provider, reset_stats
from discovery import Candidate, edgar, hiring, hn, normalize_url, rss, web, yc
from discovery.feedback import allocate, source_stats
from discovery.planner import make_plan
from discovery.triage import select
from backfill import backfill
from enrich import EnrichResult, enrich_startup
from enrich_github import enrich_people_github
from decide.training import append_decisions
from train_decider import train
from export import export_all
from extractor import extract, extract_people
from memory import DB_DIR, mark_seen, seen_urls, upsert_edges, upsert_people, upsert_profile
from models import Contact
from quality import RunReport, check_extraction, evaluate_run, tidy
from rating import rate
from scraper import Page, scrape_urls, search_results

MAX_PEOPLE_SEARCHES = 12  # public-search lookups for founders' profile links, per run
BACKFILL_LIMIT = 3  # older stored startups re-enriched per run
AVG_EXTRACTION_TOKENS = 4500  # for the 'tokens saved' estimate when a page is gated
MAX_GITHUB_LOOKUPS = 30  # public profile API calls per run
TARGET_VALID = 8  # stop extracting once this many startups passed validation
MAX_TEAM_LLM = 6  # About/Team page extraction calls (Groq tokens), per run


def enrichment_enabled() -> bool:
    return os.environ.get("CALI_ENRICH", "1") != "0"


def gate_enabled() -> bool:
    return os.environ.get("CALI_GATE", "1") != "0"


def search_fn(query: str) -> list[dict]:
    time.sleep(1)  # be gentle with the search engines
    return search_results(query, 5, attempts=1)


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
        guarded("edgar", edgar.fetch),  # off unless CALI_CONTACT_EMAIL is set (SEC User-Agent policy)
        guarded("hiring", hiring.fetch),
    )
    cands = [c for r in results for c in r]
    print("candidates per source:", dict(Counter(c.source for c in cands)))
    return cands


def process(pages, by_url: dict[str, Candidate], report: RunReport):
    """Extract + validate every page. Returns [(extraction, source, markdown)] for accepted startups."""
    log = telemetry.current()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    accepted = []
    for page in pages:
        if report.valid >= TARGET_VALID:  # enough good startups for today: the tail would only burn tokens
            report.deferred_urls.append(normalize_url(page.url))
            continue
        if report.quota_exhausted:
            if log:
                log.rejection(page.url, by_url.get(normalize_url(page.url), Candidate("", "", "", "unknown")).source, ["extraction error"])
            continue
        cand = by_url.get(normalize_url(page.url))
        source = cand.source if cand else "unknown"
        title, snippet, triage = (cand.title, cand.snippet, cand.triage) if cand else ("", "", 0.0)
        if gate_enabled():
            gate = gate_page(page.markdown, title=title)
            if not gate.ok:  # looks like a guide/listicle/hobby page: don't spend LLM tokens on it
                report.gated += 1
                print(f"gate {page.url}: p={gate.p}", file=sys.stderr)
                if log:
                    log.rejection(page.url, source, [f"gated: not a startup page (p={gate.p})"])
                    log.candidate(page.url, source, title, snippet, triage, "gated")
                continue
        try:
            ex = extract(page.markdown)
        except Exception as e:
            print(f"extract failed {page.url}: {e}", file=sys.stderr)
            report.issues["extraction error"] = report.issues.get("extraction error", 0) + 1
            if llm.quota_exhausted(e):
                report.quota_exhausted = True  # stop spending time on a dead quota; the rest are skipped
            if log:
                log.error(f"extract failed {page.url}: {e}")
                log.rejection(page.url, source, ["extraction error"])
                log.candidate(page.url, source, title, snippet, triage, "error")
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
            kept = checked.extraction
            # links the LLM read off this very page (already grounded by quality.filter_people)
            people = [
                p.model_copy(update={"link_source": page.url})
                if (p.linkedin or p.twitter or p.github or p.homepage) and not p.link_source
                else p
                for p in kept.people
            ]
            accepted.append((tidy(kept.model_copy(update={"people": people})), source, page.markdown))
            if log:
                log.accept(ex.startup.company_name, page.url, source, len(people), len(kept.edges))
                log.candidate(page.url, source, title, snippet, triage, "accepted")
        for issue in checked.issues:
            report.issues[issue] = report.issues.get(issue, 0) + 1
        if not checked.accepted:
            print(f"reject {page.url}: {checked.issues}", file=sys.stderr)
            if log:
                log.rejection(page.url, source, checked.issues)
                log.candidate(page.url, source, title, snippet, triage, "rejected")
    return accepted


async def enrich_all(accepted, log) -> list[EnrichResult]:
    """Contacts, socials, team page and people links for each accepted startup (never fatal)."""
    results = []
    search_budget, team_budget, gh_budget = [MAX_PEOPLE_SEARCHES], [MAX_TEAM_LLM], [MAX_GITHUB_LOOKUPS]
    github_fn = lambda people: enrich_people_github(people, budget=gh_budget)  # noqa: E731
    for ex, source, md in accepted:
        try:
            res = await enrich_startup(
                ex, source, md, search_fn=search_fn, extract_fn=extract_people,
                search_budget=search_budget, team_budget=team_budget, github_fn=github_fn,
            )
        except Exception as e:
            log.error(f"enrich failed {ex.startup.company_name}: {e}")
            res = EnrichResult(ex, Contact(status="crawl_failed"), [f"error: {e}"])
        results.append(res)
        print(f"enriched {ex.startup.company_name}: {res.contact.status}, "
              f"{len(res.contact.emails)} emails, {len(res.contact.phones)} phones; {res.notes}")
    return results


async def run(data_dir: Path) -> RunReport:
    if llm.quota_blocked(data_dir):  # every Groq key is spent until 00:00 UTC: crawling now would be wasted work
        print("Groq daily quota is spent (data/quota.json); skipping this run. CALI_IGNORE_QUOTA=1 overrides.")
        return RunReport(skipped="groq quota exhausted")
    os.environ["CALI_DATA_DIR"] = str(data_dir)  # caches (extractions, plan) live beside the data
    log = telemetry.RunLog()
    llm.reset_usage()
    report = RunReport()
    try:
        with log.stage("discover") as st:
            cands = await discover()
            report.candidates = len(cands)
            st["counts"] = {"candidates": len(cands), **{f"src_{k}": v for k, v in Counter(c.source for c in cands).items()}}

        with log.stage("triage") as st:
            stats = source_stats(data_dir)
            caps = allocate(stats, sorted({c.source for c in cands}))
            log.feedback = {"source_stats": stats, "caps": caps}
            decider = get_provider()
            reset_stats(decider.name)
            chosen = select(cands, seen_urls(data_dir), caps=caps, decider=decider)
            by_url = {normalize_url(c.url): c for c in chosen}
            st["counts"] = {"in": len(cands), "selected": len(chosen)}
            st["notes"] = [f"crawl caps by source: {caps}", f"decider: {decider.name}"]

        with log.stage("crawl") as st:
            inline = []  # candidates whose text we already have (Launch HN, hiring posts, SEC filings)
            for c in (c for c in chosen if c.content):
                content = c.content
                if c.source == "edgar":  # a filing has no product description: add the company's own homepage
                    content = await edgar.materialize(c, search_fn=search_fn)
                    if content is None:
                        print(f"edgar: no website found for {c.company}; skipping", file=sys.stderr)
                        log.rejection(c.url, c.source, ["no company website found"])
                        log.candidate(c.url, c.source, c.title, c.snippet, c.triage, "no_website")
                        continue
                inline.append(Page(c.url, content))
            crawled = await scrape_urls([c.url for c in chosen if not c.content])
            order = {normalize_url(c.url): i for i, c in enumerate(chosen)}  # best-ranked first
            pages = sorted(inline + crawled, key=lambda p: order.get(normalize_url(p.url), 99))
            report.crawled = len(pages)
            st["counts"] = {"requested": len(chosen), "crawled": len(pages)}
            print(f"selected {len(chosen)}, crawled {len(pages)}")

        with log.stage("extract") as st:
            accepted = process(pages, by_url, report)
            st["counts"] = {"extracted": report.extracted, "relevant": report.relevant, "valid": report.valid}

        # Enrich + rate only startups that passed validation (cheap, and avoids crawling junk sites).
        results: list[EnrichResult] = []
        if enrichment_enabled() and accepted and not report.quota_exhausted:
            with log.stage("enrich") as st:
                results = await enrich_all(accepted, log)
                st["counts"] = {
                    "startups": len(results),
                    "websites": sum(1 for r in results if r.contact.website),
                    "emails": sum(len(r.contact.emails) for r in results),
                    "phones": sum(len(r.contact.phones) for r in results),
                }
                st["notes"] = [n for r in results for n in r.notes][:10]
        else:
            results = [EnrichResult(ex, Contact(status="disabled"), []) for ex, _, _ in accepted]

        ratings = [rate(r.extraction.startup, r.extraction.people, r.extraction.edges, r.contact) for r in results]
        for a, r, rt in zip(log.accepted, results, ratings):
            a.update(score=rt.score, gaps=rt.gaps, website=r.contact.website,
                     emails=len(r.contact.emails), phones=len(r.contact.phones))
        scores_by_url = {a["url"]: a.get("score") for a in log.accepted}
        for row in log.candidate_log:
            if row["outcome"] == "accepted":
                row["score"] = scores_by_url.get(row["url"])
        report.enriched = sum(1 for r in results if r.contact.status == "ok")
        report.with_website = sum(1 for r in results if r.contact.website)
        report.with_email = sum(1 for r in results if r.contact.emails)
        report.with_phone = sum(1 for r in results if r.contact.phones)
        report.people = sum(len(r.extraction.people) for r in results)
        report.edges = sum(len(r.extraction.edges) for r in results)
        report.people_linked = sum(
            1 for r in results for p in r.extraction.people if p.linkedin or p.twitter or p.github
        )
        report.avg_score = round(sum(rt.score for rt in ratings) / len(ratings), 1) if ratings else 0.0

        with log.stage("gates") as st:
            evaluate_run(report)
            st["counts"] = {"passed": int(report.passed), "avg_score": int(report.avg_score)}
            st["notes"] = report.failures

        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        (data_dir / "quality_report.json").write_text(
            json.dumps({"generated_at": now, **report.to_dict()}, indent=2)
        )

        if not report.passed and report.extracted and not report.quota_exhausted:
            # paid-for pages: never re-crawl them tomorrow (their extractions are cached too)
            mark_seen([u for u in (normalize_url(p.url) for p in pages) if u not in report.deferred_urls], db_dir=data_dir)

        if report.passed:
            with log.stage("store") as st:
                findings = []
                for (ex, source, _), res, rt in zip(accepted, results, ratings):
                    s, people, edges = res.extraction.startup, res.extraction.people, res.extraction.edges
                    upsert_profile(
                        s, db_dir=data_dir,
                        extras={
                            "score": rt.score,
                            "score_json": json.dumps({"parts": rt.parts, "gaps": rt.gaps}),
                            "contact_json": res.contact.model_dump_json(),
                        },
                    )
                    upsert_people(people, db_dir=data_dir)
                    upsert_edges(edges, db_dir=data_dir)
                    findings.append(
                        {
                            **s.model_dump(), "source": source, "score": rt.score, "gaps": rt.gaps,
                            "contact": res.contact.model_dump(),
                            "people": [p.model_dump() for p in people], "edges": [e.model_dump() for e in edges],
                        }
                    )
                mark_seen([u for u in (normalize_url(c.url) for c in chosen) if u not in report.deferred_urls], db_dir=data_dir)
                (data_dir / "daily_brief.json").write_text(
                    json.dumps({"generated_at": now, "findings": findings}, indent=2, ensure_ascii=False)
                )
                export_all(data_dir)
                st["counts"] = {"startups": len(findings), "people": report.people, "edges": report.edges}

            # Rows stored before enrichment existed (or whose enrichment failed) get a few attempts per run.
            if enrichment_enabled() and not report.quota_exhausted:
                with log.stage("backfill") as st:
                    done = await backfill(data_dir, limit=BACKFILL_LIMIT, search_fn=search_fn)
                    st["counts"] = {"startups": len(done), "emails": sum(d["emails"] for d in done)}
                    st["notes"] = [f"{d['company']}: {d['status']}, score {d['score']}" for d in done]
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
        calls = DECIDER_STATS["calls"]
        log.decisions = {
            "provider": DECIDER_STATS["provider"], "calls": calls, "fallbacks": DECIDER_STATS["fallbacks"],
            "avg_latency_ms": round(DECIDER_STATS["latency_ms"] / calls, 1) if calls else 0.0,
            "jev_input_tokens": DECIDER_STATS["jev_input_tokens"],
            "gated_pages": report.gated, "tokens_saved_est": report.gated * AVG_EXTRACTION_TOKENS,
        }
        append_decisions(data_dir, log.run_id, log.candidate_log)
        try:
            train(data_dir)  # cheap; returns None until there are enough labelled rows
        except Exception as e:
            log.error(f"decider training skipped: {e}")
        if report.quota_exhausted:
            llm.mark_quota_exhausted(data_dir)
        log.usage = {**llm.USAGE, "by_purpose": {k: dict(v) for k, v in llm.USAGE_BY.items()}}
        log.quality = report.to_dict()
        log.passed, log.failures = report.passed, report.failures
        log.quota_exhausted, log.token_budget = report.quota_exhausted, llm.token_budget()
        log.write(data_dir)  # always: failed runs are exactly what the dashboard must show
        log.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=DB_DIR)
    args = ap.parse_args()
    args.data_dir.mkdir(parents=True, exist_ok=True)
    rep = asyncio.run(run(args.data_dir))
    print(json.dumps(rep.to_dict(), indent=2))
    if rep.skipped:
        sys.exit(0)
    if not rep.passed:
        print("QUALITY GATES FAILED: " + "; ".join(rep.failures), file=sys.stderr)
        sys.exit(1)
