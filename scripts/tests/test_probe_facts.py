"""Tests for the additive probe shape facts in ``scripts/probe_facts.py``.

The helper reads a body the probe already downloaded and reports date geometry
and low-cardinality dimensions. The rules worth guarding hardest are the
negative ones: a column that does not parse as ISO dates must never be reported
as one, and a malformed body must yield nulls rather than an exception.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from scripts.probe_facts import facts_from_csv, facts_from_json, null_facts

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "scripts" / "probe_facts.py"
CHECK_SCRIPT = ROOT / "scripts" / "check.sh"
FUELPRICE = ROOT / "scripts" / "tests" / "fixtures" / "fuelprice_live_array.json"


def _run_helper(mode: str, body: bytes) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, str(HELPER), mode],
        input=body,
        capture_output=True,
        check=False,
    )


def _helper_facts(mode: str, body: bytes) -> dict:
    completed = _run_helper(mode, body)
    assert completed.returncode == 0, completed.stderr.decode()
    return json.loads(completed.stdout)


# --- helper behaviour -------------------------------------------------------


def test_json_array_reports_exact_date_counts_and_dimension() -> None:
    facts = facts_from_json(FUELPRICE.read_text(encoding="utf-8"))

    assert facts == {
        "newest_date": "2026-09-17",
        "oldest_date": "2026-09-03",
        "distinct_dates": 3,
        "rows_per_date": {"min": 2, "mean": 2.0, "max": 2},
        "largest_gap_days": 7,
        "dimension_cardinality": {"series_type": 2},
    }


def test_csv_body_reports_date_counts_and_dimensions() -> None:
    body = "date,station,value\n2026-09-01,A,1\n2026-09-02,A,2\n2026-09-02,B,3\n"

    facts = facts_from_csv(body)

    assert facts["newest_date"] == "2026-09-02"
    assert facts["oldest_date"] == "2026-09-01"
    assert facts["distinct_dates"] == 2
    assert facts["rows_per_date"] == {"min": 1, "mean": 1.5, "max": 2}
    assert facts["largest_gap_days"] == 1
    assert facts["dimension_cardinality"] == {"station": 2, "value": 3}

    # The CLI's CSV mode must agree with the function.
    assert _helper_facts("--csv", body.encode()) == facts


def test_body_without_date_column_returns_nulls() -> None:
    facts = facts_from_json('[{"name": "alpha"}, {"name": "beta"}]')

    assert facts["newest_date"] is None
    assert facts["oldest_date"] is None
    assert facts["distinct_dates"] == 0
    assert facts["rows_per_date"] is None
    assert facts["largest_gap_days"] is None
    assert facts["dimension_cardinality"] == {"name": 2}


def test_single_distinct_date_has_null_gap() -> None:
    facts = facts_from_json('[{"date": "2026-01-01"}, {"date": "2026-01-01"}]')

    assert facts["newest_date"] == "2026-01-01"
    assert facts["oldest_date"] == "2026-01-01"
    assert facts["distinct_dates"] == 1
    assert facts["rows_per_date"] == {"min": 2, "mean": 2.0, "max": 2}
    assert facts["largest_gap_days"] is None


def test_duplicate_dates_count_rows_over_distinct_dates() -> None:
    facts = facts_from_json(
        '[{"date": "2026-01-01"}, {"date": "2026-01-01"}, {"date": "2026-01-03"}]'
    )

    assert facts["distinct_dates"] == 2
    assert facts["rows_per_date"] == {"min": 1, "mean": 1.5, "max": 2}
    assert facts["largest_gap_days"] == 2


def test_iso_timestamps_use_the_date_part() -> None:
    facts = facts_from_json(
        '[{"timestamp": "2026-01-01T23:59:59Z"}, '
        '{"timestamp": "2026-01-02T00:00:01+08:00"}]'
    )

    assert facts["newest_date"] == "2026-01-02"
    assert facts["oldest_date"] == "2026-01-01"
    assert facts["distinct_dates"] == 2


def test_non_iso_column_is_not_treated_as_dates() -> None:
    facts = facts_from_json('[{"date": "01/08/2026"}, {"date": "02/08/2026"}]')

    assert facts["newest_date"] is None
    assert facts["oldest_date"] is None
    assert facts["distinct_dates"] == 0
    assert facts["rows_per_date"] is None
    assert facts["largest_gap_days"] is None


def test_iso_values_in_a_non_date_named_column_are_ignored() -> None:
    # Only date-ish column names are candidates; a "code" column that happens
    # to hold ISO strings is not evidence of a date dimension.
    facts = facts_from_json('[{"code": "2026-01-01"}, {"code": "2026-01-02"}]')

    assert facts["newest_date"] is None
    assert facts["oldest_date"] is None
    assert facts["distinct_dates"] == 0
    assert facts["rows_per_date"] is None
    assert facts["largest_gap_days"] is None


def test_one_unparseable_value_disqualifies_the_whole_column() -> None:
    # A partial parse would produce a plausible but wrong newest date, so the
    # strict rule is that every non-empty value must parse.
    facts = facts_from_json('[{"date": "2026-01-01"}, {"date": "01/08/2026"}]')

    assert facts["newest_date"] is None
    assert facts["oldest_date"] is None
    assert facts["distinct_dates"] == 0


def test_empty_and_non_tabular_bodies_return_null_facts() -> None:
    assert facts_from_json("[]") == null_facts()
    assert facts_from_json("{}") == null_facts()
    assert facts_from_json('{"meta": {"version": 1}}') == null_facts()


def test_dimension_cardinality_ignores_numeric_and_high_cardinality_columns() -> None:
    numeric = facts_from_json('[{"n": 1}, {"n": 2}]')
    assert numeric["dimension_cardinality"] == {}

    high_cardinality = facts_from_json(
        json.dumps([{"code": str(index)} for index in range(201)])
    )
    assert high_cardinality["dimension_cardinality"] == {}


def test_dimension_cardinality_is_capped_at_eight_sorted_columns() -> None:
    columns = [f"dim_{index:02d}" for index in range(10)]
    facts = facts_from_json(json.dumps([dict.fromkeys(columns, "value")]))

    assert list(facts["dimension_cardinality"]) == sorted(columns)[:8]
    assert set(facts["dimension_cardinality"].values()) == {1}


# --- CLI robustness ---------------------------------------------------------


def test_malformed_bodies_never_raise_and_never_emit_partial_json() -> None:
    cases = [
        ("--json", b"{not json"),
        ("--json", b""),
        ("--json", b'\xff\xfe\x00binary'),
        ("--csv", b'name,address\nAlpha,"unterminated\n'),
        ("--csv", b""),
    ]
    for mode, body in cases:
        completed = _run_helper(mode, body)
        assert completed.returncode == 0, completed.stderr.decode()
        assert json.loads(completed.stdout) == null_facts()


def test_cli_output_is_byte_identical_across_runs() -> None:
    body = FUELPRICE.read_bytes()

    first = _run_helper("--json", body)
    second = _run_helper("--json", body)

    assert first.returncode == second.returncode == 0
    assert first.stdout == second.stdout


# --- check.sh wiring --------------------------------------------------------

FAKE_CURL = """#!/usr/bin/env bash
set -euo pipefail
output_path=""
headers_path=""
while (( $# > 0 )); do
  case "$1" in
    --output) output_path="$2"; shift 2 ;;
    --dump-header) headers_path="$2"; shift 2 ;;
    --max-time|--write-out) shift 2 ;;
    *) shift ;;
  esac
done
[[ -z "$output_path" || "$output_path" == "/dev/null" ]] || cp "$PROBE_FACTS_TEST_BODY" "$output_path"
[[ -z "$headers_path" ]] || printf 'HTTP/1.1 200 OK\\r\\nLast-Modified: Sat, 08 Aug 2026 12:00:00 GMT\\r\\n\\r\\n' > "$headers_path"
printf '200'
"""


def _run_check_sh(tmp_path: Path, body: bytes, suffix: str) -> dict:
    body_path = tmp_path / f"body{suffix}"
    body_path.write_bytes(body)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_curl = bin_dir / "curl"
    fake_curl.write_text(FAKE_CURL, encoding="utf-8")
    fake_curl.chmod(0o755)

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    manifest = {
        "datasets": [
            {
                "id": "captured-facts",
                "url": f"https://example.invalid/captured{suffix}",
                "refresh_frequency": "daily",
                "namespace": "test",
            }
        ]
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    environment = os.environ.copy()
    environment["PATH"] = f"{bin_dir}:{environment['PATH']}"
    environment["PROBE_FACTS_TEST_BODY"] = str(body_path)

    completed = subprocess.run(
        ["bash", str(CHECK_SCRIPT), "manifest.json"],
        cwd=run_dir,
        env=environment,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)["datasets"][0]


def test_check_sh_merges_facts_into_the_json_array_row(tmp_path: Path) -> None:
    row = _run_check_sh(tmp_path, FUELPRICE.read_bytes(), ".json")

    assert row["newest_date"] == "2026-09-17"
    assert row["oldest_date"] == "2026-09-03"
    assert row["distinct_dates"] == 3
    assert row["rows_per_date"] == {"min": 2, "mean": 2.0, "max": 2}
    assert row["largest_gap_days"] == 7
    assert row["dimension_cardinality"] == {"series_type": 2}

    # Additive only: the pre-existing evidence is untouched.
    assert row["record_count"] == 6
    assert row["column_count"] == 10
    assert row["shape_basis"] == "json-array"
    assert row["first_row_hash"].startswith("shape-v1:")
    assert row["status"] in {
        "fresh",
        "aging",
        "stale",
        "discontinued",
        "degraded",
        "browser-dependent",
        "unreachable",
        "unknown",
        "unknown-freshness",
        "reference",
    }


def test_check_sh_merges_facts_into_the_csv_row(tmp_path: Path) -> None:
    body = b"date,station,value\n2026-09-01,A,1\n2026-09-02,A,2\n2026-09-02,B,3\n"
    row = _run_check_sh(tmp_path, body, ".csv")

    assert row["newest_date"] == "2026-09-02"
    assert row["oldest_date"] == "2026-09-01"
    assert row["distinct_dates"] == 2
    assert row["rows_per_date"] == {"min": 1, "mean": 1.5, "max": 2}
    assert row["largest_gap_days"] == 1
    assert row["dimension_cardinality"] == {"station": 2, "value": 3}
    assert row["shape_basis"] == "csv-headers"


def test_check_sh_reports_null_facts_without_a_date_column(tmp_path: Path) -> None:
    row = _run_check_sh(tmp_path, b'[{"name": "alpha"}, {"name": "beta"}]', ".json")

    assert row["newest_date"] is None
    assert row["oldest_date"] is None
    assert row["distinct_dates"] == 0
    assert row["rows_per_date"] is None
    assert row["largest_gap_days"] is None
    assert row["dimension_cardinality"] == {"name": 2}
