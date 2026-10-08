#!/usr/bin/env python3
"""Offline onboarding preserves measurements and rejects incoherent snapshots."""

from __future__ import annotations

import copy
import json
import shutil
import socket
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.gen_health_trust_summary import GenerationError, generate
from scripts.gen_readme import STATUS_LABELS
from scripts.validate_at_runtime import validate_health


def _fixture(root: Path) -> tuple[Path, dict]:
    root.mkdir(parents=True, exist_ok=True)
    (root / "health").mkdir(exist_ok=True)
    for name in ("datapulse.schema.json", "health.schema.json"):
        shutil.copy2(ROOT / name, root / name)
    manifest = json.loads((ROOT / "datapulse.json").read_text())
    rows = []
    for dataset_id in ("alpha", "new"):
        row = copy.deepcopy(manifest["datasets"][0])
        row.update(id=dataset_id, url=f"https://example.invalid/{dataset_id}", health_report=f"data/{dataset_id}.md")
        rows.append(row)
    manifest["datasets"] = rows
    (root / "datapulse.json").write_text(json.dumps(manifest))
    snapshot = {
        "schema": "datapulse/v0.4/dataset-health",
        "checked_at": "2026-10-07T08:10:43Z",
        "_trust_summary": {
            "datasets_total": 1,
            "by_status": {key: int(key == "fresh") for key, _ in STATUS_LABELS},
            "checked_at": "2026-10-07T08:10:43Z",
            "pipeline_heartbeat_at": "2026-10-07T08:14:13Z",
        },
        "datasets": [{"dataset_id": "alpha", "url": "https://example.invalid/alpha", "status": "fresh", "last_checked": "2026-10-03T10:36:37Z", "record_count": 961, "nested": {"evidence": [1, None]}}],
    }
    path = root / "health/latest.json"
    path.write_text(json.dumps(snapshot) + "\n")
    return path, snapshot


def test_added_dataset_derives_total_and_status_counts_without_network(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path, snapshot = _fixture(tmp_path)

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("onboarding attempted network access")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    assert generate(tmp_path)
    result = json.loads(path.read_text())
    assert result["_trust_summary"]["datasets_total"] == 2
    counts = result["_trust_summary"]["by_status"]
    assert sum(counts.values()) == 2
    assert all(count >= 0 for count in counts.values())
    assert counts["fresh"] == counts["unknown_freshness"] == 1
    assert result["datasets"][1] == {"dataset_id": "new", "url": "https://example.invalid/new", "last_checked": None, "status": "unknown-freshness", "message": "Not probed; provisional onboarding status."}
    assert validate_health(path)[0]
    assert result["checked_at"] == snapshot["checked_at"]


@pytest.mark.parametrize("key,status", STATUS_LABELS)
def test_existing_probed_status_and_all_data_survive_untouched(tmp_path: Path, key: str, status: str) -> None:
    path, snapshot = _fixture(tmp_path)
    snapshot["datasets"][0]["status"] = status
    snapshot["_trust_summary"]["by_status"] = {name: int(name == key) for name, _ in STATUS_LABELS}
    path.write_text(json.dumps(snapshot))
    before = copy.deepcopy(snapshot)
    generate(tmp_path)
    result = json.loads(path.read_text())
    assert result["datasets"][0] == before["datasets"][0]
    assert {k: v for k, v in result["_trust_summary"].items() if k not in {"datasets_total", "by_status"}} == {k: v for k, v in before["_trust_summary"].items() if k not in {"datasets_total", "by_status"}}


def test_snapshot_only_record_is_retained_but_excluded_from_manifest_total(tmp_path: Path) -> None:
    path, snapshot = _fixture(tmp_path)
    orphan = {"dataset_id": "retired", "url": "https://example.invalid/retired", "last_checked": "2026-10-01T00:00:00Z", "status": "stale", "record_count": 42}
    snapshot["datasets"].append(orphan)
    snapshot["_trust_summary"]["datasets_total"] = 2
    snapshot["_trust_summary"]["by_status"]["stale"] = 1
    path.write_text(json.dumps(snapshot))
    generate(tmp_path)
    result = json.loads(path.read_text())
    assert result["datasets"][:2] == snapshot["datasets"]
    assert result["_trust_summary"]["datasets_total"] == 2
    assert result["_trust_summary"]["by_status"]["stale"] == 0
    assert sum(result["_trust_summary"]["by_status"].values()) == 2
    assert not generate(tmp_path)


def test_same_inputs_and_repeated_runs_produce_identical_bytes(tmp_path: Path) -> None:
    path, _ = _fixture(tmp_path)
    original = path.read_bytes()
    generate(tmp_path)
    first = path.read_bytes()
    path.write_bytes(original)
    generate(tmp_path)
    assert path.read_bytes() == first
    assert not generate(tmp_path)
    assert path.read_bytes() == first


@pytest.mark.parametrize("field,value", [("datasets_total", 99), ("datasets_total", True), ("by_status", {"fresh": -1}), ("by_status", {"fresh": 2}), ("by_status", {"fresh": True}), ("by_status", {"invented": 1})])
def test_genuinely_incoherent_summary_is_rejected_without_writing(tmp_path: Path, field: str, value: object) -> None:
    path, snapshot = _fixture(tmp_path)
    snapshot["_trust_summary"][field] = value
    path.write_text(json.dumps(snapshot))
    before = path.read_bytes()
    with pytest.raises(GenerationError):
        generate(tmp_path)
    assert path.read_bytes() == before


def test_duplicate_probe_is_rejected_without_deleting_data(tmp_path: Path) -> None:
    path, snapshot = _fixture(tmp_path)
    snapshot["datasets"].append(copy.deepcopy(snapshot["datasets"][0]))
    path.write_text(json.dumps(snapshot))
    before = path.read_bytes()
    with pytest.raises(GenerationError, match="duplicate"):
        generate(tmp_path)
    assert path.read_bytes() == before


def test_cli_and_release_order(tmp_path: Path) -> None:
    path, _ = _fixture(tmp_path)
    result = subprocess.run([sys.executable, str(ROOT / "scripts/gen_health_trust_summary.py"), "--root", str(tmp_path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(path.read_text())["_trust_summary"]["datasets_total"] == 2
    listed = subprocess.run(["bash", "scripts/generate.sh", "release-build", "--list"], cwd=ROOT, capture_output=True, text=True)
    assert listed.returncode == 0, listed.stderr
    assert listed.stdout.index("gen_health_trust_summary.py") < listed.stdout.index("gen_readme.py")


@pytest.mark.parametrize("status,message", [("fresh", "Not probed; provisional onboarding status."), ("unknown-freshness", "HTTP 200")])
def test_schema_allows_null_probe_time_only_for_explicit_placeholder(tmp_path: Path, status: str, message: str) -> None:
    path, snapshot = _fixture(tmp_path)
    snapshot["datasets"][0].update(last_checked=None, status=status, message=message)
    path.write_text(json.dumps(snapshot))
    valid, errors = validate_health(path)
    assert not valid
    assert errors


def test_invalid_manifest_is_rejected_before_snapshot_write(tmp_path: Path) -> None:
    path, _ = _fixture(tmp_path)
    manifest_path = tmp_path / "datapulse.json"
    manifest = json.loads(manifest_path.read_text())
    del manifest["datasets"][1]["url"]
    manifest_path.write_text(json.dumps(manifest))
    before = path.read_bytes()
    with pytest.raises(GenerationError, match="url"):
        generate(tmp_path)
    assert path.read_bytes() == before
