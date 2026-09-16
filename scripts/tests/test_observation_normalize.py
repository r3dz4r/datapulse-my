"""Tests pinning observation_normalize's truth rules for all three built-in profiles.

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


#: One fuelprice object per series kind for the same date: the price `level`
#: row and the week-on-week `change_weekly` row. Null prices are unmeasured;
#: the change row's 0 deltas are integers that must stay integral.
_FUELPRICE_LEVEL_OBJECT: bytes = (
    '{"date":"2025-09-04","ron95":2.05,"ron97":3.36,"diesel":2.98,"ron95_skps":null,'
    '"diesel_budi":null,"diesel_skds":null,"ron95_budi95":null,"diesel_eastmsia":null,'
    '"series_type":"level"}'
).encode("utf-8")

_FUELPRICE_CHANGE_OBJECT: bytes = (
    '{"date":"2025-09-04","ron95":0,"ron97":0.01,"diesel":0,"ron95_skps":null,'
    '"diesel_budi":null,"diesel_skds":null,"ron95_budi95":null,"diesel_eastmsia":null,'
    '"series_type":"change_weekly"}'
).encode("utf-8")

FUELPRICE_JSON_MAIN: bytes = (
    b"[" + _FUELPRICE_LEVEL_OBJECT + b"," + _FUELPRICE_CHANGE_OBJECT + b"]"
)

#: The same two rows arriving in the opposite order.
FUELPRICE_JSON_REVERSED: bytes = (
    b"[" + _FUELPRICE_CHANGE_OBJECT + b"," + _FUELPRICE_LEVEL_OBJECT + b"]"
)

#: MAIN plus an exact repeat of the level row: dropped and counted, not kept.
FUELPRICE_JSON_DUPLICATE: bytes = (
    b"["
    + _FUELPRICE_LEVEL_OBJECT
    + b","
    + _FUELPRICE_CHANGE_OBJECT
    + b","
    + _FUELPRICE_LEVEL_OBJECT
    + b"]"
)

#: The rows the json engine should retain, in the payload's key order.
FUELPRICE_JSON_LEVEL_ROW: dict[str, Any] = {
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

FUELPRICE_JSON_CHANGE_ROW: dict[str, Any] = {
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
            (FUELPRICE_JSON_MAIN, "fuelprice_json_v1"),
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


def test_fuelprice_json_keeps_both_series_kinds_for_one_date() -> None:
    """Protects the pilot's lead invariant: the same date as a `level` row and
    as a `change_weekly` row is two records with two record_ids — not a
    duplicate to drop — and `series_type` survives as a first-class column."""
    result = normalize(FUELPRICE_JSON_MAIN, "fuelprice_json_v1")
    assert result.record_count == 2
    assert result.projection["record_count"] == 2
    assert result.projection["deduped_rows"] == 0
    assert "series_type" in result.projection["columns"]
    assert _row_record_id(FUELPRICE_JSON_LEVEL_ROW) in result.record_ids
    assert _row_record_id(FUELPRICE_JSON_CHANGE_ROW) in result.record_ids


def test_fuelprice_json_exact_duplicates_are_dropped_and_counted() -> None:
    """Protects the dedup boundary: the profile carries the module-wide
    exact-duplicate policy and no more — a row identical after normalization
    is dropped and counted, while the two series kinds sharing a date are not
    duplicates and both survive."""
    result = normalize(FUELPRICE_JSON_DUPLICATE, "fuelprice_json_v1")
    assert result.projection["deduped_rows"] == 1
    assert result.record_count == 2


def test_fuelprice_json_null_price_stays_null_not_zero() -> None:
    """Protects null semantics: a null price is unmeasured, not free. The
    retained level row's record_id pins ron95_skps as null, and the id the
    row would carry under 0-coercion is absent."""
    result = normalize(FUELPRICE_JSON_MAIN, "fuelprice_json_v1")
    assert _row_record_id(FUELPRICE_JSON_LEVEL_ROW) in result.record_ids
    zero_coerced = {**FUELPRICE_JSON_LEVEL_ROW, "ron95_skps": 0}
    assert _row_record_id(zero_coerced) not in result.record_ids


def test_fuelprice_json_integer_price_stays_integral() -> None:
    """Protects numeric typing: the change row's ron95 delta parses as the
    integer 0 and the record_id pins that; the id under float coercion (0.0)
    is absent."""
    result = normalize(FUELPRICE_JSON_MAIN, "fuelprice_json_v1")
    assert _row_record_id(FUELPRICE_JSON_CHANGE_ROW) in result.record_ids
    float_coerced = {**FUELPRICE_JSON_CHANGE_ROW, "ron95": 0.0}
    assert _row_record_id(float_coerced) not in result.record_ids


def test_fuelprice_json_non_array_body_fails_closed_without_projection() -> None:
    """Protects the parse contract: a JSON object where the top-level array
    belongs raises NormalizationParseError naming the shape, and an empty
    array is equally a non-projection. The raise is the no-projection proof:
    no result can be produced from a body of the wrong shape."""
    with pytest.raises(NormalizationParseError, match="not a JSON array"):
        normalize(b'{"features": []}', "fuelprice_json_v1")
    with pytest.raises(NormalizationParseError, match="empty JSON array"):
        normalize(b"[]", "fuelprice_json_v1")


def test_fuelprice_json_record_without_date_or_series_type_fails_closed() -> None:
    """Protects the two mandatory anchors: a record lacking `date` (no
    observation anchor) or lacking `series_type` (kind marker lost, level and
    change_weekly would conflate) is named by index and fails closed rather
    than being partially projected."""
    with pytest.raises(NormalizationParseError, match=r"record 0.*'date'"):
        normalize(b'[{"ron95": 2.05, "series_type": "level"}]', "fuelprice_json_v1")
    with pytest.raises(NormalizationParseError, match=r"record 1.*'series_type'"):
        normalize(
            b'[{"date": "2025-09-04", "ron95": 2.05, "series_type": "level"},'
            b'{"date": "2025-09-11", "ron95": 2.05}]',
            "fuelprice_json_v1",
        )


def test_fuelprice_json_sparse_keys_are_declared_not_extractable() -> None:
    """Protects the no-fabrication rule for the new engine: a key absent from
    any record drops the column as not_extractable instead of being padded
    with invented nulls."""
    body = (
        b'[{"date":"2025-09-04","ron95":2.05,"series_type":"level"},'
        b'{"date":"2025-09-11","ron97":3.36,"series_type":"level"}]'
    )
    result = normalize(body, "fuelprice_json_v1")
    assert result.dropped_fields == [
        {"name": "ron95", "basis": "not_extractable"},
        {"name": "ron97", "basis": "not_extractable"},
    ]
    assert result.projection["columns"] == ["date", "series_type"]


def test_fuelprice_json_same_bytes_twice_produce_identical_projections() -> None:
    """Protects determinism: two runs over the same payload agree on every
    field, and the canonical projection bytes are identical."""
    first = normalize(FUELPRICE_JSON_MAIN, "fuelprice_json_v1")
    second = normalize(FUELPRICE_JSON_MAIN, "fuelprice_json_v1")
    assert first == second
    assert first.projection_digest == second.projection_digest
    assert first.record_ids == second.record_ids
    assert canonical_json(first.projection) == canonical_json(second.projection)


def test_fuelprice_json_out_of_order_rows_leave_the_projection_unchanged() -> None:
    """Protects the pinned ordering: rows are placed in the total order of
    their canonical bytes, so the same rows arriving in reverse still produce
    the same record_ids sequence and the same projection digest."""
    forward = normalize(FUELPRICE_JSON_MAIN, "fuelprice_json_v1")
    backward = normalize(FUELPRICE_JSON_REVERSED, "fuelprice_json_v1")
    assert backward.projection_digest == forward.projection_digest
    assert backward.record_ids == forward.record_ids
    assert canonical_json(backward.projection) == canonical_json(forward.projection)
