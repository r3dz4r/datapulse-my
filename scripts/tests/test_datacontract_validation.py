"""End-to-end contract-gate tests for canonical DataPulse JSON artifacts."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts" / "run_datacontract_validation.sh"


def run_validation(health: Path, manifest: Path) -> subprocess.CompletedProcess[str]:
    """Run the shell gate with explicit fixture paths."""
    return subprocess.run(
        ["bash", str(RUNNER)],
        cwd=ROOT,
        env={
            **os.environ,
            "DATAPULSE_HEALTH_PATH": str(health),
            "DATAPULSE_MANIFEST_PATH": str(manifest),
        },
        capture_output=True,
        check=False,
        text=True,
    )


def test_datacontract_validation_accepts_canonical_health_snapshot() -> None:
    """The committed canonical health and manifest inputs satisfy the ODCS gate."""
    result = run_validation(ROOT / "health/latest.json", ROOT / "datapulse.json")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "DataPulse contract validation: OK" in result.stdout


def test_datacontract_validation_rejects_missing_manifest_dataset_id(tmp_path: Path) -> None:
    """Removing a required manifest field is a release-blocking contract drift."""
    health = tmp_path / "health.json"
    manifest = tmp_path / "datapulse.json"
    shutil.copyfile(ROOT / "health/latest.json", health)
    payload = json.loads((ROOT / "datapulse.json").read_text(encoding="utf-8"))
    del payload["datasets"][0]["id"]
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    result = run_validation(health, manifest)

    assert result.returncode != 0
    assert "id" in result.stdout + result.stderr


def test_datacontract_validation_rejects_unknown_health_status(tmp_path: Path) -> None:
    """A status outside the stable taxonomy cannot pass the release gate."""
    health = tmp_path / "health.json"
    manifest = tmp_path / "datapulse.json"
    payload = json.loads((ROOT / "health/latest.json").read_text(encoding="utf-8"))
    payload["datasets"][0]["status"] = "made-up-status"
    health.write_text(json.dumps(payload), encoding="utf-8")
    shutil.copyfile(ROOT / "datapulse.json", manifest)

    result = run_validation(health, manifest)

    assert result.returncode != 0
    assert "status" in result.stdout + result.stderr
