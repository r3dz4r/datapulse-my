#!/usr/bin/env python3
"""Deterministic normalization profiles for historical observation capture.

Why this module exists
----------------------
The observation envelope records that a payload was *captured*; the historical
schema records that a normalized projection was *retained*.  A future reader
can only reconstruct the original from the projection if the exact
transformation is pinned: a normalization that silently re-shapes the source
destroys the audit chain.  Every result therefore carries the profile name and
version, profiles are pinned to ``NORMALIZATION_PROFILE_VERSION`` (the same
wire format the envelope asserts as ``normalization_profile_version``), and
``projection_digest`` is the SHA-256 over
``observation_store.canonical_json(projection)`` — the same computation
``observation_store.put_normalized`` performs — so an in-memory result and the
filed artifact are byte-for-byte comparable.

Normalization never mutates captured bytes.  Raw payloads are written only by
``observation_capture`` through ``observation_store``; this module writes only
derived projections, and only through ``observation_store.put_normalized``.

Determinism contract: the same ``(payload, profile name, profile version)``
always produces a byte-identical ``NormalizationResult``.

``fuelprice_csv_v1`` rules (pinned; changing any of them is a new version)
---------------------------------------------------------------------------
* Header: header cells are whitespace-trimmed; columns whose trimmed header is
  empty are dropped and reported in ``dropped_fields`` as ``not_extractable``
  under the positional name ``column_<original header index>``; surviving
  columns keep their order.  Duplicate non-empty trimmed header names fail
  closed with a parse error rather than silently re-shaping the row map.
* Rows: entirely blank rows are skipped.  Rows are stable-sorted by the first
  retained column, then by original row order.  A cell missing from a short
  row becomes ``null`` and is reported as ``not_delivered``; a non-empty cell
  beyond the header is reported as ``not_extractable``.
* Nulls: an empty (or whitespace-only) cell becomes ``null``.  Nothing else is
  ever treated as null, and no value is ever coerced.
* Numeric columns: a column whose non-null cells are strictly more than half
  parseable as integers or finite floats is numeric.  Integers stay integers.
  A non-numeric cell in a numeric column becomes ``null`` and is reported in
  ``dropped_fields`` with basis ``does_not_apply``.
* Dedup: exact-duplicate rows (identical after normalization) are dropped
  after sorting; ``deduped_rows`` counts them.
* Identity: each retained row gets ``record_id = "sha256:" + hex(sha256(
  canonical_json(row)))`` inside a ``record_ids`` list — never a column.
* Output projection (exactly these members):
  ``{"format", "record_count", "columns", "dropped_fields", "deduped_rows",
  "record_ids"}``.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import logging
import math
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Sequence

try:
    # Absolute form when the repo root is on sys.path (pipeline, pytest rootdir).
    from scripts.observation_store import canonical_json, put_normalized, read_normalized
except ModuleNotFoundError:  # bare form when scripts/ itself is on sys.path
    from observation_store import canonical_json, put_normalized, read_normalized

__all__ = [
    "NORMALIZATION_PROFILE_VERSION",
    "NormalizationParseError",
    "NormalizationProfile",
    "NormalizationProfileError",
    "NormalizationResult",
    "file_normalized",
    "get_profile",
    "main",
    "normalize",
    "register_profile",
]

logger = logging.getLogger(__name__)

NORMALIZATION_PROFILE_VERSION = "datapulse-normalization-profile/v1"

#: Closed vocabulary for ``dropped_fields[*].basis``.  Never extended at runtime.
BASIS_VOCABULARY: Final[frozenset[str]] = frozenset(
    {"does_not_apply", "not_extractable", "not_delivered"}
)

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

RECORD_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^sha256:[0-9a-f]{64}$")

_INT_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[+-]?\d+$")
_FLOAT_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^[+-]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?$"
)


class NormalizationProfileError(Exception):
    """A profile is unknown, ambiguous, or violated its contract."""


class NormalizationParseError(NormalizationProfileError):
    """A payload cannot be parsed under a profile.  Names the line/offset."""


@dataclass(frozen=True)
class NormalizationResult:
    """The deterministic outcome of applying one pinned profile to one payload.

    ``projection_digest`` is ``"sha256:<64hex>"`` over
    ``observation_store.canonical_json(projection)`` and must equal the digest
    returned when the projection is filed via ``file_normalized``.
    """

    profile_name: str
    profile_version: str
    format: str
    projection: dict
    projection_digest: str
    record_count: int
    record_ids: list[str]
    dropped_fields: list[dict]


@dataclass(frozen=True)
class NormalizationProfile:
    """A pinned, named normalization policy.

    ``apply`` dispatches on ``format``; every policy field is descriptive
    metadata that the pinned ``(name, version)`` pair makes auditable.
    """

    name: str
    version: str
    format: str
    input_content_type: str
    row_ordering: str
    null_handling: str
    numeric_handling: str
    dedup: bool
    description: str

    def apply(self, payload: bytes) -> NormalizationResult:
        """Apply this profile to ``payload`` and return the pinned result."""
        if self.format == "csv":
            return _normalize_csv(self, payload)
        raise NormalizationProfileError(
            f"profile {self.name}/{self.version} declares unsupported format "
            f"{self.format!r}; no normalization was attempted"
        )


_PROFILES: dict[tuple[str, str], NormalizationProfile] = {}


def register_profile(profile: NormalizationProfile) -> None:
    """Register ``profile`` in the module-level registry.

    Idempotent on ``(name, version)``: re-registering an equal profile is a
    no-op; registering a *different* profile under an existing pair raises
    ``NormalizationProfileError`` (a silent redefinition would change the
    meaning of every projection already filed under that pair).
    """
    if not isinstance(profile, NormalizationProfile):
        raise NormalizationProfileError(
            f"register_profile expects a NormalizationProfile, got {type(profile).__name__}"
        )
    key = (profile.name, profile.version)
    existing = _PROFILES.get(key)
    if existing is not None and existing != profile:
        raise NormalizationProfileError(
            f"profile ({profile.name!r}, {profile.version!r}) is already registered "
            "with a different definition; version-pinned profiles never change"
        )
    _PROFILES[key] = profile
    logger.debug("registered normalization profile %s/%s", profile.name, profile.version)


def _registered_designations() -> list[str]:
    return sorted(f"{name}/{version}" for name, version in _PROFILES)


def get_profile(name: str, *, version: str | None = None) -> NormalizationProfile:
    """Exact-match lookup of a registered profile.

    ``name`` may be the base name (``"fuelprice_csv"``) or the full
    designation (``"fuelprice_csv_v1"``).  An explicit ``version`` requires
    the exact ``(name, version)`` pair.  Missing or ambiguous lookups raise
    ``NormalizationProfileError`` — fail closed, never guess.
    """
    if version is not None:
        profile = _PROFILES.get((name, version))
        if profile is None:
            raise NormalizationProfileError(
                f"no normalization profile registered as {name!r} version {version!r}; "
                f"registered: {_registered_designations()}"
            )
        return profile

    by_name = [p for (n, _v), p in _PROFILES.items() if n == name]
    if len(by_name) == 1:
        return by_name[0]
    if len(by_name) > 1:
        versions = sorted(v for n, v in _PROFILES if n == name)
        raise NormalizationProfileError(
            f"profile name {name!r} is ambiguous across versions {versions}; "
            "pass an explicit version — a projection must pin one"
        )

    by_designation = [p for (n, v), p in _PROFILES.items() if f"{n}_{v}" == name]
    if len(by_designation) == 1:
        return by_designation[0]
    if len(by_designation) > 1:
        raise NormalizationProfileError(
            f"profile designation {name!r} matches multiple registered profiles; "
            "pass --version explicitly to pin one"
        )
    raise NormalizationProfileError(
        f"no normalization profile registered for {name!r}; "
        f"registered: {_registered_designations()}"
    )


def normalize(
    payload: bytes, profile_name: str, *, profile_version: str | None = None
) -> NormalizationResult:
    """Producer's single entry point: payload bytes in, pinned result out.

    Unknown profiles and unparseable payloads fail closed with typed
    exceptions naming the registered designations or the offending
    line/offset.
    """
    if not isinstance(payload, (bytes, bytearray, memoryview)):
        raise NormalizationProfileError(
            f"payload must be bytes-like, got {type(payload).__name__}"
        )
    profile = get_profile(profile_name, version=profile_version)
    return profile.apply(bytes(payload))


def file_normalized(result: NormalizationResult, *, root: str | Path | None = None) -> str:
    """File ``result.projection`` through ``observation_store.put_normalized``.

    Returns the store's digest.  Raises ``NormalizationProfileError`` if the
    store's digest differs from ``result.projection_digest`` — a mismatch
    means the projection changed between normalization and filing, breaking
    the audit chain between memory and disk.
    """
    if RECORD_ID_PATTERN.fullmatch(result.projection_digest) is None:
        raise NormalizationProfileError(
            f"projection_digest {result.projection_digest!r} is malformed; expected "
            "'sha256:' followed by exactly 64 lowercase hexadecimal characters"
        )
    store_digest = put_normalized(
        result.projection, root=Path(root) if root is not None else None
    )
    if store_digest != result.projection_digest:
        raise NormalizationProfileError(
            f"store digest {store_digest} does not match the result's projection_digest "
            f"{result.projection_digest}; the projection changed between normalization "
            "and filing — nothing may be claimed from this result"
        )
    return store_digest


# ---------------------------------------------------------------------------
# CSV normalization (shared engine for csv-format profiles)
# ---------------------------------------------------------------------------


class _DroppedFields:
    """Ordered unique ``{name, basis}`` entries over a closed basis vocabulary."""

    def __init__(self) -> None:
        self.entries: list[dict[str, str]] = []
        self._seen: set[tuple[str, str]] = set()

    def add(self, name: str, basis: str) -> None:
        if basis not in BASIS_VOCABULARY:
            raise NormalizationProfileError(
                f"dropped-field basis {basis!r} is outside the closed vocabulary "
                f"{sorted(BASIS_VOCABULARY)}; a new basis is a schema change, not a "
                "producer decision"
            )
        key = (name, basis)
        if key not in self._seen:
            self._seen.add(key)
            self.entries.append({"name": name, "basis": basis})


def _parse_number(text: str) -> int | float | None:
    """Parse an integer or finite float; anything else is not a number.

    ``nan``/``inf`` spellings never match, and Python's int() acceptance of
    underscores is bypassed by matching a strict grammar first.
    """
    if _INT_PATTERN.fullmatch(text):
        return int(text)
    if _FLOAT_PATTERN.fullmatch(text):
        value = float(text)
        if math.isfinite(value):
            return value
    return None


def _normalize_csv(profile: NormalizationProfile, payload: bytes) -> NormalizationResult:
    """Apply the pinned CSV rules documented at module scope."""
    try:
        text = bytes(payload).decode("utf-8")
    except UnicodeDecodeError as error:
        raise NormalizationParseError(
            f"byte offset {error.start}: payload is not valid UTF-8 CSV"
        ) from error

    reader = csv.reader(io.StringIO(text, newline=""))
    rows: list[list[str]] = []
    try:
        for row in reader:
            rows.append(row)
    except csv.Error as error:
        raise NormalizationParseError(
            f"line {reader.line_num}: CSV parse failed: {error}"
        ) from error
    if not rows:
        raise NormalizationParseError("line 1: payload has no header row")

    dropped = _DroppedFields()
    columns: list[str] = []
    column_indices: list[int] = []
    seen_headers: set[str] = set()
    for index, raw_header in enumerate(rows[0]):
        name = raw_header.strip()
        if not name:
            dropped.add(f"column_{index}", "not_extractable")
            continue
        if name in seen_headers:
            raise NormalizationParseError(
                f"line 1: duplicate header {name!r} after trimming; a duplicated "
                "column name would silently re-shape the row map"
            )
        seen_headers.add(name)
        columns.append(name)
        column_indices.append(index)
    if not columns:
        raise NormalizationParseError(
            "line 1: no columns remain after trimming; every header cell is empty"
        )

    staged: list[list[str | None]] = []
    for row in rows[1:]:
        if not row or all(cell.strip() == "" for cell in row):
            continue
        cells: list[str | None] = []
        for position, header_index in enumerate(column_indices):
            if header_index >= len(row):
                cells.append(None)
                dropped.add(columns[position], "not_delivered")
            else:
                value = row[header_index].strip()
                cells.append(value if value else None)
        for extra_index in range(len(rows[0]), len(row)):
            if row[extra_index].strip():
                dropped.add(f"column_{extra_index}", "not_extractable")
        staged.append(cells)

    numeric_positions: set[int] = set()
    for position in range(len(columns)):
        values = [row[position] for row in staged if row[position] is not None]
        if not values:
            continue
        parseable = sum(1 for value in values if _parse_number(value) is not None)
        if parseable * 2 > len(values):
            numeric_positions.add(position)

    typed_rows: list[dict[str, Any]] = []
    for cells in staged:
        typed: dict[str, Any] = {}
        for position, column in enumerate(columns):
            value = cells[position]
            if value is None:
                typed[column] = None
            elif position in numeric_positions:
                number = _parse_number(value)
                if number is None:
                    dropped.add(column, "does_not_apply")
                    typed[column] = None
                else:
                    typed[column] = number
            else:
                typed[column] = value
        typed_rows.append(typed)

    first_column = columns[0]

    def _sort_key(item: tuple[dict[str, Any], int]) -> tuple[tuple[int, Any], int]:
        value = item[0].get(first_column)
        if value is None:
            rank: tuple[int, Any] = (0, 0)
        elif isinstance(value, str):
            rank = (2, value)
        else:
            rank = (1, value)
        return (rank, item[1])

    ordered = sorted(zip(typed_rows, range(len(typed_rows))), key=_sort_key)

    final_rows: list[dict[str, Any]] = []
    seen_rows: set[bytes] = set()
    deduped_rows = 0
    for typed, _order in ordered:
        row_bytes = canonical_json(typed)
        if profile.dedup and row_bytes in seen_rows:
            deduped_rows += 1
            continue
        seen_rows.add(row_bytes)
        final_rows.append(typed)

    record_ids = [
        "sha256:" + hashlib.sha256(canonical_json(row)).hexdigest() for row in final_rows
    ]
    projection: dict[str, Any] = {
        "format": "csv",
        "record_count": len(final_rows),
        "columns": columns,
        "dropped_fields": dropped.entries,
        "deduped_rows": deduped_rows,
        "record_ids": record_ids,
    }
    projection_digest = "sha256:" + hashlib.sha256(canonical_json(projection)).hexdigest()
    return NormalizationResult(
        profile_name=profile.name,
        profile_version=profile.version,
        format="csv",
        projection=projection,
        projection_digest=projection_digest,
        record_count=len(final_rows),
        record_ids=record_ids,
        dropped_fields=dropped.entries,
    )


# ---------------------------------------------------------------------------
# Built-in profiles (registered as data; part 2 adds the JSON profile)
# ---------------------------------------------------------------------------

_NUMERIC_HANDLING_CSV: Final[str] = (
    "column numeric when strictly more than half of its non-null cells parse as "
    "integers or finite floats; integers stay integers; non-numeric cells in "
    "numeric columns are dropped as does_not_apply and never coerced"
)

_FUELPRICE_CSV_V1: Final[NormalizationProfile] = NormalizationProfile(
    name="fuelprice_csv",
    version="v1",
    format="csv",
    input_content_type="text/csv",
    row_ordering="stable_sort_by_first_column_then_original_row_order",
    null_handling="empty_cell_becomes_null",
    numeric_handling=_NUMERIC_HANDLING_CSV,
    dedup=True,
    description=(
        "Weekly fuel-price CSV from storage.data.gov.my (dataset 'fuelprice', "
        "full_vintage retention per config/observation-policies.json): trimmed "
        "headers, empty-header columns dropped, empty cells nulled, majority-typed "
        "numeric columns with integers kept integral, exact duplicates removed "
        "after a stable sort by the first column."
    ),
)

register_profile(_FUELPRICE_CSV_V1)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _result_bytes(result: NormalizationResult) -> bytes:
    """Canonical serialization of a full result, for byte-identity checks."""
    return canonical_json(
        {
            "profile_name": result.profile_name,
            "profile_version": result.profile_version,
            "format": result.format,
            "projection": result.projection,
            "projection_digest": result.projection_digest,
            "record_count": result.record_count,
            "record_ids": result.record_ids,
            "dropped_fields": result.dropped_fields,
        }
    )


_SELFTEST_CSV: Final[bytes] = (
    "date,ron95,ron97,diesel,region,\n"
    "2025-01-01,2.05,3.36,2.98,kl,\n"
    "2025-01-08,2.05,3.36,2.98,kl,\n"
    "2025-01-15,2.05,3.38,2.98,kl,\n"
    "2025-01-22,2.05,3.38,2.98,jb,\n"
    "2025-02-01,2.05,3.38,2.98,jb,\n"
    "2025-02-08,2.05,n/a,2.98,jb,\n"
    "2025-02-15,2.07,3.42,3.04,kl,\n"
    "2025-02-22,2.07,3.42,3.04,kl,\n"
    "2025-03-01,2.07,3.42,3.04,penang,\n"
    "2025-03-08,2.07,3.47,3.04,penang,\n"
    "2025-01-08,2.05,3.36,2.98,kl,\n"
    "2025-03-15,2.07,3.47,3.04,kk,\n"
).encode("utf-8")


def _run_selftest() -> int:
    """Acceptance selftest for the CSV profile against a scratch store.

    Runs inside a scratch root under the worktree; the production store root
    is never touched.  Output is deterministic (no paths, no timestamps) so
    two runs are byte-identical.  Exits 0 only when every check holds.
    """
    failures: list[str] = []

    def check(label: str, holds: bool) -> None:
        print(f"{label}: {'ok' if holds else 'FAIL'}")
        if not holds:
            failures.append(label)

    scratch = Path(tempfile.mkdtemp(prefix=".observation-normalize-selftest-", dir=REPO_ROOT))
    try:
        first = normalize(_SELFTEST_CSV, "fuelprice_csv_v1")
        print(f"profile={first.profile_name}/{first.profile_version}")
        print(f"record_count={first.record_count}")
        check("record_count>0", first.record_count > 0)
        store_digest = file_normalized(first, root=scratch)
        print(f"projection_digest={first.projection_digest}")
        print(f"store_digest={store_digest}")
        check(
            "projection_digest matches the digest returned by file_normalized",
            first.projection_digest == store_digest,
        )
        check(
            "filed projection reads back as the same canonical bytes",
            read_normalized(store_digest, root=scratch) == canonical_json(first.projection),
        )

        second = normalize(_SELFTEST_CSV, "fuelprice_csv_v1")
        check(
            "two runs of the csv profile against the same payload are byte-identical",
            _result_bytes(first) == _result_bytes(second),
        )

        check(
            "register_profile is idempotent on (name, version)",
            (register_profile(get_profile("fuelprice_csv_v1")), True)[1],
        )

        v2 = NormalizationProfile(
            name="fuelprice_csv",
            version="v2",
            format="csv",
            input_content_type="text/csv",
            row_ordering="stable_sort_by_first_column_then_original_row_order",
            null_handling="empty_cell_becomes_null",
            numeric_handling=_NUMERIC_HANDLING_CSV,
            dedup=False,
            description="selftest-only variant of fuelprice_csv_v1 that keeps duplicate rows",
        )
        register_profile(v2)
        kept = normalize(_SELFTEST_CSV, "fuelprice_csv_v2")
        print(f"v2_projection_digest={kept.projection_digest}")
        print(f"v2_deduped_rows={kept.projection['deduped_rows']}")
        check("two versions of the same name produce different projections",
              kept.projection_digest != first.projection_digest)
        check("v2 keeps duplicates (deduped_rows == 0)", kept.projection["deduped_rows"] == 0)
        check("v2 retains one more record than the deduplicating v1",
              kept.record_count == first.record_count + 1)
        pinned_v1 = get_profile("fuelprice_csv", version="v1")
        pinned_v2 = get_profile("fuelprice_csv", version="v2")
        check(
            "two versions of the same name return different objects",
            pinned_v1 != pinned_v2 and pinned_v1 is not pinned_v2,
        )

        print(f"dropped_fields={canonical_json(first.dropped_fields).decode('utf-8')}")
        check("dropped_fields is non-empty", len(first.dropped_fields) > 0)
        check(
            "every dropped-field basis comes from the closed vocabulary",
            all(entry.get("basis") in BASIS_VOCABULARY for entry in first.dropped_fields),
        )
        check(
            "the non-numeric cell in a numeric column is dropped as does_not_apply",
            any(
                entry.get("basis") == "does_not_apply" and entry.get("name") == "ron97"
                for entry in first.dropped_fields
            ),
        )
        check(
            "the trailing empty header column is dropped as not_extractable",
            any(
                entry.get("basis") == "not_extractable" and entry.get("name") == "column_5"
                for entry in first.dropped_fields
            ),
        )
    except Exception as error:  # noqa: BLE001 — the selftest reports, never traces
        failures.append(f"selftest raised {type(error).__name__}: {error}")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    if failures:
        for failure in failures:
            print(f"FAIL {failure}", file=sys.stderr)
        return 1
    print("selftest passed: profile pinned, digests matched, results byte-identical")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """CLI: ``--selftest``, or ``--payload PATH --profile NAME [--version V] [--store ROOT]``."""
    parser = argparse.ArgumentParser(
        prog="observation_normalize.py",
        description="Deterministic normalization profiles for historical observation capture.",
    )
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="run the acceptance selftest against a scratch store inside the worktree",
    )
    parser.add_argument("--payload", type=Path, metavar="PATH", help="payload file to normalize")
    parser.add_argument(
        "--profile", metavar="DESIGNATION", help="profile designation, e.g. fuelprice_csv_v1"
    )
    parser.add_argument(
        "--version",
        dest="profile_version",
        metavar="V",
        help="explicit profile version; overrides any version implied by --profile",
    )
    parser.add_argument(
        "--store",
        type=Path,
        metavar="ROOT",
        help="absolute store root for filing the projection (default: the store's configured root)",
    )
    arguments = parser.parse_args(argv)

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    if arguments.selftest:
        return _run_selftest()
    if arguments.payload is None or not arguments.profile:
        parser.error("--payload and --profile are required unless --selftest is given")

    try:
        result = normalize(
            arguments.payload.read_bytes(),
            arguments.profile,
            profile_version=arguments.profile_version,
        )
        store_digest = file_normalized(result, root=arguments.store)
    except (NormalizationProfileError, OSError) as error:
        print(f"ERROR {error}", file=sys.stderr)
        return 2
    print(f"profile={result.profile_name}/{result.profile_version}")
    print(f"record_count={result.record_count}")
    print(f"projection_digest={result.projection_digest}")
    print(f"store_digest={store_digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
