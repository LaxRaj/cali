"""Generate clearly-fictional DEMO data for developing the dashboard without live runs.

    uv run python scripts/make_demo_data.py            # writes ../frontend/demo-data
Companies and people are invented. meta.json marks the folder as demo so the UI shows a banner.
"""

import json
import random
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from export import export_all  # noqa: E402
from memory import upsert_edges, upsert_people, upsert_profile  # noqa: E402
from models import Contact, ContactItem, Edge, Person, StartupProfile  # noqa: E402
from outcomes import mark  # noqa: E402
from rating import rate  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "frontend" / "demo-data"
rng = random.Random(7)
PITCH = "Your {x} is the bottleneck as data grows. I can ship a Next.js front end with vector semantic search so users find answers instantly."

# (name, product, stack, stage, source, bottleneck, founders, investors)
STARTUPS = [
    ("Lumen Index", "Semantic search for legal contracts", ["Python", "Postgres", "React"], "seed", "rss", "keyword search misses clauses", ["Maya Okafor", "Theo Brandt"], ["Northwind Ventures"]),
    ("Vectorly", "Managed vector database for agents", ["Rust", "gRPC", "Kubernetes"], "Series A", "web", "multi-tenant index latency", ["Priya Raman"], ["Harbor Capital", "Northwind Ventures"]),
    ("Paperplane AI", "RAG assistant over company docs", ["Python", "LangChain", "Pinecone"], "pre-seed", "hn", "retrieval quality on messy PDFs", ["Sam Idris", "Lena Fischer"], ["Open Seed Fund"]),
    ("Tidepool Labs", "Observability for ML pipelines", ["Go", "ClickHouse", "Next.js"], "seed", "yc", "slow trace search UI", ["Jon Abara"], ["Harbor Capital"]),
    ("Corvid", "Developer knowledge graph for codebases", ["TypeScript", "Neo4j"], "seed", "hn", "graph queries over big repos", ["Ana Lopes", "Kai Winter"], ["Open Seed Fund", "Northwind Ventures"]),
    ("Fernwood", "Clinical trial matching engine", ["Python", "FastAPI", "Elasticsearch"], "Series A", "rss", "matching free-text eligibility", ["Dr. Nia Hassan"], ["Meridian Bio Partners"]),
    ("Quillbase", "Support-ticket triage with embeddings", ["Python", "Redis", "React"], "pre-seed", "web", "duplicate ticket detection", ["Omar Beck"], []),
    ("Basalt", "Open-source feature store", ["Rust", "Arrow"], "seed", "yc", "online/offline sync", ["Iris Moreau", "Dev Patel"], ["Harbor Capital"]),
    ("Nimbus Notes", "AI notebook with cross-note recall", ["TypeScript", "SQLite"], "pre-seed", "hn", "semantic recall at scale", ["Zoe Tanaka"], ["Open Seed Fund"]),
    ("Gridline", "Geospatial search for logistics", ["Go", "PostGIS", "Next.js"], "seed", "rss", "map search latency", ["Marco Ruiz", "Ines Duarte"], ["Meridian Bio Partners"]),
    ("Hearth", "Voice agent for home services", ["Python", "WebRTC"], "seed", "yc", "call knowledge retrieval", ["Bea Nowak"], ["Northwind Ventures"]),
    ("Pocket Atlas", "Travel itinerary RAG", ["Next.js", "Supabase"], "pre-seed", "web", "grounding answers in sources", ["Ravi Menon"], []),
]
SOURCES = ["hn", "rss", "yc", "web", "hiring", "edgar"]


def build_db(tmp: Path) -> None:
    day = datetime.now(timezone.utc)
    for i, (name, prod, stack, stage, src, bott, founders, investors) in enumerate(STARTUPS):
        when = (day - timedelta(days=i * 2 + 1)).isoformat(timespec="seconds")
        slug = name.lower().replace(" ", "")
        site = f"https://{slug}.example"  # .example is a reserved TLD: nothing here is a real address
        has_contact = i % 3 != 2
        contact = Contact(
            website=site, status="ok", enriched_at=when, contact_page=f"{site}/contact" if has_contact else "",
            pages_crawled=[f"{site}/", f"{site}/about"],
            emails=[ContactItem(value=f"hello@{slug}.example", kind="general", source_url=f"{site}/contact")] if has_contact else [],
            phones=[ContactItem(value=f"+1202555{1000 + i:04d}", kind="main", source_url=f"{site}/contact")] if i % 2 == 0 else [],
            socials={"linkedin": f"https://www.linkedin.com/company/{slug}", "twitter": f"https://x.com/{slug}"} if i % 4 != 3 else {},
        )
        profile = StartupProfile(company_name=name, core_product=prod, tech_stack=stack, likely_bottleneck=bott,
                                 value_prop_pitch=PITCH.format(x=bott.split(" ")[0] + " layer"), is_relevant=True,
                                 funding_stage=stage, funding_amount=f"${2 + i % 5}.{i}M" if i % 3 else "",
                                 hq=["Berlin, Germany", "Austin, USA", "London, UK", ""][i % 4], website=site,
                                 source_url=f"https://example.com/{slug}", discovered_at=when)
        people = [Person(name=f, role="co-founder", org=name, evidence=f"{f} co-founded {name}",
                         linkedin=f"https://www.linkedin.com/in/{f.lower().replace(' ', '-')}" if j == 0 or i % 2 else "",
                         github=f"https://github.com/{f.lower().replace(' ', '')}" if i % 5 == 0 else "",
                         link_source=f"{site}/about")
                  for j, f in enumerate(founders)]
        edges = [Edge(src=f, rel="cofounded" if len(founders) > 1 else "founded", dst=name,
                      evidence=f"{f} co-founded {name}") for f in founders]
        for inv in investors:
            edges.append(Edge(src=inv, rel="invested_in", dst=name, evidence=f"{inv} led the {stage} round"))
        if i % 4 == 0 and i + 1 < len(STARTUPS):
            edges.append(Edge(src=name, rel="competitor_of", dst=STARTUPS[i + 1][0], evidence=f"{name} competes with {STARTUPS[i + 1][0]}"))
        rt = rate(profile, people, edges, contact)
        upsert_profile(profile, db_dir=tmp, extras={"score": rt.score, "score_json": json.dumps({"parts": rt.parts, "gaps": rt.gaps}),
                                                    "contact_json": contact.model_dump_json()})
        upsert_people(people, db_dir=tmp)
        upsert_edges(edges, db_dir=tmp)


def make_runs(out: Path) -> None:
    (out / "runs").mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).replace(hour=6, minute=0, second=0, microsecond=0)
    index = []
    for d in range(30, 0, -1):
        start = now - timedelta(days=d - 1)
        quota_fail = d in (23, 9, 3)
        gate_fail = d in (16, 12)
        cands = rng.randint(70, 130)
        selected = rng.randint(8, 12)
        crawled = selected - rng.randint(0, 2)
        extracted = 1 if quota_fail else crawled - rng.randint(0, 1)
        relevant = max(1, int(extracted * rng.uniform(0.5, 0.8)))
        valid = 1 if quota_fail else (1 if gate_fail else max(3, relevant - rng.randint(0, 1)))
        passed = not (quota_fail or gate_fail)
        tokens = rng.randint(55_000, 120_000) if not quota_fail else rng.randint(150_000, 198_000)
        src_counts = {s: rng.randint(4, 60) for s in SOURCES}
        stage_defs = [("discover", 38, {"candidates": cands}), ("triage", 6, {"in": cands, "selected": selected}),
                      ("crawl", 41, {"requested": selected, "crawled": crawled}),
                      ("extract", 95, {"extracted": extracted, "relevant": relevant, "valid": valid}),
                      ("enrich", 38, {"startups": valid, "websites": valid, "emails": max(0, valid - 1), "phones": valid // 2}),
                      ("gates", 0.1, {"passed": int(passed)})]
        if passed:
            stage_defs.append(("store", 9, {"startups": valid}))
        stages, off = [], 0.0
        for name, base, counts in stage_defs:
            dur = round(base * rng.uniform(0.7, 1.4), 2)
            stages.append({"name": name, "started_at": (start + timedelta(seconds=off)).isoformat(timespec="seconds"),
                           "offset_s": round(off, 2), "duration_s": dur, "status": "ok", "counts": counts,
                           "notes": (["only 1 valid startups (< 3)"] if name == "gates" and not passed else [])})
            off += dur
        failures = (["only 1 valid startups (< 3)", "only 1 discovery sources produced valid startups (< 2)"]
                    if not passed else [])
        errors = ([f"extract failed https://example.com/p{n}: Error code: 429 - rate limit (TPD)" for n in range(selected - 1)]
                  if quota_fail else [])
        run_id = start.strftime("%Y%m%dT%H%M%SZ")
        accepted = [{"company": s[0], "url": f"https://example.com/{s[0].lower()}", "source": s[4], "people": len(s[6]),
                     "edges": len(s[6]) + len(s[7]), "score": rng.randint(45, 95),
                     "gaps": rng.sample(["email", "phone", "investors", "people profiles", "location"], rng.randint(0, 3)),
                     "website": f"https://{s[0].lower().replace(' ', '')}.example", "emails": rng.randint(0, 2), "phones": rng.randint(0, 1)}
                    for s in rng.sample(STARTUPS, min(valid, len(STARTUPS)))] if valid else []
        stats = {s: {"crawled": rng.randint(4, 30), "accepted": 0, "yield": 0.0, "avg_score": 0.0} for s in SOURCES + ["launch_hn"]}
        for s_, st in stats.items():
            st["accepted"] = rng.randint(0, st["crawled"] // 2)
            st["yield"] = round(st["accepted"] / st["crawled"], 3)
            st["avg_score"] = round(rng.uniform(40, 85), 1) if st["accepted"] else 0.0
        caps = {s_: max(2, min(7, round(12 * (st["yield"] + 0.15) / 1.6))) for s_, st in stats.items()}
        run = {
            "run_id": run_id, "started_at": start.isoformat(timespec="seconds"), "duration_s": round(off, 1),
            "passed": passed, "status": "passed" if passed else ("quota" if quota_fail else "failed"),
            "failures": failures, "tokens": tokens, "token_budget": 200_000,
            "funnel": {"candidates": cands, "selected": selected, "crawled": crawled, "extracted": extracted,
                       "relevant": relevant, "valid": valid},
            "sources": src_counts,
            "feedback": {"source_stats": stats, "caps": caps},
            "decisions": {"provider": "local", "calls": cands + selected, "fallbacks": 0,
                          "avg_latency_ms": round(rng.uniform(55, 95), 1), "jev_input_tokens": 0,
                          "gated_pages": (gated := rng.randint(0, 3)), "tokens_saved_est": gated * 4500},
            "plan": {"web_queries": ["seed round semantic search startup", "Series A RAG platform launch"],
                     "hn_keywords": ["RAG", "vector search", "developer tools"]},
            "stages": stages,
            "source_health": {s: {"candidates": c, "seconds": round(rng.uniform(0.8, 9), 2),
                                  "error": "" if not (s == "web" and d % 7 == 0) else "No results found."}
                              for s, c in src_counts.items()},
            "usage": {"prompt_tokens": int(tokens * 0.9), "completion_tokens": int(tokens * 0.1),
                      "total_tokens": tokens, "calls": selected + 2},
            "quality": {"candidates": cands, "crawled": crawled, "extracted": extracted, "relevant": relevant,
                        "valid": valid, "passed": passed, "failures": failures,
                        "validity_rate": round(valid / relevant, 3) if relevant else 0,
                        "dropped_ungrounded": rng.randint(0, 9),
                        "enriched": valid, "with_website": valid, "with_email": max(0, valid - 1),
                        "with_phone": valid // 2, "people_linked": valid, "avg_score": round(rng.uniform(55, 80), 1)},
            "accepted": accepted,
            "rejections": [{"url": f"https://example.com/junk{n}", "source": rng.choice(SOURCES),
                            "reasons": [rng.choice(["not a relevant startup page", "missing core_product"])]}
                           for n in range(relevant and extracted - relevant)],
            "errors": errors,
        }
        (out / "runs" / f"{run_id}.json").write_text(json.dumps(run, indent=2))
        index.append({k: run[k] for k in ("run_id", "started_at", "duration_s", "passed", "status", "funnel", "tokens", "token_budget", "sources", "failures")})
    (out / "runs_index.json").write_text(json.dumps({"runs": index}, indent=2))
    latest_ok = next(r for r in reversed(index) if r["passed"])
    q = json.loads((out / "runs" / f"{latest_ok['run_id']}.json").read_text())["quality"]
    (out / "quality_report.json").write_text(json.dumps({"generated_at": latest_ok["started_at"], **q, "sources": latest_ok["sources"], "people": 14, "edges": 22, "issues": {}}, indent=2))


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        build_db(tmp)
        now = datetime.now(timezone.utc)
        mark("Vectorly", "contacted", "emailed team@; no reply yet", tmp, now=now - timedelta(days=9))  # -> follow_up
        mark("Lumen Index", "replied", "asked for a call next week", tmp, now=now - timedelta(days=2))
        mark("Fernwood", "passed", "healthcare, not our focus", tmp, now=now - timedelta(days=5))
        export_all(tmp)
        shutil.copy(tmp / "profiles.json", OUT / "profiles.json")
        shutil.copy(tmp / "graph.json", OUT / "graph.json")
        shutil.copy(tmp / "outcomes.json", OUT / "outcomes.json")
    make_runs(OUT)
    profiles = json.loads((OUT / "profiles.json").read_text())
    (OUT / "daily_brief.json").write_text(json.dumps({"generated_at": profiles[0]["discovered_at"], "findings": profiles[:4]}, indent=2))
    (OUT / "meta.json").write_text(json.dumps({"demo": True, "note": "Fictional demo data. Not real startups."}))
    print(f"demo data written to {OUT}")


if __name__ == "__main__":
    main()
