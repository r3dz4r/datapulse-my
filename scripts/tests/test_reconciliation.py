"""Deterministic tests for conservative cross-source reconciliation."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("gen_reconciliation", ROOT / "scripts/gen_reconciliation.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def entry(dataset_id, name, url, custodian="dosm", cadence="monthly"):
    return {"id": dataset_id, "name": name, "url": url, "source": "Fixture portal", "custodian": custodian, "refresh_frequency": cadence}


def health(dataset_id, count=100, content_date="2026-08-01", status="fresh"):
    return {"dataset_id": dataset_id, "record_count": count, "record_count_estimated": False, "content_freshness_date": content_date, "freshness_signal_source": "content_date_parse", "status": status}


def snapshot(*rows):
    return {"checked_at": "2026-08-15T00:00:00Z", "datasets": list(rows)}


def seeds(*groups):
    return {"schema": MODULE.SEED_SCHEMA, "groups": list(groups)}


def seed(relationship="equivalent", policy="strict"):
    return {"key": "reviewed-pair", "logical_name": "Reviewed Pair", "members": ["alpha", "beta"], "relationship": relationship, "rationale": "Reviewed synthetic relationship.", "comparison": {"record_count_policy": policy, "record_count_tolerance_pct": 5.0, "content_date_tolerance_days": 2}}


def test_exact_url_group_is_strict_and_deterministic():
    result = MODULE.generate({"datasets": [entry("beta", "Beta", "https://example.test/data.csv#fragment"), entry("alpha", "Alpha", "https://EXAMPLE.test/data.csv")]}, snapshot(health("alpha"), health("beta", 101)), seeds())
    group = result["groups"][0]
    assert result["summary"]["groups_total"] == 1
    assert group["grouping_method"] == "exact_url"
    assert [row["id"] for row in group["members"]] == ["alpha", "beta"]
    assert group["verdict"] == "discrepancy"
    assert group["comparisons"][0]["record_count_within_tolerance"] is False


def test_guarded_name_group_reports_count_delta_as_context():
    manifest = {"datasets": [entry("alpha", "OpenDOSM Annual Population by State", "https://storage.dosm.gov.my/population.csv", cadence="annual"), entry("beta", "Annual Population by State", "https://api.data.gov.my/data-catalogue?id=population_state", cadence="annual")]}
    result = MODULE.generate(manifest, snapshot(health("alpha"), health("beta", 140)), seeds())
    group = result["groups"][0]
    assert group["grouping_method"] == "semantic_title"
    assert group["verdict"] == "agree"
    assert group["comparisons"][0]["record_count_delta_pct"] == 28.571
    assert group["comparisons"][0]["record_count_within_tolerance"] is None


def test_seed_override_uses_reviewed_strict_policy():
    result = MODULE.generate({"datasets": [entry("alpha", "Alpha", "https://example.test/a.csv"), entry("beta", "Beta", "https://other.test/b.csv")]}, snapshot(health("alpha"), health("beta", 120)), seeds(seed()))
    group = result["groups"][0]
    assert group["group_key"] == "seed:reviewed-pair"
    assert group["confidence"] == "reviewed"
    assert group["verdict"] == "discrepancy"
    assert group["requires_human_review"] is True


def test_national_and_state_titles_do_not_auto_group():
    result = MODULE.generate({"datasets": [entry("deaths", "Annual Deaths", "https://api.data.gov.my/data-catalogue?id=deaths", cadence="annual"), entry("deaths_state", "Annual Deaths by State", "https://storage.dosm.gov.my/death_state.csv", cadence="annual")]}, snapshot(health("deaths", 25), health("deaths_state", 390)), seeds())
    assert result["groups"] == []
    assert result["summary"]["datasets_single_source"] == 2


def test_reviewed_different_granularity_is_context_not_issue():
    result = MODULE.generate({"datasets": [entry("alpha", "Annual Deaths", "https://example.test/deaths.csv"), entry("beta", "Annual Deaths by State", "https://other.test/deaths.csv")]}, snapshot(health("alpha", 25), health("beta", 390)), seeds(seed("different_granularity", "context_only")))
    group = result["groups"][0]
    assert group["verdict"] == "different_granularity"
    assert group["requires_human_review"] is False
    assert group["comparisons"][0]["record_count_delta"] == 365


def test_single_source_is_counted_but_not_emitted_as_group():
    result = MODULE.generate({"datasets": [entry("only", "Only Dataset", "https://example.test/only.csv")]}, snapshot(health("only")), seeds())
    assert result["groups"] == []
    assert result["summary"]["datasets_single_source"] == 1
    assert set(result["summary"]["by_verdict"]) == set(MODULE.VERDICTS)


def test_cli_writes_complete_artifact(tmp_path: Path):
    manifest, health_file, seed_file, output = (tmp_path / name for name in ("datapulse.json", "latest.json", "reconciliation_groups.json", "health/reconciliation.json"))
    manifest.write_text(json.dumps({"datasets": [entry("alpha", "Alpha", "https://example.test/data.csv"), entry("beta", "Beta", "https://example.test/data.csv")] }), encoding="utf-8")
    health_file.write_text(json.dumps(snapshot(health("alpha"), health("beta"))), encoding="utf-8")
    seed_file.write_text(json.dumps(seeds()), encoding="utf-8")
    result = subprocess.run(["python3", str(ROOT / "scripts/gen_reconciliation.py"), "--manifest", str(manifest), "--health", str(health_file), "--seeds", str(seed_file), "--output", str(output)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema"] == "datapulse/v1/dataset-reconciliation"
    assert payload["generated_at"] == "2026-08-15T00:00:00Z"
    assert payload["summary"]["groups_total"] == 1
