#!/usr/bin/env python3
"""Report source-authority binding coverage across ``datapulse.json`` datasets.

A consumer that wants to bind a dataset row back to its authoritative source
needs more than the upstream URL: it needs the publishing identity (steward,
custodian, attribution, licence), a canonical dataset identifier, and a declared
expectation about the payload (expected record count, series/schema identity,
freshness interpretation, and the rule that disqualifies non-authoritative
mirrors).

This is a read-only operator smoke test. It measures how many datasets carry
each binding field and prints ``present/total`` with a percentage. Partial
coverage is the finding, not a failure: the check exits non-zero only when it
cannot measure at all (missing file, invalid JSON, or no ``datasets`` array).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_MANIFEST = Path(__file__).resolve().parents[1] / "datapulse.json"

# The mirror-disqualification rule has no schema property yet, so accept the
# plausible spellings (nested or top-level) and let the report show 0 coverage
# until a deliberate schema change introduces the canonical field.
MIRROR_DISQUALIFICATION_KEYS: tuple[str, ...] = (
    "mirror_disqualification_rule",
    "mirror_disqualification",
    "disqualifies_mirrors",
)

INTERPRETATION_LABEL = "freshness_policy.interpretation"
MIRROR_LABEL = "mirror_disqualification_rule"


@dataclass(frozen=True)
class FieldCoverage:
    """How many datasets carry one binding field."""

    field: str
    present: int
    total: int

    @property
    def percentage(self) -> float:
        """Coverage as a percentage, or 0.0 for an empty dataset set."""
        return 100.0 * self.present / self.total if self.total else 0.0

    def render(self) -> str:
        """Return the one-line ``present/total (pct%)`` rendering."""
        return f"{self.field}: {self.present}/{self.total} ({self.percentage:.1f}%)"


@dataclass(frozen=True)
class BindingReport:
    """Measured binding coverage for the whole manifest."""

    total: int
    fields: tuple[FieldCoverage, ...]
    interpretation_counts: tuple[tuple[str, int], ...]

    def field(self, name: str) -> FieldCoverage:
        """Return the coverage entry for ``name`` (raises ``KeyError`` if absent)."""
        for entry in self.fields:
            if entry.field == name:
                return entry
        raise KeyError(name)


def _is_present(value: Any) -> bool:
    """Treat blank strings and empty containers as absent, ``False``/``0`` as present."""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (Mapping, list, tuple, set)):
        return len(value) > 0
    return True


def _freshness_interpretation(row: Mapping[str, Any]) -> str | None:
    """Return the declared freshness interpretation, or ``None`` when missing."""
    policy = row.get("freshness_policy")
    if not isinstance(policy, Mapping):
        return None
    interpretation = policy.get("interpretation")
    if isinstance(interpretation, str) and interpretation.strip():
        return interpretation
    return None


def _nested_value(row: Mapping[str, Any], keys: Sequence[str]) -> Any:
    """Look for the first present key among ``keys`` anywhere inside ``row``."""
    queue: list[Mapping[str, Any]] = [row]
    while queue:
        current = queue.pop(0)
        for key in keys:
            if key in current:
                return current[key]
        for value in current.values():
            if isinstance(value, Mapping):
                queue.append(value)
    return None


def _mirror_rule(row: Mapping[str, Any]) -> Any:
    return _nested_value(row, MIRROR_DISQUALIFICATION_KEYS)


BINDING_FIELDS: tuple[tuple[str, Callable[[Mapping[str, Any]], Any]], ...] = (
    ("url", lambda row: row.get("url")),
    ("steward", lambda row: row.get("steward")),
    ("custodian", lambda row: row.get("custodian")),
    ("attribution", lambda row: row.get("attribution")),
    ("licence", lambda row: row.get("licence")),
    ("canonical_id", lambda row: row.get("canonical_id")),
    ("expected_record_count", lambda row: row.get("expected_record_count")),
    ("series_code", lambda row: row.get("series_code")),
    ("schema_id", lambda row: row.get("schema_id")),
    (INTERPRETATION_LABEL, _freshness_interpretation),
    (MIRROR_LABEL, _mirror_rule),
)


def load_datasets(manifest_path: Path) -> list[dict[str, Any]]:
    """Read and structurally validate ``manifest_path`` read-only.

    Raises ``OSError`` for an unreadable file, ``json.JSONDecodeError`` for
    invalid JSON, and ``ValueError`` when the ``datasets`` array is absent,
    empty, or contains a non-object row.
    """
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("manifest root is not a JSON object")
    datasets = payload.get("datasets")
    if not isinstance(datasets, list) or not datasets:
        raise ValueError("manifest has no non-empty datasets array")

    rows: list[dict[str, Any]] = []
    for index, row in enumerate(datasets):
        if not isinstance(row, Mapping):
            raise ValueError(f"datasets[{index}] is not a JSON object")
        rows.append(dict(row))
    return rows


def _interpretation_counts(datasets: Sequence[Mapping[str, Any]]) -> tuple[tuple[str, int], ...]:
    counter: Counter[str] = Counter()
    for row in datasets:
        counter[_freshness_interpretation(row) or "missing"] += 1
    # Declared values first (alphabetical), the not-declared bucket last.
    declared = sorted(
        (value, count) for value, count in counter.items() if value != "missing"
    )
    missing = counter.get("missing")
    if missing is not None:
        declared.append(("missing", missing))
    return tuple(declared)


def measure_binding(datasets: Sequence[Mapping[str, Any]]) -> BindingReport:
    """Measure per-field coverage over already-loaded ``datasets``."""
    total = len(datasets)
    if total == 0:
        raise ValueError("cannot measure binding coverage over zero datasets")
    fields = tuple(
        FieldCoverage(
            field=label,
            present=sum(1 for row in datasets if _is_present(getter(row))),
            total=total,
        )
        for label, getter in BINDING_FIELDS
    )
    return BindingReport(
        total=total,
        fields=fields,
        interpretation_counts=_interpretation_counts(datasets),
    )


def render_report(report: BindingReport) -> list[str]:
    """Render ``report`` as deterministic stdout lines."""
    lines = ["Source authority binding coverage:"]
    for entry in report.fields:
        lines.append(entry.render())
        if entry.field == INTERPRETATION_LABEL:
            for value, count in report.interpretation_counts:
                lines.append(f"  {value}: {count}")
    lines.append(f"Datasets measured: {report.total}")
    return lines


def main(argv: Sequence[str] | None = None) -> int:
    """Print binding coverage; exit 0 on a measurement, 2 when it cannot measure."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="path to datapulse.json (defaults to the repository manifest)",
    )
    args = parser.parse_args(argv)
    try:
        datasets = load_datasets(args.manifest)
        report = measure_binding(datasets)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
        print(f"source authority binding check error: {error}", file=sys.stderr)
        return 2
    for line in render_report(report):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
