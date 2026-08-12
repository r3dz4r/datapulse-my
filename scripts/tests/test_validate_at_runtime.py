"""Tests for the runtime probe-boundary validator."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from scripts.validate_at_runtime import (
    validate_health,
    validate_all,
    validate_manifest,
)


ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT


def test_validate_manifest_valid() -> None:
    ok, errors = validate_manifest(ROOT / "datapulse.json")

    assert ok
    assert errors == []


def test_validate_manifest_invalid(tmp_path: Path) -> None:
    manifest = json.loads((ROOT / "datapulse.json").read_text(encoding="utf-8"))
    del manifest["datasets"][0]["name"]
    manifest["datasets"][1]["url"] = 42
    path = tmp_path / "datapulse.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    ok, errors = validate_manifest(path)

    assert not ok
    assert any("name" in error for error in errors)
    assert any("url" in error for error in errors)


def test_validate_health_valid() -> None:
    ok, errors = validate_health(
        ROOT / "health/latest.json", manifest=ROOT / "datapulse.json"
    )

    assert ok
    assert errors == []


def test_validate_health_stale_dataset_ref(tmp_path: Path) -> None:
    health = json.loads((ROOT / "health/latest.json").read_text(encoding="utf-8"))
    health["datasets"][0]["dataset_id"] = "not-in-manifest"
    path = tmp_path / "latest.json"
    path.write_text(json.dumps(health), encoding="utf-8")

    ok, errors = validate_health(path, manifest=ROOT / "datapulse.json")

    assert not ok
    assert any("not-in-manifest" in error and "manifest" in error for error in errors)


def test_pipeline_calls_validator() -> None:
    pipeline = Path("/home/redza/dotfiles/scripts/datapulse-pipeline.sh")
    result = subprocess.run(
        ["bash", "-n", str(pipeline)], capture_output=True, text=True, check=False
    )

    assert result.returncode == 0, result.stderr
    source = pipeline.read_text(encoding="utf-8")
    assert "scripts/validate_at_runtime.py" in source
    assert "--input" in source
    assert "--schemas" in source


def test_validate_all_accepts_health_directory() -> None:
    ok, errors = validate_all(ROOT / "health", SCHEMAS / "schemas")

    assert ok
    assert errors == []


def test_validate_all_rejects_bad_manifest(tmp_path: Path) -> None:
    shutil.copytree(ROOT / "health", tmp_path / "health")
    shutil.copy2(ROOT / "datapulse.json", tmp_path / "datapulse.json")
    shutil.copy2(ROOT / "scripts/probe-policy.json", tmp_path / "probe-policy.json")
    manifest = json.loads((tmp_path / "datapulse.json").read_text(encoding="utf-8"))
    manifest["datasets"][0].pop("name")
    (tmp_path / "datapulse.json").write_text(json.dumps(manifest), encoding="utf-8")

    ok, errors = validate_all(tmp_path, tmp_path / "schemas")

    assert not ok
    assert any("datapulse.json" in error and "name" in error for error in errors)
