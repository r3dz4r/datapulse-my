"""Tests for deterministic per-dataset probe-window generation."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/gen_probe_window.py"


def write_fixture(
    tmp_path: Path,
    *,
    reference_at: str = "2026-09-26T12:00:00Z",
    history: list[dict[str, str]] | None = None,
    dataset_ids: list[str] | None = None,
) -> tuple[Path, Path, Path, Path]:
    health = tmp_path / "latest.json"
    history_path = tmp_path / "history.jsonl"
    manifest = tmp_path / "datapulse.json"
    output = tmp_path / "probe-window.json"
    health.write_text(json.dumps({"checked_at": reference_at, "datasets": []}), encoding="utf-8")
    history_path.write_text(
        "" if history is None else "\n".join(json.dumps(row) for row in history) + "\n",
        encoding="utf-8",
    )
    manifest.write_text(
        json.dumps({"datasets": [{"id": dataset_id} for dataset_id in (dataset_ids or [])]}),
        encoding="utf-8",
    )
    return history_path, health, manifest, output


def run_generator(
    history: Path, health: Path, manifest: Path, output: Path
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--history",
            str(history),
            "--health",
            str(health),
            "--manifest",
            str(manifest),
            "--out",
            str(output),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def test_fixture_history_produces_exact_counts_for_both_windows(tmp_path: Path) -> None:
    history, health, manifest, output = write_fixture(
        tmp_path,
        history=[
            {"dataset_id": "fuelprice", "observed_at": "2026-09-12T12:00:00Z"},
            {"dataset_id": "fuelprice", "observed_at": "2026-09-24T11:59:59Z"},
            {"dataset_id": "fuelprice", "observed_at": "2026-09-25T12:00:00Z"},
            {"dataset_id": "fuelprice", "observed_at": "2026-09-26T12:00:00Z"},
            {"dataset_id": "fuelprice", "observed_at": "2026-09-12T11:59:59Z"},
        ],
        dataset_ids=["fuelprice"],
    )

    result = run_generator(history, health, manifest, output)

    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text(encoding="utf-8"))["counts"]["fuelprice"] == {
        "probe_count_14d": 4,
        "probe_count_24h": 2,
    }


def test_dataset_without_observations_in_window_is_zeroed(tmp_path: Path) -> None:
    history, health, manifest, output = write_fixture(
        tmp_path,
        history=[
            {"dataset_id": "old", "observed_at": "2026-08-01T00:00:00Z"},
        ],
        dataset_ids=["old", "never-probed"],
    )

    result = run_generator(history, health, manifest, output)

    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text(encoding="utf-8"))["counts"] == {
        "never-probed": {"probe_count_14d": 0, "probe_count_24h": 0},
        "old": {"probe_count_14d": 0, "probe_count_24h": 0},
    }


def test_absent_history_skips_and_leaves_existing_artifact_untouched(tmp_path: Path) -> None:
    history, health, manifest, output = write_fixture(
        tmp_path, dataset_ids=["fuelprice"]
    )
    history.unlink()
    sentinel = b'{"sentinel":true}\n'
    output.write_bytes(sentinel)

    result = run_generator(history, health, manifest, output)

    assert result.returncode == 0
    assert "history input" in result.stderr
    assert "committed artifact" in result.stderr
    assert output.read_bytes() == sentinel


def test_identical_inputs_produce_byte_identical_outputs(tmp_path: Path) -> None:
    history, health, manifest, output = write_fixture(
        tmp_path,
        history=[
            {"dataset_id": "zeta", "observed_at": "2026-09-25T00:00:00Z"},
            {"dataset_id": "alpha", "observed_at": "2026-09-20T00:00:00Z"},
        ],
        dataset_ids=["zeta", "alpha"],
    )
    first = run_generator(history, health, manifest, output)
    first_hash = hashlib.sha256(output.read_bytes()).hexdigest()
    second = run_generator(history, health, manifest, output)
    second_hash = hashlib.sha256(output.read_bytes()).hexdigest()

    assert first.returncode == second.returncode == 0
    assert first_hash == second_hash
    assert output.read_bytes().endswith(b"\n")


def test_reference_at_is_copied_verbatim_from_health_snapshot(tmp_path: Path) -> None:
    reference_at = "2026-09-26T20:00:00+08:00"
    history, health, manifest, output = write_fixture(
        tmp_path,
        reference_at=reference_at,
        history=[{"dataset_id": "fuelprice", "observed_at": "2026-09-26T12:00:00Z"}],
        dataset_ids=["fuelprice"],
    )

    result = run_generator(history, health, manifest, output)

    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text(encoding="utf-8"))["reference_at"] == reference_at


def test_output_matches_pinned_structure_and_sorted_count_keys(tmp_path: Path) -> None:
    history, health, manifest, output = write_fixture(
        tmp_path,
        history=[{"dataset_id": "zeta", "observed_at": "2026-09-26T00:00:00Z"}],
        dataset_ids=["zeta", "alpha"],
    )

    result = run_generator(history, health, manifest, output)
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert result.returncode == 0, result.stderr
    assert list(payload) == ["schema", "reference_at", "window_days", "counts"]
    assert payload["schema"] == "datapulse/v1/probe-window-counts"
    assert payload["window_days"] == [14, 1]
    assert list(payload["counts"]) == ["alpha", "zeta"]
    assert set(payload["counts"]["alpha"]) == {"probe_count_14d", "probe_count_24h"}
    assert all(isinstance(value, int) and value >= 0 for value in payload["counts"]["zeta"].values())
