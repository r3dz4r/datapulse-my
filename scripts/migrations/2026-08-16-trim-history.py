#!/usr/bin/env python3
"""Move expired raw health observations to monthly gzip archives."""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from gen_health_history import (  # noqa: E402
    DEFAULT_ARCHIVES_DIR,
    DEFAULT_HISTORY,
    archive_rows,
    parse_datetime,
    read_history,
    write_history,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    parser.add_argument("--archives-dir", type=Path, default=DEFAULT_ARCHIVES_DIR)
    parser.add_argument("--retention-days", type=int, default=7)
    parser.add_argument("--now", help="cutoff reference as an ISO 8601 timestamp")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.retention_days < 1:
        raise SystemExit("--retention-days must be at least 1")
    now = parse_datetime(args.now, field="now") if args.now else datetime.now(UTC)
    cutoff = now - timedelta(days=args.retention_days)
    rows = read_history(args.history)
    retained = [
        row
        for row in rows
        if parse_datetime(row["observed_at"], field="observed_at") >= cutoff
    ]
    expired = [row for row in rows if row not in retained]
    archive_rows(expired, args.archives_dir)
    write_history(args.history, retained)
    print(f"archived {len(expired)} rows to {args.archives_dir}")
    print(f"retained {len(retained)} rows in {args.history}")


if __name__ == "__main__":
    main()
