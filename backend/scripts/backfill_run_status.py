"""Add `status` to runs_index.json entries written before the field existed.

    uv run python scripts/backfill_run_status.py [--data-dir DIR]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from memory import DB_DIR  # noqa: E402
from telemetry import backfill_index  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=DB_DIR)
    args = ap.parse_args()
    print(f"backfilled {backfill_index(args.data_dir)} index entries")
