#!/usr/bin/env python3
"""Derive ``expected_record_count`` from recorded shape facts, and audit the authored ones.

The manifest carries a hand-authored ``expected_record_count`` per dataset and
the served classifier in ``scripts/check.sh`` turns it into two tests: a row is
``incomplete`` when it holds fewer rows than expected, and ``degraded`` when it
holds fewer than half. That guard only means something when the expectation sits
close to what the payload actually holds; an authored number far above or below
the observed count either never fires on real loss or fires on legitimate
growth.

This script reads the shape facts the probe now records on each health row
(``newest_date``, ``oldest_date``, ``distinct_dates``, ``rows_per_date``,
``largest_gap_days``, ``dimension_cardinality``) plus the observed
``record_count``, and classifies every dataset by what its evidence shows:

* ``unknown``  - no usable date or count evidence; proposes nothing.
* ``closed``   - the newest date is more than 180 days before ``--as-of``, so
  the series no longer moves and its size is an invariant.
* ``windowed`` - rows-per-date oscillates by 3x or more, so a low count is not
  a loss; a window minimum is only proposed when ``--history`` is supplied.
* ``open``     - everything else; proposes 90% of the observed count.

It separately audits every authored ``expected_record_count`` against the
observed count and reports the fraction of rows that would have to vanish
before the classifier's floor can trip.

Hard rules:

* **Offline and read-only.** The script reads the local files the operator
  names. It never touches the network and never writes anything except the
  ``--report`` path.
* **Absent is not zero.** A missing fact yields a null proposal and an explicit
  reason code; nothing defaults a missing count to 0 or a missing date to today.
* **Malformed input never raises.** A null row, a string where a number belongs,
  an unparseable date, an empty health file, or a dataset absent from either
  input is skipped into a stated reason and the report is still emitted.
* **Deterministic.** ``--as-of`` defaults to today and is the only clock the
  script reads, so two runs on the same inputs with the same ``--as-of`` produce
  byte-identical output.

Exit status is 1 when the audit flags anything and 0 when it does not. When an
explicit ``--report`` path is given the report is always written and the process
exits 0, because the invocation is a report request rather than a gate; run the
script without ``--report`` to get the gating exit status.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger("derive_expectations")

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "datapulse.json"
DEFAULT_HEALTH = ROOT / "health" / "latest.json"

# The six facts the probe records. Order is stable for deterministic output.
FACT_FIELDS = (
    "newest_date",
    "oldest_date",
    "distinct_dates",
    "rows_per_date",
    "largest_gap_days",
    "dimension_cardinality",
)

CLASSIFICATIONS = ("unknown", "closed", "windowed", "open")

# A series that has not moved for this long is treated as closed: its size is an
# invariant, not a live count that can oscillate.
CLOSED_AFTER_DAYS = 180
# rows_per_date.max >= 3 * min marks a series whose count legitimately swings.
WINDOW_RATIO = 3
# Open series keep a 10% cushion so routine revision cannot trip `incomplete`.
OPEN_RETENTION = 0.9
# The served classifier's floor is expected * 0.5.
GUARD_FLOOR_RATIO = 0.5
# At this required loss the guard can no longer fire at a plausible loss.
GUARD_UNREACHABLE_RATIO = 0.90

BAND_ORDER = ("<=50%", "50-60%", "60-80%", "80-90%", ">90%")

REPORT_SCHEMA = "datapulse/v1/expectation-derivation"


def is_number(value: object) -> bool:
    """True for real JSON numbers. ``bool`` is not a count in this vocabulary."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def parse_iso_date(value: object) -> date | None:
    """Parse a ``YYYY-MM-DD`` date, or the date part of an ISO timestamp.

    Only an unambiguous ISO form is accepted; ``01/08/2026`` and a bare
    ``2026-09`` return ``None`` rather than a plausible-looking wrong date.
    """
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    for separator in ("T", " "):
        if separator in text:
            text = text.split(separator, 1)[0]
            break
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _is_absent(value: object) -> bool:
    """True when a fact carries no evidence at all."""
    if value is None:
        return True
    return isinstance(value, str) and value.strip() == ""


def _no_newest_reason(row: dict[str, Any]) -> str:
    """Distinguish a pre-change row from a payload that has no date column.

    ``no_facts`` means every one of the six fields is null or absent, which is
    what a row probed before the shape-facts change looks like. ``no_date_column``
    means the row carries some fact evidence but no usable newest date, so the
    probe ran and simply found no date dimension. Collapsing the two would read
    an absent fact as "no date column" and hide that nothing was ever recorded.
    """
    if all(row.get(field) is None for field in FACT_FIELDS):
        return "no_facts"
    return "no_date_column"


def _is_windowed(rows_per_date: object) -> bool:
    """True when the per-date row count varies by at least a factor of three."""
    if not isinstance(rows_per_date, dict):
        return False
    minimum = rows_per_date.get("min")
    maximum = rows_per_date.get("max")
    if not (is_number(minimum) and is_number(maximum)):
        return False
    return maximum >= WINDOW_RATIO * minimum


def _as_count(value: object) -> object:
    """Normalise an integral float to int so the JSON stays stable."""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def classify_dataset(
    dataset_id: str,
    row: dict[str, Any],
    *,
    as_of: date,
    history_counts: dict[str, list[float]],
) -> dict[str, Any]:
    """Classify one dataset and propose an expectation from its evidence alone.

    The order of the tests is the contract: no evidence is ``unknown`` before
    any date reasoning; a quiet series is ``closed`` before its count shape is
    inspected; only a moving series can be ``windowed`` or ``open``.
    """
    observed = row.get("record_count")
    entry: dict[str, Any] = {
        "dataset_id": dataset_id,
        "classification": "unknown",
        "reason": None,
        "observed_record_count": _as_count(observed) if is_number(observed) else None,
        "proposed_expected_record_count": None,
        "history_observations": None,
        "facts": {field: row.get(field) for field in FACT_FIELDS},
    }

    if not is_number(observed):
        if _is_absent(row.get("newest_date")):
            entry["reason"] = _no_newest_reason(row)
        elif observed is None or (isinstance(observed, str) and not observed.strip()):
            entry["reason"] = "observed_record_count_missing"
        else:
            entry["reason"] = "observed_record_count_not_numeric"
        return entry

    if _is_absent(row.get("newest_date")):
        entry["reason"] = _no_newest_reason(row)
        return entry

    newest = parse_iso_date(row.get("newest_date"))
    if newest is None:
        entry["reason"] = "unparseable_newest_date"
        return entry

    if (as_of - newest).days > CLOSED_AFTER_DAYS:
        entry["classification"] = "closed"
        entry["reason"] = "closed_series"
        entry["proposed_expected_record_count"] = _as_count(observed)
        return entry

    if _is_windowed(row.get("rows_per_date")):
        entry["classification"] = "windowed"
        counts = history_counts.get(dataset_id)
        if counts:
            entry["reason"] = "windowed_history"
            entry["proposed_expected_record_count"] = _as_count(min(counts))
            entry["history_observations"] = len(counts)
        else:
            entry["reason"] = "windowed_needs_history"
        return entry

    entry["classification"] = "open"
    entry["reason"] = "open"
    entry["proposed_expected_record_count"] = max(
        1, math.floor(observed * OPEN_RETENTION)
    )
    return entry


def _band_for(required_loss: float | None) -> str:
    if required_loss is None:
        return "undefined"
    if required_loss <= 0.5:
        return "<=50%"
    if required_loss <= 0.6:
        return "50-60%"
    if required_loss <= 0.8:
        return "60-80%"
    if required_loss <= 0.9:
        return "80-90%"
    return ">90%"


def _read_json(path: Path) -> tuple[Any, str | None]:
    """Read a JSON document, returning ``(payload, error_reason)``."""
    try:
        text = path.read_text(encoding="utf-8")
    except (FileNotFoundError, IsADirectoryError, OSError, UnicodeDecodeError):
        return None, "unreadable"
    if not text.strip():
        return None, "empty"
    try:
        return json.loads(text), None
    except json.JSONDecodeError:
        return None, "invalid_json"


def _index_datasets(
    payload: object, id_key: str
) -> tuple[dict[str, dict[str, Any]], int, str | None]:
    """Index ``datasets`` rows by id, tolerating a bare top-level list."""
    if isinstance(payload, dict):
        items = payload.get("datasets")
    elif isinstance(payload, list):
        items = payload
    else:
        items = None
    if not isinstance(items, list):
        return {}, 0, "missing_datasets"
    index: dict[str, dict[str, Any]] = {}
    malformed = 0
    for item in items:
        if not isinstance(item, dict):
            malformed += 1
            continue
        dataset_id = item.get(id_key)
        if not isinstance(dataset_id, str) or not dataset_id:
            malformed += 1
            continue
        index[dataset_id] = item
    return index, malformed, None


def _load_history(
    path: Path | None,
) -> tuple[dict[str, list[float]], int, int, str | None]:
    """Read a JSONL of prior observations into per-dataset count lists.

    Each line may be a bare observation row (``dataset_id`` + ``record_count``)
    or a snapshot object carrying a ``datasets`` list. Unparseable lines are
    counted and skipped, never raised.
    """
    if path is None:
        return {}, 0, 0, None
    try:
        text = path.read_text(encoding="utf-8")
    except (FileNotFoundError, IsADirectoryError, OSError, UnicodeDecodeError):
        return {}, 0, 0, "unreadable"

    counts: dict[str, list[float]] = defaultdict(list)
    observations = 0
    parse_errors = 0
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            document = json.loads(stripped)
        except json.JSONDecodeError:
            parse_errors += 1
            continue
        if isinstance(document, dict) and isinstance(document.get("datasets"), list):
            rows = document["datasets"]
        elif isinstance(document, list):
            rows = document
        elif isinstance(document, dict):
            rows = [document]
        else:
            parse_errors += 1
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            dataset_id = row.get("dataset_id")
            record_count = row.get("record_count")
            if isinstance(dataset_id, str) and is_number(record_count):
                counts[dataset_id].append(record_count)
                observations += 1
    return dict(counts), observations, parse_errors, None


def build_derivation(
    manifest_index: dict[str, dict[str, Any]],
    health_index: dict[str, dict[str, Any]],
    *,
    as_of: date,
    history_counts: dict[str, list[float]],
) -> dict[str, Any]:
    """Classify the union of datasets, skipping any absent from either input."""
    dataset_ids = sorted(set(manifest_index) | set(health_index))
    entries: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []

    for dataset_id in dataset_ids:
        if dataset_id not in manifest_index:
            skipped.append({"dataset_id": dataset_id, "reason": "absent_from_manifest"})
            continue
        if dataset_id not in health_index:
            skipped.append({"dataset_id": dataset_id, "reason": "absent_from_health"})
            continue
        entries.append(
            classify_dataset(
                dataset_id,
                health_index[dataset_id],
                as_of=as_of,
                history_counts=history_counts,
            )
        )

    counts = Counter(entry["classification"] for entry in entries)
    reasons = Counter(str(entry["reason"]) for entry in entries)
    return {
        "counts": {name: counts.get(name, 0) for name in CLASSIFICATIONS},
        "reasons": {reason: reasons[reason] for reason in sorted(reasons)},
        "classified": len(entries),
        "skipped": skipped,
        "datasets": entries,
    }


def build_audit(
    manifest_index: dict[str, dict[str, Any]],
    health_index: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Measure how hard the truncation guard is to trip for every authored value."""
    bands: dict[str, int] = {band: 0 for band in BAND_ORDER}
    guard_unreachable: list[str] = []
    expectation_above_observed: list[str] = []
    entries: list[dict[str, Any]] = []

    for dataset_id in sorted(manifest_index):
        entry = manifest_index[dataset_id]
        row = health_index.get(dataset_id)
        if row is None:
            continue
        expected = entry.get("expected_record_count")
        observed = row.get("record_count")
        if not (is_number(expected) and is_number(observed)):
            continue

        if observed > 0:
            required_loss: float | None = 1 - (expected * GUARD_FLOOR_RATIO) / observed
        elif expected > 0:
            # observed == 0 with a positive expectation: every row is gone.
            required_loss = 1.0
        else:
            required_loss = None

        flags: list[str] = []
        if required_loss is not None and required_loss >= GUARD_UNREACHABLE_RATIO:
            flags.append("guard_unreachable")
            guard_unreachable.append(dataset_id)
        if expected > observed:
            flags.append("expectation_above_observed")
            expectation_above_observed.append(dataset_id)

        band = _band_for(required_loss)
        bands[band] = bands.get(band, 0) + 1

        record: dict[str, Any] = {
            "dataset_id": dataset_id,
            "expected_record_count": _as_count(expected),
            "observed_record_count": _as_count(observed),
            "required_loss": (
                round(required_loss, 6) if required_loss is not None else None
            ),
            "required_loss_pct": (
                round(required_loss * 100, 1) if required_loss is not None else None
            ),
            "band": band,
            "flags": flags,
        }
        entries.append(record)

    if bands.get("undefined") == 0:
        bands.pop("undefined", None)

    return {
        "audited": len(entries),
        # "flagged" is the guard-unreachable count: the datasets whose guard can
        # no longer fire at a plausible loss. `expectation_above_observed` is
        # reported separately because it is a different failure (the authored
        # number already exceeds the source), not a dead guard.
        "flagged": len(guard_unreachable),
        "guard_unreachable": guard_unreachable,
        "expectation_above_observed": expectation_above_observed,
        "bands": bands,
        "datasets": entries,
    }


def build_report(
    *,
    manifest_path: Path,
    health_path: Path,
    history_path: Path | None,
    as_of: date,
    manifest_index: dict[str, dict[str, Any]],
    health_index: dict[str, dict[str, Any]],
    manifest_malformed: int,
    health_malformed: int,
    history_counts: dict[str, list[float]],
    history_observations: int,
    history_parse_errors: int,
    input_errors: list[dict[str, str]],
) -> dict[str, Any]:
    """Assemble the deterministic report the operator inspects."""
    derivation = build_derivation(
        manifest_index, health_index, as_of=as_of, history_counts=history_counts
    )
    derivation["malformed_manifest_entries"] = manifest_malformed
    derivation["malformed_health_rows"] = health_malformed
    for _ in range(manifest_malformed):
        derivation["skipped"].append(
            {"dataset_id": None, "reason": "malformed_manifest_entry"}
        )
    for _ in range(health_malformed):
        derivation["skipped"].append(
            {"dataset_id": None, "reason": "malformed_health_row"}
        )
    audit = build_audit(manifest_index, health_index)
    return {
        "schema": REPORT_SCHEMA,
        "as_of": as_of.isoformat(),
        "inputs": {
            "manifest": str(manifest_path),
            "health": str(health_path),
            "history": str(history_path) if history_path is not None else None,
        },
        "input_errors": input_errors,
        "history": {
            "observations": history_observations,
            "parse_errors": history_parse_errors,
        },
        "derivation": derivation,
        "audit": audit,
    }


def _write_report(path: Path, report: dict[str, Any]) -> None:
    """Write exactly the named path; no temp file, no other artifact."""
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _parse_as_of(raw: str) -> date:
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"--as-of must be YYYY-MM-DD, got {raw!r}"
        ) from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Derive expected_record_count from recorded shape facts and audit "
            "the authored manifest values. Never rewrites the manifest."
        )
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--health", type=Path, default=DEFAULT_HEALTH)
    parser.add_argument(
        "--history",
        type=Path,
        default=None,
        help="JSONL of prior observation rows used to window a min count.",
    )
    parser.add_argument(
        "--as-of",
        type=_parse_as_of,
        default=None,
        help="Reference date (YYYY-MM-DD). Defaults to today and is the only clock read.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Write the report JSON here. The process then exits 0.",
    )
    parser.add_argument(
        "--quiet", action="store_true", help="Suppress the stderr summary."
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    as_of = args.as_of if args.as_of is not None else date.today()

    input_errors: list[dict[str, str]] = []

    manifest_payload, manifest_error = _read_json(args.manifest)
    if manifest_error is not None:
        input_errors.append({"source": "manifest", "reason": manifest_error})
    manifest_index, manifest_malformed, index_error = _index_datasets(
        manifest_payload, "id"
    )
    if index_error is not None and manifest_error is None:
        input_errors.append({"source": "manifest", "reason": index_error})

    health_payload, health_error = _read_json(args.health)
    if health_error is not None:
        input_errors.append({"source": "health", "reason": health_error})
    health_index, health_malformed, health_index_error = _index_datasets(
        health_payload, "dataset_id"
    )
    if health_index_error is not None and health_error is None:
        input_errors.append({"source": "health", "reason": health_index_error})

    (
        history_counts,
        history_observations,
        history_parse_errors,
        history_error,
    ) = _load_history(args.history)
    if history_error is not None:
        input_errors.append({"source": "history", "reason": history_error})

    report = build_report(
        manifest_path=args.manifest,
        health_path=args.health,
        history_path=args.history,
        as_of=as_of,
        manifest_index=manifest_index,
        health_index=health_index,
        manifest_malformed=manifest_malformed,
        health_malformed=health_malformed,
        history_counts=history_counts,
        history_observations=history_observations,
        history_parse_errors=history_parse_errors,
        input_errors=input_errors,
    )

    findings = bool(report["audit"]["guard_unreachable"]) or bool(
        report["audit"]["expectation_above_observed"]
    )

    if args.report is not None:
        try:
            _write_report(args.report, report)
        except OSError as exc:
            LOGGER.error("could not write report to %s: %s", args.report, exc)
            return 2

    if not args.quiet:
        LOGGER.info(
            "derivation %s (classified=%d skipped=%d); audit audited=%d flagged=%d above_observed=%d",
            report["derivation"]["counts"],
            report["derivation"]["classified"],
            len(report["derivation"]["skipped"]),
            report["audit"]["audited"],
            report["audit"]["flagged"],
            len(report["audit"]["expectation_above_observed"]),
        )
        if findings:
            LOGGER.warning(
                "findings: guard_unreachable=%s expectation_above_observed=%s",
                report["audit"]["guard_unreachable"],
                report["audit"]["expectation_above_observed"],
            )

    if args.report is None:
        # Gate mode: no report path means the exit status is the output signal.
        return 1 if findings else 0
    # Report mode: the report carries the findings; the request itself succeeded.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
