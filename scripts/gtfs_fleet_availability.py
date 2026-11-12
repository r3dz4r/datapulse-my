#!/usr/bin/env python3
"""Report GTFS realtime fleet availability from the stored observation history.

Reads ``health/history.jsonl`` read-only, one line at a time, and summarises the
vehicle counts that ``probe_gtfs.py`` already records as ``record_count`` for
every ``gtfs_realtime_*`` dataset. No network access and no writes: the report
goes to stdout as JSON (default) or as a human table (``--table``).

Metric contract (schema ``datapulse/v1/gtfs-fleet-availability``):

* operator key: ``dataset_id`` with the ``gtfs_realtime_`` prefix removed.
* bucket: (operator, UTC date, UTC hour) taken verbatim from ``cycle``
  (``YYYY-MM-DDTHH:MM``); a row whose cycle has any other shape, or a selected
  line that is not a JSON object, is counted in ``skipped_rows`` and ignored.
* per bucket: ``cycles``; ``vehicles_min``/``vehicles_max``/``vehicles_median``
  over rows whose ``record_count_estimated`` is false and whose ``record_count``
  is an integer (null when there are none; the median is the lower median so it
  stays an integer); ``zero_vehicle_cycles`` (``record_count == 0``);
  ``estimated_cycles`` (``record_count_estimated`` is true).
* per operator: maximal runs of consecutive observations, ordered by cycle,
  whose ``record_count`` is 0. Any other observation, including a null count,
  ends a run.
* ``as_of``: the maximum cycle among the rows the report covers, never the
  wall clock.

Identical input bytes produce byte-identical output: every list is sorted
explicitly and JSON keys are sorted.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable
from datetime import date, datetime
from pathlib import Path
from statistics import median_low
from typing import Any, TextIO

SCHEMA = "datapulse/v1/gtfs-fleet-availability"
PREFIX = "gtfs_realtime_"
DEFAULT_HISTORY = Path("/srv/datapulse-my/health/history.jsonl")
CYCLE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})", re.ASCII)
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}", re.ASCII)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def parse_cycle(cycle: Any) -> tuple[str, int] | None:
    """Return (date, hour) for a well-formed UTC minute cycle, else None."""
    if not isinstance(cycle, str):
        return None
    match = CYCLE_RE.fullmatch(cycle)
    if match is None:
        return None
    try:
        datetime.strptime(cycle, "%Y-%m-%dT%H:%M")
    except ValueError:
        return None
    return match.group(1), int(match.group(2))


def operator_key(dataset_id: str) -> str:
    return dataset_id[len(PREFIX):]


def build_report(lines: Iterable[str], since: str | None = None) -> dict[str, Any]:
    """Aggregate history lines into the fleet-availability report."""
    skipped = 0
    as_of: str | None = None
    # (operator, date, hour) -> [cycles, zero, estimated, [counts...]]
    buckets: dict[tuple[str, str, int], list[Any]] = {}
    # operator -> dataset_id
    dataset_ids: dict[str, str] = {}
    # operator -> [(cycle, observed_at, line_index, is_zero)]
    sequences: dict[str, list[tuple[str, str, int, bool]]] = {}

    for index, line in enumerate(lines):
        if PREFIX not in line:
            continue  # cheap pre-filter; cannot be a selected row
        try:
            row = json.loads(line)
        except ValueError:
            skipped += 1
            continue
        if not isinstance(row, dict):
            skipped += 1
            continue
        dataset_id = row.get("dataset_id")
        if not isinstance(dataset_id, str) or not dataset_id.startswith(PREFIX):
            continue
        cycle = row.get("cycle")
        parsed = parse_cycle(cycle)
        if parsed is None:
            skipped += 1
            continue
        day, hour = parsed
        if since is not None and day < since:
            continue

        operator = operator_key(dataset_id)
        dataset_ids[operator] = dataset_id
        record_count = row.get("record_count")
        estimated = row.get("record_count_estimated") is True
        is_zero = _is_int(record_count) and record_count == 0

        bucket = buckets.setdefault((operator, day, hour), [0, 0, 0, []])
        bucket[0] += 1
        if is_zero:
            bucket[1] += 1
        if estimated:
            bucket[2] += 1
        elif _is_int(record_count):
            bucket[3].append(record_count)

        observed_at = row.get("observed_at")
        sequences.setdefault(operator, []).append(
            (cycle, observed_at if isinstance(observed_at, str) else "", index, is_zero)
        )
        if as_of is None or cycle > as_of:
            as_of = cycle

    bucket_rows: list[dict[str, Any]] = []
    for (operator, day, hour) in sorted(buckets):
        cycles, zero, estimated_n, counts = buckets[(operator, day, hour)]
        bucket_rows.append(
            {
                "operator": operator,
                "date": day,
                "hour": hour,
                "cycles": cycles,
                "vehicles_min": min(counts) if counts else None,
                "vehicles_max": max(counts) if counts else None,
                "vehicles_median": median_low(counts) if counts else None,
                "zero_vehicle_cycles": zero,
                "estimated_cycles": estimated_n,
            }
        )

    runs: list[dict[str, Any]] = []
    operators: list[dict[str, Any]] = []
    for operator in sorted(sequences):
        sequence = sorted(sequences[operator])
        operator_runs: list[dict[str, Any]] = []
        in_run = False
        for cycle, _observed, _index, is_zero in sequence:
            if not is_zero:
                in_run = False
            elif in_run:
                operator_runs[-1]["end_cycle"] = cycle
                operator_runs[-1]["cycles"] += 1
            else:
                in_run = True
                operator_runs.append(
                    {"operator": operator, "start_cycle": cycle, "end_cycle": cycle, "cycles": 1}
                )
        runs.extend(operator_runs)
        operators.append(
            {
                "operator": operator,
                "dataset_id": dataset_ids[operator],
                "cycles": len(sequence),
                "first_cycle": sequence[0][0],
                "last_cycle": sequence[-1][0],
                "zero_vehicle_cycles": sum(1 for item in sequence if item[3]),
                "zero_vehicle_runs": len(operator_runs),
                "longest_zero_vehicle_run": max((r["cycles"] for r in operator_runs), default=0),
            }
        )

    return {
        "schema": SCHEMA,
        "as_of": as_of,
        "since": since,
        "skipped_rows": skipped,
        "operators": operators,
        "buckets": bucket_rows,
        "zero_vehicle_runs": runs,
    }


def render_json(report: dict[str, Any]) -> str:
    return json.dumps(report, sort_keys=True, indent=2, ensure_ascii=True) + "\n"


def _cell(value: Any) -> str:
    return "-" if value is None else str(value)


def render_table(report: dict[str, Any]) -> str:
    header = ("operator", "date", "hour", "cycles", "min", "median", "max", "zero", "estimated")
    rows = [
        (
            b["operator"], b["date"], f"{b['hour']:02d}", str(b["cycles"]),
            _cell(b["vehicles_min"]), _cell(b["vehicles_median"]), _cell(b["vehicles_max"]),
            str(b["zero_vehicle_cycles"]), str(b["estimated_cycles"]),
        )
        for b in report["buckets"]
    ]
    widths = [max([len(h)] + [len(r[i]) for r in rows]) for i, h in enumerate(header)]
    out = ["  ".join(h.ljust(w) for h, w in zip(header, widths)).rstrip()]
    out.extend("  ".join(c.ljust(w) for c, w in zip(r, widths)).rstrip() for r in rows)
    out.append("")
    out.append("zero-vehicle runs:")
    if report["zero_vehicle_runs"]:
        for run in report["zero_vehicle_runs"]:
            out.append(
                f"  {run['operator']}  {run['start_cycle']} -> {run['end_cycle']}  cycles={run['cycles']}"
            )
    else:
        out.append("  none")
    out.append("")
    out.append(
        f"summary: schema={report['schema']} as_of={_cell(report['as_of'])} "
        f"since={_cell(report['since'])} operators={len(report['operators'])} "
        f"buckets={len(report['buckets'])} zero_vehicle_runs={len(report['zero_vehicle_runs'])} "
        f"skipped_rows={report['skipped_rows']}"
    )
    return "\n".join(out) + "\n"


def _since(value: str) -> str:
    if DATE_RE.fullmatch(value) is None:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got {value!r}")
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid date {value!r}: {exc}") from exc
    return value


def main(argv: list[str] | None = None, stdout: TextIO | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY,
                        help=f"history JSONL path (default: {DEFAULT_HISTORY})")
    parser.add_argument("--since", type=_since, default=None,
                        help="only include rows whose cycle date is on or after YYYY-MM-DD")
    parser.add_argument("--table", action="store_true", help="print a human table instead of JSON")
    args = parser.parse_args(argv)

    with args.history.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        report = build_report(handle, since=args.since)
    text = render_table(report) if args.table else render_json(report)
    (stdout or sys.stdout).write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
