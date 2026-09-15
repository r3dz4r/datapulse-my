"""Tests pinning observation_normalize's truth rules for both built-in profiles.

These tests exist because the module's own ``--selftest`` prints and exits but
is not wired to CI: without pinned tests, a later change can silently drop a
sparse key, unbind ``projection_digest`` from what the store wrote, or make a
projection non-reproducible while the gate stays green.  Every test here names
a property from the module's documented contract and fails when that property
is broken.  Scratch store roots are created with ``tempfile.mkdtemp()`` inside
the worktree and removed in a ``finally`` block; the production store root is
never touched.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from observation_normalize import (  # noqa: E402
    NormalizationParseError,
    NormalizationProfile,
    NormalizationProfileError,
    file_normalized,
    normalize,
    register_profile,
)
from observation_store import canonical_json  # noqa: E402

RECORD_ID_FORM = re.compile(r"^sha256:[0-9a-f]{64}$")

#: Four data rows over trimmed headers; the third row exactly duplicates the
#: first, the trailing header cell is empty, and "n/a" sits in a numeric column.
CSV_MAIN: bytes = (
    "date, ron95 , diesel,region,\n"
    "2025-01-08,2.05,2.98,kl,\n"
    "2025-01-01,2.05,2.98,kl,\n"
    "2025-01-08,2.05,2.98,kl,\n"
    "2025-01-15,2.05,n/a,kl,\n"
).encode("utf-8")

#: Three unique rows under headers padded with whitespace; no other quirks.
CSV_CLEAN: bytes = (
    "  date  , region , price\n"
    "2025-01-01,kl,2.05\n"
    "2025-01-08,jb,2.07\n"
    "2025-01-15,kl,2.09\n"
).encode("utf-8")

#: "b" is absent from the second record and "c" from the first: both sparse.
JSON_SPARSE: bytes = (
    '{"features":[{"attributes":{"a":1,"b":2}},{"attributes":{"a":1,"c":3}}]}'
).encode("utf-8")

#: Dense keys whose first appearance order (b, a, c) differs from sorted order.
JSON_FIRST_APPEARANCE: bytes = (
    '{"features":[{"attributes":{"b":1,"a":2,"c":9}},{"attributes":{"c":3,"b":4,"a":5}}]}'
).encode("utf-8")

#: "a" is dense but explicitly null in every record; it must survive as null.
JSON_EXPLICIT_NULL: bytes = (
    '{"features":[{"attributes":{"a":null,"b":1}},{"attributes":{"a":null,"b":2}}]}'
).encode("utf-8")

#: The row the CSV engine should retain for the 2025-01-15 line: the non-numeric
#: "n/a" cell became null, not a fabricated numeric and not a string.
CSV_MAIN_ROW_NONNUMERIC: dict[str, Any] = {
    "date": "2025-01-15",
    "ron95": 2.05,
    "diesel": None,
    "region": "kl",
}


def _scratch_root() -> Path:
    """A fresh store root inside the worktree, never the production root."""
    return Path(tempfile.mkdtemp(prefix=".test-observation-normalize-", dir=ROOT))


def _row_record_id(row: dict[str, Any]) -> str:
    """The pinned record-id formula: sha256 over canonical_json of the row."""
    return "sha256:" + hashlib.sha256(canonical_json(row)).hexdigest()


def _no_dedup_csv_profile() -> NormalizationProfile:
    """A second CSV profile identical to fuelprice_csv_v1 except dedup=False."""
    return NormalizationProfile(
        name="fuelprice_csv",
        version="v2",
        format="csv",
        input_content_type="text/csv",
        row_ordering="stable_sort_by_first_column_then_original_row_order",
        null_handling="empty_cell_becomes_null",
        numeric_handling=(
            "column numeric when strictly more than half of its non-null cells parse as "
            "integers or finite floats; integers stay integers; non-numeric cells in "
            "numeric columns are dropped as does_not_apply and never coerced"
        ),
        dedup=False,
        description="test-only variant of fuelprice_csv_v1 that keeps duplicate rows",
    )


def test_csv_record_count_and_trimmed_column_order_are_pinned() -> None:
    """Protects the count and shape contract: unique rows in, same count out;
    headers trimmed; declared column order preserved."""
    result = normalize(CSV_CLEAN, "fuelprice_csv_v1")
    assert result.record_count == 3
    assert result.projection["record_count"] == 3
    assert result.projection["columns"] == ["date", "region", "price"]
    assert result.dropped_fields == []


def test_csv_duplicate_rows_are_dropped_counted_and_the_rule_is_profile_data() -> None:
    """Protects the dedup rule: exact duplicates are dropped and counted under
    fuelprice_csv_v1, and a profile that keeps duplicates changes the outcome —
    proving dedup is data in the profile, not hard-coded behaviour."""
    result = normalize(CSV_MAIN, "fuelprice_csv_v1")
    assert result.record_count == 3  # four data rows, one exact duplicate
    assert result.projection["deduped_rows"] == 1

    register_profile(_no_dedup_csv_profile())
    kept = normalize(CSV_MAIN, "fuelprice_csv_v2")
    assert kept.projection["deduped_rows"] == 0
    assert kept.record_count == 4
    assert kept.projection_digest != result.projection_digest


def test_csv_nonnumeric_cell_in_numeric_column_is_declared_not_coerced() -> None:
    """Protects the no-fabrication rule: "n/a" in the numeric diesel column is
    reported as does_not_apply, and the row's record_id pins that the cell
    became null — a coerced or string value would change the id."""
    result = normalize(CSV_MAIN, "fuelprice_csv_v1")
    assert result.dropped_fields == [
        {"name": "column_4", "basis": "not_extractable"},  # trailing empty header
        {"name": "diesel", "basis": "does_not_apply"},
    ]
    assert _row_record_id(CSV_MAIN_ROW_NONNUMERIC) in result.record_ids


def test_csv_record_ids_are_one_per_record_and_never_a_column() -> None:
    """Protects identity: one well-formed sha256 record_id per retained record,
    and record_ids never leaks into the column list."""
    result = normalize(CSV_MAIN, "fuelprice_csv_v1")
    assert len(result.record_ids) == result.record_count == 3
    assert len(set(result.record_ids)) == 3
    for record_id in result.record_ids:
        assert RECORD_ID_FORM.fullmatch(record_id) is not None, record_id
        assert re.fullmatch(r"[0-9a-f]{64}", record_id.removeprefix("sha256:"))
    assert "record_ids" not in result.projection["columns"]


def test_json_sparse_keys_are_declared_not_extractable() -> None:
    """Protects the sparse-key declaration: keys absent from any record are
    named in dropped_fields with basis not_extractable — not filled, not
    reclassified under a different basis."""
    result = normalize(JSON_SPARSE, "mbpp_json_v1")
    assert result.dropped_fields == [
        {"name": "b", "basis": "not_extractable"},
        {"name": "c", "basis": "not_extractable"},
    ]
    assert result.projection["columns"] == ["a"]


def test_json_columns_preserve_first_appearance_order() -> None:
    """Protects column ordering: keys enter columns by first appearance across
    records, so (b, a, c) stays unsorted."""
    result = normalize(JSON_FIRST_APPEARANCE, "mbpp_json_v1")
    assert result.projection["columns"] == ["b", "a", "c"]
    assert result.dropped_fields == []


def test_json_explicit_null_stays_null_and_is_not_a_dropped_field() -> None:
    """Protects null semantics: a dense key that is explicitly null survives as
    null. The projection does not carry rows, so the value side is pinned via
    the record_ids — canonical rows {"a":null,"b":n} — which change under any
    fabrication or drop."""
    result = normalize(JSON_EXPLICIT_NULL, "mbpp_json_v1")
    assert result.projection["columns"] == ["a", "b"]
    assert result.dropped_fields == []
    assert result.record_ids == [
        _row_record_id({"a": None, "b": 1}),
        _row_record_id({"a": None, "b": 2}),
    ]


def test_projection_digest_is_bound_to_what_the_store_holds() -> None:
    """Protects the audit chain: projection_digest equals the digest the store
    returns from file_normalized, and equals sha256 over canonical_json of the
    projection recomputed independently here."""
    scratch = _scratch_root()
    try:
        for payload, designation in (
            (CSV_MAIN, "fuelprice_csv_v1"),
            (JSON_SPARSE, "mbpp_json_v1"),
        ):
            result = normalize(payload, designation)
            recomputed = "sha256:" + hashlib.sha256(
                canonical_json(result.projection)
            ).hexdigest()
            assert recomputed == result.projection_digest
            assert file_normalized(result, root=scratch) == result.projection_digest
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def test_normalize_is_reproducible_byte_for_byte() -> None:
    """Protects determinism: the same (payload, profile) yields equal results —
    every field, including projection_digest and record_ids, and byte-identical
    canonical projections."""
    for payload, designation in (
        (CSV_MAIN, "fuelprice_csv_v1"),
        (JSON_SPARSE, "mbpp_json_v1"),
        (JSON_EXPLICIT_NULL, "mbpp_json_v1"),
    ):
        first = normalize(payload, designation)
        second = normalize(payload, designation)
        assert first == second
        assert first.projection_digest == second.projection_digest
        assert first.record_ids == second.record_ids
        assert canonical_json(first.projection) == canonical_json(second.projection)


def test_file_normalized_writes_only_under_normalized_and_never_blobs() -> None:
    """Protects the no-raw-overwrite rule: filing a projection creates files
    only under normalized/ and nothing under blobs/. The store API only takes a
    root, so "nothing outside the root" is observed as: every file present in
    the scratch root afterwards lives under normalized/."""
    scratch = _scratch_root()
    try:
        result = normalize(CSV_MAIN, "fuelprice_csv_v1")
        files_before = {p for p in scratch.rglob("*") if p.is_file()}
        assert file_normalized(result, root=scratch) == result.projection_digest
        files_after = {p for p in scratch.rglob("*") if p.is_file()}
        new_files = files_after - files_before
        assert new_files, "filing a projection must write at least one file"
        normalized_root = scratch / "normalized"
        for path in new_files:
            assert normalized_root in path.parents, path
        assert any(normalized_root.rglob("*.json"))
        assert not (scratch / "blobs").exists()
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def test_unknown_profile_or_version_fails_closed() -> None:
    """Protects fail-closed lookup: an unknown name raises, and a known name
    with an unknown version raises instead of silently returning the default —
    both as the declared NormalizationProfileError."""
    with pytest.raises(NormalizationProfileError, match="no normalization profile"):
        normalize(CSV_MAIN, "no_such_profile_v1")
    with pytest.raises(NormalizationProfileError, match="version 'v999'"):
        normalize(CSV_MAIN, "fuelprice_csv", profile_version="v999")


def test_malformed_json_payloads_fail_closed_naming_the_problem() -> None:
    """Protects the parse contract: invalid JSON, a document without features,
    and a feature without attributes each raise NormalizationParseError with a
    message naming what was wrong — never a coerced projection."""
    with pytest.raises(NormalizationParseError, match="JSON parse failed"):
        normalize(b'{"features": [', "mbpp_json_v1")
    with pytest.raises(NormalizationParseError, match="features"):
        normalize(b'{"results": []}', "mbpp_json_v1")
    with pytest.raises(NormalizationParseError, match="attributes"):
        normalize(b'{"features": [{"geometry": {}}]}', "mbpp_json_v1")
