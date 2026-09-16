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

``mbpp_json_v1`` rules (pinned; changing any of them is a new version)
---------------------------------------------------------------------
* Input: ArcGIS-style JSON ``{"features": [{"attributes": {...}}, ...]}`` as
  served by MBPP's FeatureServer endpoints.  Only each feature's
  ``attributes`` object is projected; other feature members (e.g.
  ``geometry``) are outside this profile's scope.  A payload that is not
  valid UTF-8, is not such a document (not an object, no ``features`` list,
  or a feature without an ``attributes`` object) fails closed with
  ``NormalizationParseError`` naming what was wrong — never coerced into a
  shape the source did not have.
* Columns: every key appearing under any record's ``attributes`` is a
  candidate column, ordered by first appearance across the records.  A
  *sparse* key — present in some records and absent from others — is dropped
  and reported in ``dropped_fields`` as ``not_extractable``: JSON has no
  header row, so a silently omitted or null-filled sparse key would make the
  projection look complete when it is not.  Sparse keys are never filled
  with a fabricated value.
* Nulls: an explicit JSON ``null`` stays ``null``.  JSON-native types are
  preserved exactly as parsed; nothing is inferred, coerced, or fabricated.
* Rows: stable-sorted by the first column that has at least one non-null
  value and whose non-null values are all strings (ties keep arrival order);
  if no column qualifies, records keep arrival order.  Deterministic either
  way.
* Dedup, identity, and the output projection shape are identical to
  ``fuelprice_csv_v1`` (with ``format`` = ``"json-array-of-objects"``).

``fuelprice_json_v1`` rules (pinned; changing any of them is a new version)
-----------------------------------------------------------------------
* Input: the top-level JSON array of weekly row objects served by
  ``https://api.data.gov.my/data-catalogue?id=fuelprice`` — the URL the
  manifest actually names.  The dataset's pinned CSV profile parses this
  JSON as CSV, reads the single line as a header row, and fails on the
  duplicate header; this profile reads the source as the JSON array it is.
  It does not replace ``fuelprice_csv_v1``, which stays pinned for payloads
  that really are CSV.
* Fail-closed shape: a payload that is not valid UTF-8, is not JSON, is not
  a top-level array, is an empty array, has a non-object element, or has a
  record without ``date`` or without ``series_type`` fails closed with
  ``NormalizationParseError`` naming the record index and the reason —
  never a partial parse.  ``series_type`` is mandatory because the array
  mixes row kinds: the same ``date`` appears both as a price ``level`` and
  as a ``change_weekly`` delta, and a projection that could lose the kind
  marker would conflate the two rows.
* Columns: every key appearing under any record is a candidate column in
  first-appearance order; a key absent from any record (sparse) is dropped
  and reported in ``dropped_fields`` as ``not_extractable`` — the same
  no-fabrication rule as ``mbpp_json_v1``.
* Nulls and numbers: an explicit JSON ``null`` stays ``null`` — a null price
  is unmeasured, not free — and JSON-native types are preserved exactly as
  parsed, so integers stay integers.  No inference, no coercion.
* Rows: sorted into the total order of their canonical JSON bytes, so two
  runs over the same bytes — or the same rows arriving in a different
  order — produce a byte-identical projection.  Two rows sharing a
  ``date`` but differing in ``series_type`` are two records with two
  ``record_ids``; only rows identical after normalization are duplicates.
* Dedup, identity, and the output projection shape are identical to
  ``fuelprice_csv_v1`` (with ``format`` = ``"json-top-level-array"``).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
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
        if self.format == "json-array-of-objects":
            return _normalize_json_features(self, payload)
        if self.format == "json-top-level-array":
            return _normalize_json_array(self, payload)
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
# ArcGIS-JSON normalization (shared engine for json-array-of-objects profiles)
# ---------------------------------------------------------------------------


def _normalize_json_features(profile: NormalizationProfile, payload: bytes) -> NormalizationResult:
    """Apply the pinned ArcGIS-JSON rules documented at module scope."""
    try:
        text = bytes(payload).decode("utf-8")
    except UnicodeDecodeError as error:
        raise NormalizationParseError(
            f"byte offset {error.start}: payload is not valid UTF-8 JSON"
        ) from error

    try:
        document = json.loads(text)
    except json.JSONDecodeError as error:
        raise NormalizationParseError(
            f"offset {error.pos}: JSON parse failed: {error.msg}"
        ) from error

    if not isinstance(document, dict):
        raise NormalizationParseError(
            "payload is not a JSON object; expected an ArcGIS-style document "
            'like {"features": [{"attributes": {...}}]}'
        )
    if "features" not in document:
        raise NormalizationParseError(
            "payload has no 'features' member; an ArcGIS-style document carries "
            'its records as {"features": [...]}'
        )
    features = document["features"]
    if not isinstance(features, list):
        raise NormalizationParseError(
            f"'features' must be a list, got {type(features).__name__}"
        )
    if not features:
        raise NormalizationParseError(
            "'features' is empty; there are no records to project"
        )

    attribute_maps: list[dict[str, Any]] = []
    for index, feature in enumerate(features):
        if not isinstance(feature, dict):
            raise NormalizationParseError(
                f"feature {index}: expected an object with an 'attributes' "
                f"member, got {type(feature).__name__}"
            )
        if "attributes" not in feature:
            raise NormalizationParseError(
                f"feature {index}: no 'attributes' object; a feature without "
                "attributes cannot be projected without inventing its shape"
            )
        attributes = feature["attributes"]
        if not isinstance(attributes, dict):
            raise NormalizationParseError(
                f"feature {index}: 'attributes' must be an object, got "
                f"{type(attributes).__name__}"
            )
        attribute_maps.append(attributes)

    candidate_columns: list[str] = []
    seen_keys: set[str] = set()
    for attributes in attribute_maps:
        for key in attributes:
            if key not in seen_keys:
                seen_keys.add(key)
                candidate_columns.append(key)

    dropped = _DroppedFields()
    columns: list[str] = []
    for column in candidate_columns:
        if all(column in attributes for attributes in attribute_maps):
            columns.append(column)
        else:
            dropped.add(column, "not_extractable")
    if not columns:
        raise NormalizationParseError(
            "every attribute key is sparse (absent from at least one record); "
            "no column is present in all records, so nothing can be projected "
            "without fabricating values"
        )

    typed_rows: list[dict[str, Any]] = [
        {column: attributes[column] for column in columns}
        for attributes in attribute_maps
    ]

    sort_column: str | None = None
    for column in columns:
        values = [row[column] for row in typed_rows if row[column] is not None]
        if values and all(isinstance(value, str) for value in values):
            sort_column = column
            break

    if sort_column is not None:
        pinned_column = sort_column

        def _sort_key(item: tuple[dict[str, Any], int]) -> tuple[tuple[int, Any], int]:
            value = item[0].get(pinned_column)
            if value is None:
                rank: tuple[int, Any] = (0, 0)
            elif isinstance(value, str):
                rank = (2, value)
            else:
                rank = (1, value)
            return (rank, item[1])

        typed_rows = [
            row
            for row, _order in sorted(
                zip(typed_rows, range(len(typed_rows))), key=_sort_key
            )
        ]

    final_rows: list[dict[str, Any]] = []
    seen_rows: set[bytes] = set()
    deduped_rows = 0
    for row in typed_rows:
        row_bytes = canonical_json(row)
        if profile.dedup and row_bytes in seen_rows:
            deduped_rows += 1
            continue
        seen_rows.add(row_bytes)
        final_rows.append(row)

    record_ids = [
        "sha256:" + hashlib.sha256(canonical_json(row)).hexdigest() for row in final_rows
    ]
    projection: dict[str, Any] = {
        "format": "json-array-of-objects",
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
        format="json-array-of-objects",
        projection=projection,
        projection_digest=projection_digest,
        record_count=len(final_rows),
        record_ids=record_ids,
        dropped_fields=dropped.entries,
    )


# ---------------------------------------------------------------------------
# Top-level-JSON-array normalization (engine for json-top-level-array profiles)
# ---------------------------------------------------------------------------


def _normalize_json_array(
    profile: NormalizationProfile, payload: bytes
) -> NormalizationResult:
    """Apply the pinned top-level-array rules documented at module scope."""
    try:
        text = bytes(payload).decode("utf-8")
    except UnicodeDecodeError as error:
        raise NormalizationParseError(
            f"byte offset {error.start}: payload is not valid UTF-8 JSON"
        ) from error

    try:
        document = json.loads(text)
    except json.JSONDecodeError as error:
        raise NormalizationParseError(
            f"offset {error.pos}: JSON parse failed: {error.msg}"
        ) from error

    if not isinstance(document, list):
        raise NormalizationParseError(
            "payload is not a JSON array; expected the top-level array of "
            "weekly row objects served by api.data.gov.my for the fuelprice "
            "dataset"
        )
    if not document:
        raise NormalizationParseError(
            "payload is an empty JSON array; there are no records to project"
        )

    for index, record in enumerate(document):
        if not isinstance(record, dict):
            raise NormalizationParseError(
                f"record {index}: expected a JSON object, got {type(record).__name__}"
            )
        if "date" not in record:
            raise NormalizationParseError(
                f"record {index}: no 'date' key; a fuel-price row without its "
                "observation date cannot be projected without inventing an anchor"
            )
        if "series_type" not in record:
            raise NormalizationParseError(
                f"record {index}: no 'series_type' key; without the series kind "
                "the 'level' and 'change_weekly' rows sharing a date would be "
                "conflated into one record"
            )

    candidate_columns: list[str] = []
    seen_keys: set[str] = set()
    for record in document:
        for key in record:
            if key not in seen_keys:
                seen_keys.add(key)
                candidate_columns.append(key)

    dropped = _DroppedFields()
    columns: list[str] = []
    for column in candidate_columns:
        if all(column in record for record in document):
            columns.append(column)
        else:
            dropped.add(column, "not_extractable")

    typed_rows: list[dict[str, Any]] = [
        {column: record[column] for column in columns} for record in document
    ]
    # Total content order: sorting on the canonical bytes of each full row
    # makes the projection invariant under any permutation of the input
    # array, so the same rows in a different order still produce the same
    # record_ids sequence and the same projection_digest.
    typed_rows.sort(key=canonical_json)

    final_rows: list[dict[str, Any]] = []
    seen_rows: set[bytes] = set()
    deduped_rows = 0
    for row in typed_rows:
        row_bytes = canonical_json(row)
        if profile.dedup and row_bytes in seen_rows:
            deduped_rows += 1
            continue
        seen_rows.add(row_bytes)
        final_rows.append(row)

    record_ids = [
        "sha256:" + hashlib.sha256(canonical_json(row)).hexdigest() for row in final_rows
    ]
    projection: dict[str, Any] = {
        "format": "json-top-level-array",
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
        format="json-top-level-array",
        projection=projection,
        projection_digest=projection_digest,
        record_count=len(final_rows),
        record_ids=record_ids,
        dropped_fields=dropped.entries,
    )


# ---------------------------------------------------------------------------
# Built-in profiles (registered as data)
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

_NULL_HANDLING_JSON: Final[str] = (
    "explicit json null stays null; a key absent from any record drops the "
    "column as not_extractable rather than fabricating nulls"
)

_NUMERIC_HANDLING_JSON: Final[str] = (
    "json-native types are preserved exactly as parsed; no numeric inference "
    "and no coercion"
)

_MBPP_JSON_V1: Final[NormalizationProfile] = NormalizationProfile(
    name="mbpp_json",
    version="v1",
    format="json-array-of-objects",
    input_content_type="application/json",
    row_ordering="stable_sort_by_first_string_typed_column_else_arrival_order",
    null_handling=_NULL_HANDLING_JSON,
    numeric_handling=_NUMERIC_HANDLING_JSON,
    dedup=True,
    description=(
        "ArcGIS-style feature JSON ({\"features\": [{\"attributes\": {...}}]}) as "
        "served by MBPP's FeatureServer endpoints (dataset family "
        "mbpp_arcgis_observation): every attribute key becomes a candidate "
        "column in first-appearance order; sparse keys (absent from some "
        "records) are dropped as not_extractable instead of being fabricated as "
        "nulls; explicit nulls and JSON-native types survive untouched; rows are "
        "stable-sorted by the first string-typed column and exact duplicates are "
        "removed after the sort."
    ),
)

register_profile(_MBPP_JSON_V1)

_ROW_ORDERING_JSON_ARRAY: Final[str] = (
    "sort_by_canonical_row_bytes_full_content_order"
)

_FUELPRICE_JSON_V1: Final[NormalizationProfile] = NormalizationProfile(
    name="fuelprice_json",
    version="v1",
    format="json-top-level-array",
    input_content_type="application/json",
    row_ordering=_ROW_ORDERING_JSON_ARRAY,
    null_handling=_NULL_HANDLING_JSON,
    numeric_handling=_NUMERIC_HANDLING_JSON,
    dedup=True,
    description=(
        "Weekly fuel-price rows as the top-level JSON array served by "
        "api.data.gov.my/data-catalogue?id=fuelprice (the URL the manifest "
        "actually names; the pinned csv profile parses this json as csv, reads "
        "the single line as a header row, and fails on the duplicate header): "
        "every key is a candidate column in first-appearance order; 'date' and "
        "'series_type' must exist in every record — a row without either fails "
        "closed, because dropping the kind marker would conflate the 'level' "
        "and 'change_weekly' rows that share a date; sparse keys are dropped "
        "as not_extractable rather than fabricated; explicit nulls and "
        "json-native types survive untouched; rows are sorted into the total "
        "order of their canonical json bytes so out-of-order input cannot "
        "change the projection; exact duplicates are removed after the sort."
    ),
)

register_profile(_FUELPRICE_JSON_V1)


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

#: ArcGIS payload with a deliberate sparse key: "b" is absent from the second
#: record and "c" from the first, so neither is projectable without fabrication.
_SELFTEST_JSON: Final[bytes] = (
    '{"features":[{"attributes":{"a":1,"b":2}},{"attributes":{"a":1,"c":3}}]}'
).encode("utf-8")

#: api.data.gov.my fuelprice shape: one date, two series kinds. The level row
#: prices are floats with null specials; the change_weekly deltas are integers
#: that must stay integral.
_SELFTEST_FUELPRICE_LEVEL_OBJECT: Final[bytes] = (
    '{"date":"2025-09-04","ron95":2.05,"ron97":3.36,"diesel":2.98,"ron95_skps":null,'
    '"diesel_budi":null,"diesel_skds":null,"ron95_budi95":null,"diesel_eastmsia":null,'
    '"series_type":"level"}'
).encode("utf-8")

_SELFTEST_FUELPRICE_CHANGE_OBJECT: Final[bytes] = (
    '{"date":"2025-09-04","ron95":0,"ron97":0.01,"diesel":0,"ron95_skps":null,'
    '"diesel_budi":null,"diesel_skds":null,"ron95_budi95":null,"diesel_eastmsia":null,'
    '"series_type":"change_weekly"}'
).encode("utf-8")

_SELFTEST_FUELPRICE_JSON: Final[bytes] = (
    b"[" + _SELFTEST_FUELPRICE_LEVEL_OBJECT + b"," + _SELFTEST_FUELPRICE_CHANGE_OBJECT + b"]"
)

#: The same two rows arriving in the opposite order.
_SELFTEST_FUELPRICE_JSON_REVERSED: Final[bytes] = (
    b"[" + _SELFTEST_FUELPRICE_CHANGE_OBJECT + b"," + _SELFTEST_FUELPRICE_LEVEL_OBJECT + b"]"
)

_SELFTEST_FUELPRICE_LEVEL_ROW: Final[dict[str, Any]] = {
    "date": "2025-09-04",
    "ron95": 2.05,
    "ron97": 3.36,
    "diesel": 2.98,
    "ron95_skps": None,
    "diesel_budi": None,
    "diesel_skds": None,
    "ron95_budi95": None,
    "diesel_eastmsia": None,
    "series_type": "level",
}

_SELFTEST_FUELPRICE_CHANGE_ROW: Final[dict[str, Any]] = {
    "date": "2025-09-04",
    "ron95": 0,
    "ron97": 0.01,
    "diesel": 0,
    "ron95_skps": None,
    "diesel_budi": None,
    "diesel_skds": None,
    "ron95_budi95": None,
    "diesel_eastmsia": None,
    "series_type": "change_weekly",
}


def _expected_record_id(row: dict[str, Any]) -> str:
    """The pinned record-id formula, recomputed for selftest expectations."""
    return "sha256:" + hashlib.sha256(canonical_json(row)).hexdigest()


def _run_selftest() -> int:
    """Acceptance selftest for the CSV, ArcGIS-JSON, and fuelprice-JSON
    profiles against a scratch store.

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

        json_first = normalize(_SELFTEST_JSON, "mbpp_json_v1")
        print(f"profile={json_first.profile_name}/{json_first.profile_version}")
        print(f"record_count={json_first.record_count}")
        print(
            "dropped_fields="
            f"{canonical_json(json_first.dropped_fields).decode('utf-8')}"
        )
        json_store_digest = file_normalized(json_first, root=scratch)
        print(f"projection_digest={json_first.projection_digest}")
        print(f"store_digest={json_store_digest}")
        check(
            "json projection_digest matches the digest returned by file_normalized",
            json_first.projection_digest == json_store_digest,
        )
        check("json record_count>0", json_first.record_count > 0)
        check(
            "json projection keeps exactly the members shared with the csv shape",
            set(json_first.projection)
            == {"format", "record_count", "columns", "dropped_fields", "deduped_rows", "record_ids"},
        )
        sparse_entries = [
            entry
            for entry in json_first.dropped_fields
            if entry.get("basis") == "not_extractable" and entry.get("name") in ("b", "c")
        ]
        if len(sparse_entries) != 2:
            print(
                "sparse-key check: dropped_fields as reported = "
                f"{canonical_json(json_first.dropped_fields).decode('utf-8')}"
            )
        check(
            "the sparse keys b and c are each dropped as not_extractable",
            len(sparse_entries) == 2,
        )
        check(
            "json columns keep only the dense key, in first-appearance order",
            json_first.projection["columns"] == ["a"],
        )
        check(
            "the two records collapse to one dense row (deduped_rows == 1)",
            json_first.projection["deduped_rows"] == 1,
        )

        json_second = normalize(_SELFTEST_JSON, "mbpp_json_v1")
        check(
            "two runs of the json profile against the same payload are byte-identical",
            _result_bytes(json_first) == _result_bytes(json_second),
        )

        check(
            "get_profile('mbpp_json_v1') returns the pinned json profile",
            get_profile("mbpp_json_v1") == _MBPP_JSON_V1,
        )
        check(
            "get_profile('fuelprice_csv_v1') still returns the pinned csv profile",
            get_profile("fuelprice_csv_v1") == _FUELPRICE_CSV_V1,
        )

        fuel = normalize(_SELFTEST_FUELPRICE_JSON, "fuelprice_json_v1")
        print(f"profile={fuel.profile_name}/{fuel.profile_version}")
        print(f"record_count={fuel.record_count}")
        fuel_store_digest = file_normalized(fuel, root=scratch)
        print(f"projection_digest={fuel.projection_digest}")
        print(f"store_digest={fuel_store_digest}")
        check(
            "fuelprice-json: projection_digest matches the digest returned by file_normalized",
            fuel.projection_digest == fuel_store_digest,
        )
        check("fuelprice-json: record_count>0", fuel.record_count > 0)
        check(
            "fuelprice-json: one date with two series kinds yields two records",
            fuel.record_count == 2 and fuel.projection["record_count"] == 2,
        )
        check(
            "fuelprice-json: series_type survives as a first-class column",
            "series_type" in fuel.projection["columns"],
        )
        check(
            "fuelprice-json: the level row and the change_weekly row are both retained by id",
            _expected_record_id(_SELFTEST_FUELPRICE_LEVEL_ROW) in fuel.record_ids
            and _expected_record_id(_SELFTEST_FUELPRICE_CHANGE_ROW) in fuel.record_ids,
        )
        check(
            "fuelprice-json: a null price stays null (the zero-coerced row id is absent)",
            _expected_record_id(_SELFTEST_FUELPRICE_LEVEL_ROW) in fuel.record_ids
            and _expected_record_id(
                {**_SELFTEST_FUELPRICE_LEVEL_ROW, "ron95_skps": 0}
            )
            not in fuel.record_ids,
        )
        check(
            "fuelprice-json: an integer price stays integral (the float-coerced row id is absent)",
            _expected_record_id(_SELFTEST_FUELPRICE_CHANGE_ROW) in fuel.record_ids
            and _expected_record_id(
                {**_SELFTEST_FUELPRICE_CHANGE_ROW, "ron95": 0.0}
            )
            not in fuel.record_ids,
        )
        try:
            normalize(b'{"features": []}', "fuelprice_json_v1")
            check("fuelprice-json: a non-array body fails closed", False)
        except NormalizationParseError as error:
            check(
                "fuelprice-json: a non-array body fails closed naming the shape",
                "not a JSON array" in str(error),
            )
        try:
            normalize(b'[{"ron95": 2.05, "series_type": "level"}]', "fuelprice_json_v1")
            check("fuelprice-json: a record without date fails closed", False)
        except NormalizationParseError as error:
            check(
                "fuelprice-json: a record without date fails closed naming date",
                "record 0" in str(error) and "date" in str(error),
            )
        fuel_again = normalize(_SELFTEST_FUELPRICE_JSON, "fuelprice_json_v1")
        check(
            "fuelprice-json: two runs against the same payload are byte-identical",
            _result_bytes(fuel) == _result_bytes(fuel_again),
        )
        fuel_reversed = normalize(_SELFTEST_FUELPRICE_JSON_REVERSED, "fuelprice_json_v1")
        print(f"reversed_projection_digest={fuel_reversed.projection_digest}")
        check(
            "fuelprice-json: out-of-order input rows leave the projection unchanged",
            fuel_reversed.projection_digest == fuel.projection_digest
            and fuel_reversed.record_ids == fuel.record_ids,
        )
        check(
            "get_profile('fuelprice_json_v1') returns the pinned fuelprice json profile",
            get_profile("fuelprice_json_v1") == _FUELPRICE_JSON_V1,
        )
    except Exception as error:  # noqa: BLE001 — the selftest reports, never traces
        failures.append(f"selftest raised {type(error).__name__}: {error}")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    if failures:
        for failure in failures:
            print(f"FAIL {failure}", file=sys.stderr)
        return 1
    print("selftest passed: all three profiles pinned, digests matched, results byte-identical")
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
