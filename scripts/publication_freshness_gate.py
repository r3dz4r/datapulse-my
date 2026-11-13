#!/usr/bin/env python3
"""Compare served health with its published artifact; separately bound deployment age."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import logging
import math
import re
import sys
from typing import Literal


LOGGER = logging.getLogger(__name__)
UTC_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+00:00)\Z")
HEALTH_CYCLE_MINUTES = 5
CONTENT_LAG_TOLERANCE_CYCLES = 2
CONTENT_LAG_TOLERANCE = timedelta(
    minutes=HEALTH_CYCLE_MINUTES * CONTENT_LAG_TOLERANCE_CYCLES,
)
EXIT_CODES = {"fresh": 0, "stale": 1, "unknown": 2, "served_newer": 0}


def _parse_utc(value: str) -> datetime:
    if not UTC_TIMESTAMP.fullmatch(value):
        raise ValueError("expected an ISO-8601 UTC timestamp")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _age_hours(timestamp: str | None, now: str) -> float | None:
    try:
        age = _parse_utc(now) - _parse_utc(timestamp or "")
    except (TypeError, ValueError):
        return None
    # A future deployment is unreadable evidence, not proof of freshness.
    return age / timedelta(hours=1) if age >= timedelta(0) else None


def freshness_verdict(
    served_checked_at: str | None,
    repository_checked_at: str | None,
) -> Literal["fresh", "stale", "unknown", "served_newer"]:
    """Allow two producer cycles of lag; a newer store is a distinct state."""
    try:
        lag = _parse_utc(repository_checked_at or "") - _parse_utc(served_checked_at or "")
    except (TypeError, ValueError):
        return "unknown"
    if lag < timedelta(0):
        return "served_newer"
    return "stale" if lag > CONTENT_LAG_TOLERANCE else "fresh"


def deployment_age_verdict(
    last_production_deployment_created_at: str | None,
    now: str,
    max_age_hours: float = 24,
) -> Literal["fresh", "stale", "unknown"]:
    """Pure age gate: the bound is inclusive; invalid or future input is unknown."""
    age = _age_hours(last_production_deployment_created_at, now)
    if age is None or not math.isfinite(max_age_hours) or max_age_hours <= 0:
        return "unknown"
    return "stale" if age > max_age_hours else "fresh"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--served-checked-at", help="Served /health/latest.json checked_at (UTC)")
    parser.add_argument("--published-observed-at", "--repository-checked-at", dest="reference_checked_at",
                        help="Published artifact observed_at (UTC); legacy repository option retained")
    parser.add_argument("--deployment-age-only", action="store_true",
                        help="Run the independent secondary deployment-age condition")
    parser.add_argument("--timestamp", help="Canonical production deployment created_on (UTC)")
    parser.add_argument("--now", help="Override current UTC time for deterministic checks")
    parser.add_argument("--max-age-hours", default="24", help="Maximum deployment age (default: 24)")
    args = parser.parse_args(argv)
    if not args.deployment_age_only:
        verdict = freshness_verdict(args.served_checked_at, args.reference_checked_at)
        LOGGER.info("%s: content freshness; served_checked_at=%s; published_observed_at=%s; "
                    "tolerance %s pipeline cycles (%s minutes)",
                    verdict, args.served_checked_at, args.reference_checked_at,
                    CONTENT_LAG_TOLERANCE_CYCLES,
                    HEALTH_CYCLE_MINUTES * CONTENT_LAG_TOLERANCE_CYCLES)
        return EXIT_CODES[verdict]
    now = args.now if args.now is not None else datetime.now(timezone.utc).isoformat()
    try:
        bound = float(args.max_age_hours)
    except ValueError:
        bound = math.nan
    verdict = deployment_age_verdict(args.timestamp, now, bound)
    age = _age_hours(args.timestamp, now)
    measured = "unknown" if age is None else f"{age:.6f}h"
    reason = (
        "; missing or invalid UTC timestamp, clock, or positive finite bound"
        if verdict == "unknown" else ""
    )
    LOGGER.info("%s: production deployment age %s; bound %gh%s", verdict, measured, bound, reason)
    return EXIT_CODES[verdict]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
    raise SystemExit(main())
