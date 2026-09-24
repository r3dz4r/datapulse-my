"""Regression coverage for bounded-memory history readers."""

from __future__ import annotations

import json
import random
import re
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BASELINE_COMMIT = "eab612515"
TIME = Path("/usr/bin/time")


def _write_inputs(directory: Path, rows: int) -> tuple[Path, Path, Path]:
    """Make repeatable, wide-enough input that exposes total-history retention."""
    randomizer = random.Random(20260924)
    dataset_count = 250
    manifest = {"datasets": [{"id": f"dataset-{index:03d}", "name": f"Dataset {index:03d}"} for index in range(dataset_count)]}
    latest = {
        "checked_at": "2026-08-31T23:59:00Z",
        "datasets": [{"dataset_id": item["id"], "record_count": 100, "column_count": 4} for item in manifest["datasets"]],
    }
    history = directory / "history.jsonl"
    with history.open("w", encoding="utf-8") as stream:
        for index in range(rows):
            dataset_id = f"dataset-{index % dataset_count:03d}"
            day = 1 + (index // dataset_count) % 30
            second = index // (dataset_count * 30)
            row = {
                "dataset_id": dataset_id,
                "observed_at": f"2026-08-{day:02d}T12:{second % 60:02d}:{(index // 60) % 60:02d}Z",
                "cycle": f"2026-08-{day:02d}T20:{second % 60:02d}",
                "status": "fresh",
                "probe_outcome": "success",
                "record_count": 100 + randomizer.randrange(3),
                "column_count": 4,
                "shape_hash": "shape-v1:fixture",
            }
            stream.write(json.dumps(row, separators=(",", ":")) + "\n")
    manifest_path, latest_path = directory / "manifest.json", directory / "latest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    latest_path.write_text(json.dumps(latest), encoding="utf-8")
    return history, manifest_path, latest_path


def _baseline_scripts(directory: Path) -> Path:
    scripts = directory / "scripts"
    scripts.mkdir(parents=True)
    for name in ("gen_health_history.py", "gen_drift.py"):
        source = subprocess.run(
            ["git", "show", f"{BASELINE_COMMIT}:scripts/{name}"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        ).stdout
        (scripts / name).write_bytes(source)
    for name in ("artifact_modes.py", "gen_anomaly.py"):
        shutil.copy2(ROOT / "scripts" / name, scripts / name)
    return scripts


def _run(command: list[str], directory: Path) -> tuple[bytes, int]:
    timing = directory / "time.txt"
    completed = subprocess.run(
        [str(TIME), "-v", "-o", str(timing), *command],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr.decode()
    match = re.search(r"Maximum resident set size \(kbytes\): (\d+)", timing.read_text())
    assert match, timing.read_text()
    return completed.stdout, int(match.group(1))


def _health_command(script: Path, history: Path, manifest: Path, latest: Path) -> list[str]:
    return ["python3", str(script), "--history", str(history), "--manifest", str(manifest), "--snapshot", str(latest), "--cycle", "2026-08-31T23:59"]


def _drift_command(script: Path, history: Path, manifest: Path, latest: Path, output: Path) -> list[str]:
    return ["python3", str(script), "--history", str(history), "--manifest", str(manifest), "--latest", str(latest), "--output", str(output)]


def test_history_readers_are_bounded_and_preserve_baseline(tmp_path: Path) -> None:
    assert TIME.exists(), "/usr/bin/time is required for RSS measurement"
    baseline = _baseline_scripts(tmp_path / "baseline")
    measurements: dict[str, list[int]] = {"health": [], "drift": []}
    golden: dict[str, bytes] = {}

    for size in (50_000, 200_000):
        case = tmp_path / str(size)
        case.mkdir()
        history, manifest, latest = _write_inputs(case, size)

        health_output = case / "health-output.jsonl"
        shutil.copy2(history, health_output)
        health_command = _health_command(ROOT / "scripts/gen_health_history.py", health_output, manifest, latest)
        _, rss = _run(health_command, case)
        measurements["health"].append(rss)
        repeat_output = case / "health-repeat.jsonl"
        shutil.copy2(history, repeat_output)
        repeat = health_command.copy()
        repeat[repeat.index("--history") + 1] = str(repeat_output)
        _run(repeat, case)
        assert health_output.read_bytes() == repeat_output.read_bytes()

        drift_output = case / "drift.json"
        drift_command = _drift_command(ROOT / "scripts/gen_drift.py", history, manifest, latest, drift_output)
        _, rss = _run(drift_command, case)
        measurements["drift"].append(rss)
        repeat_output = case / "drift-repeat.json"
        repeat = _drift_command(ROOT / "scripts/gen_drift.py", history, manifest, latest, repeat_output)
        _run(repeat, case)
        assert drift_output.read_bytes() == repeat_output.read_bytes()

        if size == 50_000:
            baseline_health = case / "baseline-health.jsonl"
            shutil.copy2(history, baseline_health)
            command = _health_command(baseline / "gen_health_history.py", baseline_health, manifest, latest)
            _run(command, case)
            golden["health"] = baseline_health.read_bytes()
            baseline_drift = case / "baseline-drift.json"
            _run(_drift_command(baseline / "gen_drift.py", history, manifest, latest, baseline_drift), case)
            golden["drift"] = baseline_drift.read_bytes()
            assert health_output.read_bytes() == golden["health"]
            assert drift_output.read_bytes() == golden["drift"]

    print("peak RSS (kB): " + ", ".join(f"{name} 50k={values[0]} 200k={values[1]}" for name, values in measurements.items()))
    for values in measurements.values():
        assert values[1] < 2 * values[0]
