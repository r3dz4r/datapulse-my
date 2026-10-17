"""Offline acceptance: complete rows, real consumers, and exact byte stability."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Iterator

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from scripts import gen_manifest_rows as generator
from scripts import gen_register_page
from scripts.health_policy import frequency_to_tier

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "datapulse.schema.json").read_text())
COMPLETE_FIELDS = {
    "id", "name", "source", "steward", "custodian", "attribution", "licence",
    "namespace", "vertical", "geo_coverage", "url", "record_source_url",
    "record_evidence_schema", "refresh_frequency", "freshness_policy",
    "expected_record_count", "health_report", "real_status", "verified_at",
    "attestation_ref", "methodology_version",
}


@pytest.fixture
def tmp_path() -> Iterator[Path]:
    """Keep this dispatch's temporary writes inside its worktree."""
    cache = ROOT / ".pytest_cache"
    cache.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="rowgen-test-", dir=cache) as directory:
        yield Path(directory)


def onboarding_entry(dataset_id: str = "fixture_new") -> dict:
    """Explicit reviewed judgements and provenance; no production onboarding."""
    return {
        "id": dataset_id,
        "licence": "Creative Commons Attribution 4.0",
        "custodian": "dosm",
        "steward": "Department of Statistics Malaysia",
        "attribution": "Data source: Department of Statistics Malaysia",
        "geo_coverage": "Malaysia",
        "namespace": "economy",
        "vertical": True,
        "expected_record_count": None,
        "freshness_policy": {
            "family": "data_gov_my_storage_dosm_gov_my",
            "content_date_field": "date",
            "interpretation": "observation_period",
            "discontinued_on_404": True,
            "reference_table": False,
            "notes": "Observation date; classify against publisher cadence. HTTP 404 discontinues.",
        },
        "real_status": "live",
        "verified_at": "2026-10-12",
        "attestation_ref": f"attestations/2026-10-12/{dataset_id}.json",
        "methodology_version": 3,
    }


def upstream_metadata(dataset_id: str = "fixture_new") -> dict:
    """Measured pageProps shape, with fixture URLs and title."""
    return {
        "id": dataset_id, "title": "Fixture Monthly Observations",
        "data_source": ["DOSM"], "frequency": "MONTHLY",
        "link_csv": f"https://storage.dosm.gov.my/fixture/{dataset_id}.csv",
        "link_parquet": f"https://storage.dosm.gov.my/fixture/{dataset_id}.parquet",
        "link_preview": f"https://storage.dosm.gov.my/fixture/{dataset_id}_latest.parquet",
        "link_editions": None,
        "fields": [{"name": "date", "title": "Date"}, {"name": "value", "title": "Value"}],
    }


def _stage(root: Path, entries: list[dict] | None = None, manifest: bytes | None = None) -> Path:
    (root / "config").mkdir()
    (root / "scripts").mkdir()
    for relative in ("datapulse.schema.json", "custodians.json", "scripts/probe-policy.json"):
        (root / relative).write_bytes((ROOT / relative).read_bytes())
    source = root / "config/manifest-onboarding.json"
    source.write_text(json.dumps({"schema": generator.SOURCE_SCHEMA, "datasets": entries or []}))
    (root / "datapulse.json").write_bytes(manifest or b'{"$schema":"fixture", "datasets": []}\n')
    metadata = root / "metadata.json"
    metadata.write_text(json.dumps({entry["id"]: upstream_metadata(entry["id"]) for entry in entries or []}))
    return metadata


def _generate(root: Path) -> list[dict]:
    generator.generate(root, metadata_path=root / "metadata.json")
    return json.loads((root / "datapulse.json").read_text())["datasets"]


def _cli(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts/gen_manifest_rows.py"), "--root", str(root),
         "--metadata", str(root / "metadata.json")],
        capture_output=True, text=True, check=False,
    )


def test_emits_complete_schema_valid_row_and_register_actions(tmp_path: Path) -> None:
    _stage(tmp_path, [onboarding_entry()])
    row, = _generate(tmp_path)
    assert set(row) == COMPLETE_FIELDS
    Draft202012Validator(SCHEMA, format_checker=FormatChecker()).validate(row_schema_manifest(row))
    assert row["name"] == "Fixture Monthly Observations"
    assert row["source"] == "DOSM via data.gov.my"
    assert row["url"] == row["record_source_url"] == upstream_metadata()["link_csv"]
    assert row["refresh_frequency"] == "monthly"
    assert row["health_report"] == "data/fixture_new.md"
    assert row["record_evidence_schema"] == "record-evidence/v1"
    for field in generator.JUDGEMENT_FIELDS | generator.OWNED_FIELDS:
        assert row[field] == onboarding_entry()[field]
    loaded, = gen_register_page._load_manifest(tmp_path)
    config = json.loads((ROOT / "config/register-page.json").read_text())
    html = gen_register_page._row_html(loaded, None, config, "https://mcp.data-pulse.my", None)
    assert 'data-dataset-id="fixture_new"' in html
    assert row["url"] in html
    assert "not observed" in html


def row_schema_manifest(row: dict) -> dict:
    """Wrap a row for the real manifest schema validator."""
    return {"$schema": "https://www.data-pulse.my/datapulse.schema.json", "datasets": [row]}


@pytest.mark.parametrize("frequency,expected,tier", [
    ("YEARLY", "annual", "slow"), ("ANNUAL", "annual", "slow"),
    ("MONTHLY", "monthly", "weekly-monthly"), ("QUARTERLY", "quarterly", "weekly-monthly"),
    ("DAILY", "daily", "daily"), ("WEEKLY", "weekly", "weekly-monthly"),
])
def test_publisher_cadences_are_probe_supported(frequency: str, expected: str, tier: str) -> None:
    metadata = upstream_metadata()
    metadata["frequency"] = frequency
    row = generator.emit_row(onboarding_entry(), metadata, SCHEMA)
    assert row["refresh_frequency"] == expected
    assert frequency_to_tier(row["refresh_frequency"], row["id"]) == tier


@pytest.mark.parametrize("frequency", [None, ""])
def test_only_explicit_reference_tables_may_have_no_cadence(frequency: str | None) -> None:
    metadata = upstream_metadata()
    metadata["frequency"] = frequency
    entry = onboarding_entry()
    with pytest.raises(generator.GenerationError, match="reference_table"):
        generator.emit_row(entry, metadata, SCHEMA)
    entry["freshness_policy"]["reference_table"] = True
    metadata["fields"] = [{"name": "code"}]
    row = generator.emit_row(entry, metadata, SCHEMA)
    assert row["refresh_frequency"] == "as-required"
    assert frequency_to_tier(row["refresh_frequency"]) == "slow"


def test_empty_source_preserves_all_440_real_rows_and_manifest_bytes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    original = (ROOT / "datapulse.json").read_bytes()
    _stage(tmp_path, manifest=original)
    monkeypatch.setattr(generator, "fetch_metadata", lambda _: pytest.fail("empty source must not fetch"))
    for _ in range(2):
        assert generator.generate(tmp_path) == 0
        assert (tmp_path / "datapulse.json").read_bytes() == original
    assert len(json.loads(original)["datasets"]) == 440


def test_append_preserves_every_real_row_raw_bytes_and_position(tmp_path: Path) -> None:
    original = (ROOT / "datapulse.json").read_bytes()
    _stage(tmp_path, [onboarding_entry("zz_fixture"), onboarding_entry("aa_fixture")], original)
    previous_rows = json.loads(original)["datasets"]
    rows = _generate(tmp_path)
    assert rows[:-2] == previous_rows
    assert [row["id"] for row in rows[-2:]] == ["aa_fixture", "zz_fixture"]
    before = original.decode()
    after = (tmp_path / "datapulse.json").read_text()
    _, before_spans = generator._row_spans(before)
    _, after_spans = generator._row_spans(after)
    for (start, end), (new_start, new_end) in zip(before_spans, after_spans):
        assert before[start:end] == after[new_start:new_end]
    first = (tmp_path / "datapulse.json").read_bytes()
    _generate(tmp_path)
    assert (tmp_path / "datapulse.json").read_bytes() == first


def test_selected_existing_row_updates_metadata_preserving_provenance_and_neighbours(tmp_path: Path) -> None:
    entry = onboarding_entry()
    row = generator.emit_row(entry, upstream_metadata(), SCHEMA)
    row.update({"attestation_ref": "attestations/2026-09-07/fixture_new.json", "methodology_version": 7,
                "real_status": "discontinued", "verified_at": "2026-09-07", "canonical_id": "fixture_new"})
    left = '{ "id" : "zzz_old", "attestation_ref":"opaque\\u002dlegacy", "methodology_version":99 }'
    right = '{"id":"aaa_old","expected_record_count":1e2}'
    original = ('{ "datasets" : [\n' + left + ',\n' + json.dumps(row) + ',\n' + right
                + '\n], "$schema" : "fixture" }\n').encode()
    # Existing provenance may be omitted entirely from the onboarding source.
    for field in generator.OWNED_FIELDS:
        entry.pop(field)
    _stage(tmp_path, [entry], original)
    metadata = upstream_metadata()
    metadata.update({"title": "Updated publisher title", "frequency": "YEARLY"})
    (tmp_path / "metadata.json").write_text(json.dumps({"fixture_new": metadata}))
    rows = _generate(tmp_path)
    selected = rows[1]
    assert [item["id"] for item in rows] == ["zzz_old", "fixture_new", "aaa_old"]
    assert selected["name"] == metadata["title"]
    assert selected["refresh_frequency"] == "annual"
    for field in generator.OWNED_FIELDS | {"canonical_id"}:
        assert selected[field] == row[field]
    after = (tmp_path / "datapulse.json").read_text()
    assert left in after and right in after
    assert after.startswith('{ "datasets" : [\n') and after.endswith('\n], "$schema" : "fixture" }\n')
    first = (tmp_path / "datapulse.json").read_bytes()
    _generate(tmp_path)
    assert (tmp_path / "datapulse.json").read_bytes() == first


def test_unchanged_selected_row_preserves_even_its_whitespace(tmp_path: Path) -> None:
    entry = onboarding_entry()
    row = generator.emit_row(entry, upstream_metadata(), SCHEMA)
    original = json.dumps(row_schema_manifest(row), indent=7, ensure_ascii=True).encode() + b"\r\n"
    _stage(tmp_path, [entry], original)
    _generate(tmp_path)
    assert (tmp_path / "datapulse.json").read_bytes() == original


@pytest.mark.parametrize("field", sorted(generator.JUDGEMENT_FIELDS | generator.OWNED_FIELDS))
def test_missing_explicit_fields_fail_before_any_write(tmp_path: Path, field: str) -> None:
    entry = onboarding_entry()
    entry.pop(field)
    _stage(tmp_path, [entry])
    before = (tmp_path / "datapulse.json").read_bytes()
    result = _cli(tmp_path)
    assert result.returncode == 1
    assert field in result.stderr
    assert (tmp_path / "datapulse.json").read_bytes() == before


@pytest.mark.parametrize("field,value", [
    ("namespace", "invented"), ("custodian", "unregistered"), ("licence", ""),
    ("vertical", "true"), ("expected_record_count", True), ("expected_record_count", -1),
    ("methodology_version", 0), ("verified_at", "2026-02-31"),
    ("real_status", "fresh"), ("attestation_ref", "invented.json"),
    ("id", "../escape"), ("url", "https://example.test/override.csv"),
])
def test_invalid_judgement_or_invented_override_fails_closed(tmp_path: Path, field: str, value: object) -> None:
    entry = onboarding_entry()
    entry[field] = value
    _stage(tmp_path, [entry])
    before = (tmp_path / "datapulse.json").read_bytes()
    result = _cli(tmp_path)
    assert result.returncode == 1
    assert result.stderr.startswith("gen_manifest_rows.py:")
    assert (tmp_path / "datapulse.json").read_bytes() == before


@pytest.mark.parametrize("field,value", [
    ("frequency", "FORTNIGHTLY"), ("id", "wrong_page"), ("title", None),
    ("data_source", []), ("fields", []), ("fields", [{"name": "other"}]),
    ("link_csv", None), ("link_csv", "https://storage.dosm.gov.my/fixture.parquet"),
    ("link_csv", "https://storage.dosm.gov.my/fixture.csv#preview"),
    ("link_csv", "https://user:password@example.test/fixture.csv"),
])
def test_bad_upstream_metadata_leaves_manifest_untouched(tmp_path: Path, field: str, value: object) -> None:
    _stage(tmp_path, [onboarding_entry("a_valid"), onboarding_entry("z_bad")])
    metadata = {key: upstream_metadata(key) for key in ("a_valid", "z_bad")}
    metadata["z_bad"][field] = value
    (tmp_path / "metadata.json").write_text(json.dumps(metadata))
    before = (tmp_path / "datapulse.json").read_bytes()
    result = _cli(tmp_path)
    assert result.returncode == 1
    assert "z_bad" in result.stderr
    assert (tmp_path / "datapulse.json").read_bytes() == before


def test_duplicate_onboarding_ids_are_rejected(tmp_path: Path) -> None:
    _stage(tmp_path, [onboarding_entry(), onboarding_entry()])
    with pytest.raises(generator.GenerationError, match="duplicate dataset id"):
        _generate(tmp_path)


def test_duplicate_manifest_ids_and_json_keys_are_rejected(tmp_path: Path) -> None:
    _stage(tmp_path, manifest=b'{"datasets":[{"id":"old"},{"id":"old"}]}')
    with pytest.raises(generator.GenerationError, match="duplicate dataset id"):
        _generate(tmp_path)
    (tmp_path / "datapulse.json").write_text('{"datasets":[],"datasets":[]}')
    with pytest.raises(generator.GenerationError, match="duplicate JSON key"):
        _generate(tmp_path)


def test_missing_cache_cannot_fall_back_to_network(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _stage(tmp_path, [onboarding_entry()])
    (tmp_path / "metadata.json").write_text("{}")
    monkeypatch.setattr(generator, "fetch_metadata", lambda _: pytest.fail("cache miss must fail closed"))
    with pytest.raises(generator.GenerationError, match="missing cached metadata"):
        _generate(tmp_path)


def test_non_direct_probe_adapter_is_rejected(tmp_path: Path) -> None:
    _stage(tmp_path, [onboarding_entry()])
    policy = {"defaults": {"adapter": "direct"}, "datasets": {"fixture_new": {"adapter": "browser"}}}
    (tmp_path / "scripts/probe-policy.json").write_text(json.dumps(policy))
    with pytest.raises(generator.GenerationError, match="direct probe adapter"):
        _generate(tmp_path)


def _page(metadata: dict) -> str:
    return '<html><script type="application/json" id="__NEXT_DATA__">' + json.dumps({
        "props": {"pageProps": metadata}, "other": {"link_csv": "https://example.test/decoy.csv"},
    }) + "</script></html>"


def test_reads_measured_next_data_structure_and_ignores_decoy_metadata() -> None:
    assert generator.parse_metadata(_page(upstream_metadata()), "fixture_new") == upstream_metadata()


@pytest.mark.parametrize("page", ["<html>no metadata</html>", _page(upstream_metadata()) * 2,
                                   _page({"id": "different"}),
                                   '<script id="__NEXT_DATA__">{"props":{}}</script>'])
def test_absent_ambiguous_or_wrong_page_metadata_is_rejected(page: str) -> None:
    with pytest.raises(generator.GenerationError):
        generator.parse_metadata(page, "fixture_new")


def test_live_fetch_path_uses_get_once_and_propagates_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _stage(tmp_path, [onboarding_entry()])
    calls: list[str] = []

    class Response:
        text = _page(upstream_metadata())

        def raise_for_status(self) -> None:
            return None

    def get(url: str, **kwargs: object) -> Response:
        assert kwargs["timeout"] == 30
        calls.append(url)
        return Response()

    monkeypatch.setattr(generator.requests, "get", get)
    generator.generate(tmp_path)
    assert calls == ["https://data.gov.my/data-catalogue/fixture_new"]
    before = (tmp_path / "datapulse.json").read_bytes()

    def failed_get(url: str, **kwargs: object) -> Response:
        calls.append(url)
        raise generator.requests.HTTPError("upstream HTTP 503")

    monkeypatch.setattr(generator.requests, "get", failed_get)
    with pytest.raises(generator.requests.HTTPError, match="503"):
        generator.generate(tmp_path)
    assert len(calls) == 2
    assert (tmp_path / "datapulse.json").read_bytes() == before


def test_cli_is_idempotent_and_preserves_manifest_mode(tmp_path: Path) -> None:
    _stage(tmp_path, [onboarding_entry()])
    path = tmp_path / "datapulse.json"
    path.chmod(0o640)
    result = _cli(tmp_path)
    assert result.returncode == 0, result.stderr
    assert "generated 1 selected rows" in result.stderr
    first = path.read_bytes()
    assert _cli(tmp_path).returncode == 0
    assert path.read_bytes() == first
    assert path.stat().st_mode & 0o777 == 0o640


def test_same_starting_inputs_emit_identical_bytes_across_process_hash_seeds(tmp_path: Path) -> None:
    _stage(tmp_path, [onboarding_entry()])
    path = tmp_path / "datapulse.json"
    original = path.read_bytes()
    outputs: list[bytes] = []
    for seed in ("1", "42"):
        path.write_bytes(original)
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/gen_manifest_rows.py"), "--root", str(tmp_path),
             "--metadata", str(tmp_path / "metadata.json")],
            env={**os.environ, "PYTHONHASHSEED": seed}, capture_output=True, text=True, check=False,
        )
        assert result.returncode == 0, result.stderr
        outputs.append(path.read_bytes())
    assert outputs[0] == outputs[1]


def test_generated_row_is_actually_scheduled_and_probed_by_check_sh(tmp_path: Path) -> None:
    _stage(tmp_path, [onboarding_entry()])
    row, = _generate(tmp_path)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_curl = fake_bin / "curl"
    fake_curl.write_text("""#!/usr/bin/env bash
set -euo pipefail
output_path=""
headers_path=""
request_url=""
while (( $# > 0 )); do
  case "$1" in
    --output) output_path="$2"; shift 2 ;;
    --dump-header) headers_path="$2"; shift 2 ;;
    --max-time|--write-out|--header) shift 2 ;;
    http*) request_url="$1"; shift ;;
    *) shift ;;
  esac
done
if [[ "$output_path" == "-" ]]; then
  exit 0
fi
[[ "$request_url" == https://storage.dosm.gov.my/fixture/fixture_new.csv ]]
printf 'date,value\\n2026-10-01,42\\n2026-10-02,43\\n' > "$output_path"
printf 'HTTP/1.1 200 OK\\r\\nLast-Modified: Mon, 12 Oct 2026 00:00:00 GMT\\r\\n\\r\\n' > "$headers_path"
printf '200'
""")
    fake_curl.chmod(0o755)
    environment = os.environ.copy()
    environment.update({"PATH": f"{fake_bin}:{environment['PATH']}", "TMPDIR": str(tmp_path),
                        "DATAPULSE_PROBE_POLICY": str(tmp_path / "scripts/probe-policy.json"),
                        "DATAPULSE_CHECKED_AT": "2026-10-12T00:00:00Z"})
    completed = subprocess.run(
        ["bash", str(ROOT / "scripts/check.sh"), "--due", "datapulse.json"],
        cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=45, check=False,
    )
    assert completed.returncode == 0, completed.stderr
    result, = json.loads(completed.stdout)["datasets"]
    assert result["dataset_id"] == row["id"]
    assert result["http_status"] == 200
    assert result["url"] == row["url"]
    assert result["record_count"] == 2


def test_committed_source_enrolls_no_real_datasets() -> None:
    source = json.loads((ROOT / "config/manifest-onboarding.json").read_text())
    assert source["schema"] == generator.SOURCE_SCHEMA
    assert source["datasets"] == []
