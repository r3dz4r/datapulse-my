"""Regression coverage for the health unit's literal compact invocation."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PRE_CHANGE_COMMIT = "28bbc97a1"
TIME = Path("/usr/bin/time")
CYCLE = "2026-09-24T06:00"


def _write_inputs(directory: Path, rows: int) -> None:
    """Create the files the unit finds through its default relative paths."""
    health = directory / "health"
    health.mkdir(parents=True)
    datasets = [
        {"id": f"dataset-{index:03d}", "name": f"Dataset {index:03d}"}
        for index in range(250)
    ]
    (directory / "datapulse.json").write_text(
        json.dumps({"datasets": datasets}), encoding="utf-8"
    )
    (health / "latest.json").write_text(
        json.dumps(
            {
                "checked_at": "2026-09-24T06:00:00Z",
                "datasets": [
                    {
                        "dataset_id": row["id"],
                        "status": "fresh",
                        "http_status": 200,
                        "record_count": 100,
                        "column_count": 4,
                    }
                    for row in datasets
                ],
            }
        ),
        encoding="utf-8",
    )
    with (health / "history.jsonl").open("w", encoding="utf-8") as stream:
        for index in range(rows):
            stream.write(
                json.dumps(
                    {
                        "dataset_id": f"dataset-{index % len(datasets):03d}",
                        "observed_at": "2026-09-24T06:00:00Z",
                        "cycle": f"fixture-{index:06d}",
                        "status": "fresh",
                        "probe_outcome": "success",
                        "record_count": 100,
                        "column_count": 4,
                        "shape_hash": "shape-v1:fixture",
                    },
                    separators=(",", ":"),
                )
                + "\n"
            )


def _stage_script(directory: Path, name: str) -> Path:
    scripts = directory / "scripts"
    scripts.mkdir(exist_ok=True)
    script = scripts / name
    shutil.copy2(ROOT / "scripts" / name, script)
    shutil.copy2(ROOT / "scripts" / "artifact_modes.py", scripts / "artifact_modes.py")
    if name == "gen_drift.py":
        shutil.copy2(ROOT / "scripts" / "gen_anomaly.py", scripts / "gen_anomaly.py")
    return script


def _baseline_script(directory: Path) -> Path:
    scripts = directory / "scripts"
    scripts.mkdir(exist_ok=True)
    source = subprocess.run(
        ["git", "show", f"{PRE_CHANGE_COMMIT}:scripts/gen_health_history.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    script = scripts / "gen_health_history.py"
    script.write_bytes(source)
    shutil.copy2(ROOT / "scripts" / "artifact_modes.py", scripts / "artifact_modes.py")
    return script


def _run(command: list[str], directory: Path) -> int:
    timing = directory / "time.txt"
    environment = os.environ | {"DATAPULSE_ARCHIVES_DIR": str(directory / "archives")}
    completed = subprocess.run(
        [str(TIME), "-v", "-o", str(timing), *command],
        cwd=directory,
        env=environment,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr.decode()
    match = re.search(r"Maximum resident set size \(kbytes\): (\d+)", timing.read_text())
    assert match, timing.read_text()
    return int(match.group(1))


def _outputs(directory: Path) -> tuple[bytes, bytes, bytes]:
    health = directory / "health"
    return (
        (health / "history.jsonl").read_bytes(),
        (health / "history_daily.json").read_bytes(),
        (health / "drift.json").read_bytes(),
    )


def test_compact_defaults_are_bounded_and_match_prechange_output(tmp_path: Path) -> None:
    assert TIME.exists(), "/usr/bin/time is required for RSS measurement"
    compact_measurements: list[int] = []
    drift_measurements: list[int] = []
    golden: tuple[bytes, bytes, bytes] | None = None

    for size in (50_000, 200_000):
        seed = tmp_path / f"seed-{size}"
        _write_inputs(seed, size)
        candidate = tmp_path / f"candidate-{size}"
        shutil.copytree(seed, candidate)
        history_script = _stage_script(candidate, "gen_health_history.py")
        drift_script = _stage_script(candidate, "gen_drift.py")
        compact_measurements.append(
            _run(["python3", str(history_script), "--cycle", CYCLE, "--compact"], candidate)
        )
        drift_measurements.append(_run(["python3", str(drift_script)], candidate))
        first = _outputs(candidate)
        _run(["python3", str(history_script), "--cycle", CYCLE, "--compact"], candidate)
        _run(["python3", str(drift_script)], candidate)
        assert _outputs(candidate) == first

        if size == 50_000:
            baseline = tmp_path / "baseline"
            shutil.copytree(seed, baseline)
            baseline_script = _baseline_script(baseline)
            baseline_drift_script = _stage_script(baseline, "gen_drift.py")
            _run(["python3", str(baseline_script), "--cycle", CYCLE, "--compact"], baseline)
            _run(["python3", str(baseline_drift_script)], baseline)
            golden = _outputs(baseline)
            assert first == golden

    print(
        "peak RSS (kB): "
        f"compact 50k={compact_measurements[0]} 200k={compact_measurements[1]}; "
        f"drift 50k={drift_measurements[0]} 200k={drift_measurements[1]}"
    )
    assert compact_measurements[1] < 2 * compact_measurements[0]
    assert drift_measurements[1] < 2 * drift_measurements[0]
