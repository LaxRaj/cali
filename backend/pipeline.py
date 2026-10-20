"""Daily scout: search -> scrape -> extract -> store -> export brief."""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from extractor import extract_profile
from memory import DB_DIR, upsert_profile
from scraper import scrape


async def run(data_dir: Path) -> dict:
    pages = await scrape()
    if not pages:
        raise RuntimeError("search/scrape returned no pages")

    findings = []
    for page in pages:
        try:
            profile = extract_profile(page.markdown)
        except Exception as e:  # one bad page must not sink the run
            print(f"skip {page.url}: {e}", file=sys.stderr)
            continue
        upsert_profile(profile, db_dir=data_dir)
        findings.append({"source_url": page.url, **profile.model_dump()})

    if not findings:
        raise RuntimeError("no profiles could be extracted")

    brief = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "findings": findings,
    }
    (data_dir / "daily_brief.json").write_text(json.dumps(brief, indent=2, ensure_ascii=False))
    return brief


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=DB_DIR)
    args = ap.parse_args()
    args.data_dir.mkdir(parents=True, exist_ok=True)
    brief = asyncio.run(run(args.data_dir))
    print(f"{len(brief['findings'])} profiles written to {args.data_dir}")
