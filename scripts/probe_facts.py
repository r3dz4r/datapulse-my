#!/usr/bin/env python3
"""Additive shape facts for an already-downloaded probe body.

The health probe already reduces each body to ``record_count`` and a shape
fingerprint. This helper extracts the date geometry that is otherwise thrown
away: the newest and oldest ISO date, how many rows sit on each date, the
largest gap between consecutive dates, and the distinct-value count of
low-cardinality string columns.

Rules that matter more than the field list:

* **Never guess a date.** A column whose name looks date-ish is only treated as
  a date column when every non-empty value parses as an ISO ``YYYY-MM-DD``
  date (or a full ISO timestamp, whose date part is used). A column with
  ``01/08/2026`` or ``2026-09`` therefore reports no date at all rather than a
  plausible-looking wrong one. A wrong newest/oldest date silently invalidates
  every downstream freshness check, so absence is the safe failure mode.
* **Deterministic.** The same body yields byte-identical JSON; cardinality keys
  are sorted and columns are considered in sorted order.
* **Never raises at the CLI.** Malformed, empty, or binary bodies produce a
  well-formed all-null object; the probe must not fail because a payload is
  odd.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from collections import Counter
from datetime import date
from typing import Any

# Column names that may hold a date. This is only a *candidate* filter: the
# value parse below is the gate that actually decides. False positives such as
# a numeric "runtime" column are harmless because their values do not parse.
_DATE_COLUMN_RE = re.compile(
    r"date|tarikh|period|month|year|timestamp|time", re.IGNORECASE
)

# ISO date, optionally followed by a time component and timezone. The date part
# must be exactly YYYY-MM-DD so short forms ("2026-09") are never inferred.
_ISO_DATE_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})"
    r"(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:[Zz]|[+-]\d{2}:?\d{2})?)?$"
)

# The same wrapped-row keys the shell probe treats as a tabular array.
_WRAPPER_KEYS = ("data", "result", "results", "records", "items", "rows")

_MAX_DIMENSIONS = 8
_MAX_DIMENSION_CARDINALITY = 200


def null_facts() -> dict[str, Any]:
    """Return the canonical all-null fact object.

    ``distinct_dates`` is 0 and ``dimension_cardinality`` is ``{}`` to match
    the "no date column" / "no qualifying dimension" shapes.
    """
    return {
        "newest_date": None,
        "oldest_date": None,
        "distinct_dates": 0,
        "rows_per_date": None,
        "largest_gap_days": None,
        "dimension_cardinality": {},
    }


def _parse_iso_date(value: object) -> str | None:
    """Return ``YYYY-MM-DD`` for an ISO date/timestamp, else ``None``.

    The regex rejects ambiguous local formats before ``date`` validates the
    calendar fields, so ``2026-13-01`` is also rejected rather than rounded.
    """
    if not isinstance(value, str):
        return None
    match = _ISO_DATE_RE.match(value.strip())
    if match is None:
        return None
    try:
        parsed = date(*(int(part) for part in match.groups()))
    except ValueError:
        return None
    return parsed.isoformat()


def _is_absent(value: object) -> bool:
    """True for missing values that legitimately carry no date evidence."""
    if value is None:
        return True
    return isinstance(value, str) and value.strip() == ""


def _rows_from_document(document: object) -> list | None:
    """Return the tabular rows of a JSON body, or ``None`` when there are none."""
    if isinstance(document, list):
        return document
    if isinstance(document, dict):
        for key in _WRAPPER_KEYS:
            value = document.get(key)
            if isinstance(value, list):
                return value
    return None


def _rows_from_csv(text: str) -> list[dict[str, str]]:
    """Parse a CSV body into dict rows keyed by the (BOM-stripped) header."""
    reader = csv.reader(io.StringIO(text), strict=True)
    try:
        headers = next(reader)
    except StopIteration:
        return []
    normalized = [header.strip() for header in headers]
    if normalized:
        normalized[0] = normalized[0].lstrip("\ufeff")
    rows: list[dict[str, str]] = []
    for values in reader:
        row = {
            header: values[index] if index < len(values) else ""
            for index, header in enumerate(normalized)
        }
        rows.append(row)
    return rows


def _facts_from_rows(rows: list | None) -> dict[str, Any]:
    if rows is None:
        return null_facts()

    # Pass 1: decide which columns are genuinely date columns. The name must be
    # date-ish *and* every non-empty value must parse; a column that fails
    # either test is not a date column. We never fall back to a partial
    # interpretation.
    date_values: dict[str, set[str]] = {}
    date_rejected: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        for column, value in row.items():
            if not isinstance(column, str) or _is_absent(value):
                continue
            if _DATE_COLUMN_RE.search(column) is None:
                continue
            if column in date_rejected:
                continue
            parsed = _parse_iso_date(value)
            if parsed is None:
                date_rejected.add(column)
                date_values.pop(column, None)
            else:
                date_values.setdefault(column, set()).add(parsed)
    date_columns = {
        column for column in date_values if column not in date_rejected
    }

    # Pass 2: count rows per date and profile non-date string columns.
    date_counts: Counter[str] = Counter()
    dimension_values: dict[str, set[str]] = {}
    dimension_rejected: set[str] = set()
    dimension_seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        row_dates: set[str] = set()
        for column, value in row.items():
            if not isinstance(column, str):
                continue
            if column in date_columns:
                parsed = _parse_iso_date(value)
                if parsed is not None:
                    row_dates.add(parsed)
                continue
            if column in dimension_rejected or _is_absent(value):
                continue
            if not isinstance(value, str):
                # The dimension contract is string-valued only; a numeric
                # column is not a categorical dimension even if it repeats.
                dimension_rejected.add(column)
                dimension_values.pop(column, None)
                continue
            dimension_seen.add(column)
            bucket = dimension_values.setdefault(column, set())
            if len(bucket) <= _MAX_DIMENSION_CARDINALITY:
                bucket.add(value)
        # A row contributes once per distinct date even if several date columns
        # name the same day, so rows_per_date counts rows rather than cells.
        for observed in row_dates:
            date_counts[observed] += 1

    all_dates = sorted({value for column in date_columns for value in date_values[column]})

    rows_per_date: dict[str, float | int] | None = None
    largest_gap_days: int | None = None
    if all_dates:
        counts = [date_counts[observed] for observed in all_dates]
        rows_per_date = {
            "min": min(counts),
            "mean": sum(counts) / len(counts),
            "max": max(counts),
        }
        if len(all_dates) >= 2:
            largest_gap_days = max(
                (date.fromisoformat(second) - date.fromisoformat(first)).days
                for first, second in zip(all_dates, all_dates[1:])
            )

    dimension_cardinality = {
        column: len(dimension_values[column])
        for column in sorted(dimension_seen)
        if column not in dimension_rejected
        and len(dimension_values[column]) <= _MAX_DIMENSION_CARDINALITY
    }
    dimension_cardinality = dict(
        sorted(dimension_cardinality.items())[:_MAX_DIMENSIONS]
    )

    return {
        "newest_date": all_dates[-1] if all_dates else None,
        "oldest_date": all_dates[0] if all_dates else None,
        "distinct_dates": len(all_dates),
        "rows_per_date": rows_per_date,
        "largest_gap_days": largest_gap_days,
        "dimension_cardinality": dimension_cardinality,
    }


def facts_from_json(text: str) -> dict[str, Any]:
    """Compute facts for a JSON array (or wrapped-row object) body."""
    return _facts_from_rows(_rows_from_document(json.loads(text)))


def facts_from_csv(text: str) -> dict[str, Any]:
    """Compute facts for a CSV body with a header row."""
    return _facts_from_rows(_rows_from_csv(text))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Emit additive date/dimension facts for a probe body."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--json", action="store_true", help="read a JSON body")
    mode.add_argument(
        "--csv", action="store_true", help="read a CSV body with a header row"
    )
    args = parser.parse_args()

    try:
        text = sys.stdin.read()
        if args.json:
            facts = facts_from_json(text)
        else:
            facts = facts_from_csv(text)
    except (
        csv.Error,
        json.JSONDecodeError,
        OSError,
        RecursionError,
        TypeError,
        UnicodeError,
        ValueError,
    ):
        # Odd payloads are data, not failures: report absence honestly.
        facts = null_facts()

    print(json.dumps(facts, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
