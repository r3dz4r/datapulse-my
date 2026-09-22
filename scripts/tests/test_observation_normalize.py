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
import json
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
    get_profile,
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

#: The live fuelprice source is a top-level JSON array of objects, one line
#: with 9570 fields across 957 records.  The fixture is a frozen slice copied
#: verbatim from a real capture (see config/observation-policies.json and the
#: pilot's source URL), so a test can never again "verify" the JSON source
#: with a CSV fixture: the same drift that let fuelprice_csv_v1 look correct
#: against a hand-written CSV must fail here.
FUELPRICE_FIXTURE: Path = ROOT / "scripts/tests/fixtures/fuelprice_live_array.json"

#: The exact key set the live array carries; a projection must keep all ten.
FUELPRICE_LIVE_KEYS: frozenset[str] = frozenset(
    {
        "date",
        "ron95",
        "ron97",
        "diesel",
        "ron95_skps",
        "diesel_budi",
        "diesel_skds",
        "series_type",
        "ron95_budi95",
        "diesel_eastmsia",
    }
)


def _live_fixture_bytes() -> bytes:
    """The fixture payload exactly as it sits on disk."""
    return FUELPRICE_FIXTURE.read_bytes()


def _schema_format_enum() -> list[Any]:
    """The envelope schema's admitted ``normalized_projection.format`` values."""
    schema = json.loads(
        (ROOT / "historical-observation.schema.json").read_text(encoding="utf-8")
    )
    return schema["properties"]["normalized_projection"]["properties"]["format"]["enum"]


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
            (_live_fixture_bytes(), "fuelprice_json_v1"),
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
        (_live_fixture_bytes(), "fuelprice_json_v1"),
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


# ---------------------------------------------------------------------------
# fuelprice_json_v1 — the live fuelprice source shape
# ---------------------------------------------------------------------------


def test_fuelprice_json_live_fixture_projects_a_positive_record_count() -> None:
    """The load-bearing acceptance: the frozen slice of the real source — a
    top-level JSON array of objects — projects under the newly registered
    profile with a positive record count, the ten live keys as columns, and
    nothing silently dropped.  If the profile is deleted or its engine is
    mis-wired, this is the test that fails."""
    result = normalize(_live_fixture_bytes(), "fuelprice_json_v1")
    assert result.record_count > 0
    assert result.projection["record_count"] == result.record_count
    assert result.format == "json-array-of-objects"
    assert result.projection["format"] == "json-array-of-objects"
    assert set(result.projection["columns"]) == FUELPRICE_LIVE_KEYS
    assert result.dropped_fields == []
    assert len(result.record_ids) == result.record_count


def test_fuelprice_json_format_is_admitted_by_the_envelope_schema() -> None:
    """Protects the schema boundary the earlier attempt crossed: the projection
    ``format`` the profile emits must be one the historical-observation schema
    admits, or ``capture_observation`` rejects the envelope and the pilot can
    never report the projection as retained.  A private dispatch-only format
    such as ``json-top-level-array`` fails here by construction."""
    result = normalize(_live_fixture_bytes(), "fuelprice_json_v1")
    assert result.format in _schema_format_enum()
    assert result.projection["format"] in _schema_format_enum()


def test_fuelprice_json_mutation_control_reports_a_parse_failure() -> None:
    """The mutation control: the same bytes with invalid JSON (its closing
    bracket removed) must raise NormalizationParseError naming the parse
    failure.  A projection here would mean malformed input was coerced."""
    mutated = _live_fixture_bytes().rstrip()[:-1]
    with pytest.raises(NormalizationParseError, match="JSON parse failed"):
        normalize(mutated, "fuelprice_json_v1")


def test_fuelprice_csv_profile_still_rejects_the_live_json_array() -> None:
    """The negative control must keep failing: ``fuelprice_csv_v1`` is pinned
    to CSV and must reject the JSON payload rather than silently projecting it.
    The single line parses as one header row whose trimmed cells repeat, so the
    duplicate-header guard fails closed."""
    with pytest.raises(NormalizationParseError, match="duplicate header"):
        normalize(_live_fixture_bytes(), "fuelprice_csv_v1")


def test_fuelprice_json_and_csv_profiles_are_distinct_designations() -> None:
    """Protects the versioning contract: the new profile is registered under
    its own name/version and the pinned CSV profile is untouched, so an
    existing CSV projection keeps its meaning."""
    assert get_profile("fuelprice_json_v1").name == "fuelprice_json"
    assert get_profile("fuelprice_json_v1").version == "v1"
    assert get_profile("fuelprice_json_v1").format == "json-array-of-objects"
    assert get_profile("fuelprice_json_v1").engine == "top-level-array"
    assert get_profile("fuelprice_csv_v1").format == "csv"
    assert get_profile("fuelprice_csv_v1").engine == ""


def test_fuelprice_json_keeps_both_series_kinds_for_one_date() -> None:
    """Protects the pilot's lead invariant: the same date as a ``level`` row
    and as a ``change_weekly`` row is two records with two record_ids — not a
    duplicate to drop — and ``series_type`` survives as a first-class column."""
    body = (
        b'[{"date":"2025-09-04","ron95":2.05,"series_type":"level"},'
        b'{"date":"2025-09-04","ron95":0,"series_type":"change_weekly"}]'
    )
    result = normalize(body, "fuelprice_json_v1")
    assert result.record_count == 2
    assert result.projection["deduped_rows"] == 0
    assert "series_type" in result.projection["columns"]
    assert _row_record_id(
        {"date": "2025-09-04", "ron95": 2.05, "series_type": "level"}
    ) in result.record_ids
    assert _row_record_id(
        {"date": "2025-09-04", "ron95": 0, "series_type": "change_weekly"}
    ) in result.record_ids


def test_fuelprice_json_exact_duplicates_are_dropped_and_counted() -> None:
    """Protects the dedup boundary: an exactly repeated row is dropped and
    counted, while the two series kinds sharing a date are not duplicates."""
    body = (
        b'[{"date":"2025-09-04","ron95":2.05,"series_type":"level"},'
        b'{"date":"2025-09-04","ron95":0,"series_type":"change_weekly"},'
        b'{"date":"2025-09-04","ron95":2.05,"series_type":"level"}]'
    )
    result = normalize(body, "fuelprice_json_v1")
    assert result.projection["deduped_rows"] == 1
    assert result.record_count == 2


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


def test_fuelprice_json_non_array_and_unanchored_records_fail_closed() -> None:
    """Protects the shape contract: an object where the top-level array
    belongs, an empty array, a record without ``date``, and a record without
    ``series_type`` each fail closed naming the problem rather than producing
    a partial projection."""
    with pytest.raises(NormalizationParseError, match="not a JSON array"):
        normalize(b'{"features": []}', "fuelprice_json_v1")
    with pytest.raises(NormalizationParseError, match="empty JSON array"):
        normalize(b"[]", "fuelprice_json_v1")
    with pytest.raises(NormalizationParseError, match=r"record 0.*'date'"):
        normalize(b'[{"ron95": 2.05, "series_type": "level"}]', "fuelprice_json_v1")
    with pytest.raises(NormalizationParseError, match=r"record 1.*'series_type'"):
        normalize(
            b'[{"date":"2025-09-04","ron95":2.05,"series_type":"level"},'
            b'{"date":"2025-09-11","ron95":2.05}]',
            "fuelprice_json_v1",
        )


def test_fuelprice_json_out_of_order_rows_leave_the_projection_unchanged() -> None:
    """Protects the pinned ordering: rows are placed in the total order of
    their canonical bytes, so the same rows arriving in reverse still produce
    the same record_ids sequence and the same projection digest."""
    level = b'{"date":"2025-09-04","ron95":2.05,"series_type":"level"}'
    change = b'{"date":"2025-09-04","ron95":0,"series_type":"change_weekly"}'
    forward = normalize(b"[" + level + b"," + change + b"]", "fuelprice_json_v1")
    backward = normalize(b"[" + change + b"," + level + b"]", "fuelprice_json_v1")
    assert backward.projection_digest == forward.projection_digest
    assert backward.record_ids == forward.record_ids
    assert canonical_json(backward.projection) == canonical_json(forward.projection)
