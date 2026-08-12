"""Dataset-level delta ledger and catalog snapshot compatibility tests."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DELTA_GENERATOR = ROOT / "scripts/gen_dataset_deltas.py"
SNAPSHOT_GENERATOR = ROOT / "scripts/gen_catalog_snapshot.py"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _history_row(
    dataset_id: str,
    cycle: str,
    *,
    status: str = "fresh",
    record_count: int | None = 100,
    url: str | None = None,
    shape_hash: str | None = "shape-v1:old",
    probe_outcome: str = "success",
    estimated: bool = False,
) -> dict:
    return {
        "dataset_id": dataset_id,
        "name": f"{dataset_id.title()} Dataset",
        "observed_at": f"{cycle}:05+08:00",
        "cycle": cycle,
        "status": status,
        "freshness_signal": "content-date-parse",
        "last_modified": None,
        "content_date": "2026-08-12",
        "record_count": record_count,
        "record_count_estimated": estimated,
        "http_status": 200 if probe_outcome == "success" else 500,
        "latency_ms": None,
        "probe_outcome": probe_outcome,
        "message": "fixture",
        "url": url or f"https://example.test/{dataset_id}.csv",
        "shape_hash": shape_hash,
    }


def _prepare(
    tmp_path: Path,
    *,
    cycle: str,
    manifest_ids: tuple[str, ...] = ("alpha",),
    health_overrides: dict[str, dict] | None = None,
    history: list[dict] | None = None,
) -> tuple[Path, Path, Path, Path]:
    manifest = tmp_path / "datapulse.json"
    health = tmp_path / "health/latest.json"
    history_path = tmp_path / "health/history.jsonl"
    output_dir = tmp_path / "deltas"
    _write_json(
        manifest,
        {
            "datasets": [
                {
                    "id": dataset_id,
                    "name": f"{dataset_id.title()} Dataset",
                    "namespace": "test",
                    "licence": "MIT",
                    "url": f"https://example.test/{dataset_id}.csv",
                }
                for dataset_id in manifest_ids
            ]
        },
    )
    overrides = health_overrides or {}
    _write_json(
        health,
        {
            "checked_at": f"{cycle}:05+08:00",
            "datasets": [
                {
                    "dataset_id": dataset_id,
                    "status": "fresh",
                    "record_count": 100,
                    "record_count_estimated": False,
                    "first_row_hash": "shape-v1:old",
                    "freshness_signal": "content-date-parse",
                    **overrides.get(dataset_id, {}),
                }
                for dataset_id in manifest_ids
            ],
        },
    )
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(
        "".join(json.dumps(row) + "\n" for row in (history or [])),
        encoding="utf-8",
    )
    return manifest, health, history_path, output_dir


def _run_delta(
    cycle: str, manifest: Path, health: Path, history: Path, output_dir: Path
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "python3",
            str(DELTA_GENERATOR),
            "--cycle",
            cycle,
            "--manifest",
            str(manifest),
            "--health",
            str(health),
            "--history",
            str(history),
            "--output-dir",
            str(output_dir),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _generate(
    cycle: str, manifest: Path, health: Path, history: Path, output_dir: Path
) -> dict:
    result = _run_delta(cycle, manifest, health, history, output_dir)
    assert result.returncode == 0, result.stderr
    return json.loads((output_dir / f"{cycle}.json").read_text(encoding="utf-8"))


def test_delta_first_cycle_no_baseline(tmp_path: Path) -> None:
    cycle = "2026-08-12T18:00"
    paths = _prepare(tmp_path, cycle=cycle, history=[_history_row("alpha", cycle)])

    delta = _generate(cycle, *paths)

    assert delta["previous_cycle"] is None
    assert delta["previous_cycle_skipped_reason"] == "no_history_baseline_yet"
    assert all(value == 0 for value in delta["summary"].values())
    assert all(value == [] for value in delta["deltas"].values())


def test_delta_added(tmp_path: Path) -> None:
    prior, cycle = "2026-08-12T17:55", "2026-08-12T18:00"
    history = [
        _history_row("alpha", prior),
        _history_row("alpha", cycle),
        _history_row("beta", cycle),
    ]
    paths = _prepare(
        tmp_path, cycle=cycle, manifest_ids=("alpha", "beta"), history=history
    )

    delta = _generate(cycle, *paths)

    assert [row["dataset_id"] for row in delta["deltas"]["added"]] == ["beta"]


def test_delta_removed(tmp_path: Path) -> None:
    prior, cycle = "2026-08-12T17:55", "2026-08-12T18:00"
    history = [
        _history_row("alpha", prior),
        _history_row("beta", prior),
        _history_row("alpha", cycle),
    ]
    paths = _prepare(tmp_path, cycle=cycle, history=history)

    delta = _generate(cycle, *paths)

    assert delta["deltas"]["removed"] == [
        {
            "dataset_id": "beta",
            "name": "Beta Dataset",
            "last_known_status": "fresh",
            "from_cycle": prior,
        }
    ]


def test_delta_status_change_uses_latest_successful_prior(tmp_path: Path) -> None:
    old, failed, cycle = (
        "2026-08-12T17:50",
        "2026-08-12T17:55",
        "2026-08-12T18:00",
    )
    history = [
        _history_row("alpha", old, status="fresh"),
        _history_row(
            "alpha", failed, status="degraded", probe_outcome="error"
        ),
        _history_row("alpha", cycle, status="stale"),
    ]
    paths = _prepare(
        tmp_path,
        cycle=cycle,
        health_overrides={"alpha": {"status": "stale"}},
        history=history,
    )

    delta = _generate(cycle, *paths)

    assert delta["deltas"]["status_changed"] == [
        {
            "dataset_id": "alpha",
            "name": "Alpha Dataset",
            "from_status": "fresh",
            "to_status": "stale",
            "from_cycle": old,
            "signal_source": "content-date-parse",
        }
    ]


def test_delta_url_change(tmp_path: Path) -> None:
    prior, cycle = "2026-08-12T17:55", "2026-08-12T18:00"
    history = [
        _history_row("alpha", prior, url="https://example.test/old.csv"),
        _history_row("alpha", cycle, url="https://example.test/new.csv"),
    ]
    manifest, health, history_path, output_dir = _prepare(
        tmp_path, cycle=cycle, history=history
    )
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["datasets"][0]["url"] = "https://example.test/new.csv"
    _write_json(manifest, payload)

    delta = _generate(cycle, manifest, health, history_path, output_dir)

    assert delta["deltas"]["url_changed"] == [
        {
            "dataset_id": "alpha",
            "name": "Alpha Dataset",
            "from_url": "https://example.test/old.csv",
            "to_url": "https://example.test/new.csv",
            "from_cycle": prior,
        }
    ]
    assert delta["source_artifacts"]["manifest_sha256"] == hashlib.sha256(
        manifest.read_bytes()
    ).hexdigest()


def test_delta_record_count_change(tmp_path: Path) -> None:
    prior, cycle = "2026-08-12T17:55", "2026-08-12T18:00"
    history = [
        _history_row("alpha", prior, record_count=100),
        _history_row("alpha", cycle, record_count=110),
    ]
    paths = _prepare(
        tmp_path,
        cycle=cycle,
        health_overrides={"alpha": {"record_count": 110}},
        history=history,
    )

    delta = _generate(cycle, *paths)

    assert delta["deltas"]["record_count_changed"] == [
        {
            "dataset_id": "alpha",
            "name": "Alpha Dataset",
            "from_count": 100,
            "to_count": 110,
            "delta": 10,
            "from_cycle": prior,
        }
    ]


def test_delta_schema_change(tmp_path: Path) -> None:
    prior, cycle = "2026-08-12T17:55", "2026-08-12T18:00"
    history = [
        _history_row("alpha", prior, shape_hash="shape-v1:old"),
        _history_row("alpha", cycle, shape_hash="shape-v1:new"),
    ]
    paths = _prepare(
        tmp_path,
        cycle=cycle,
        health_overrides={"alpha": {"first_row_hash": "shape-v1:new"}},
        history=history,
    )

    delta = _generate(cycle, *paths)

    assert delta["deltas"]["schema_changed"] == [
        {
            "dataset_id": "alpha",
            "name": "Alpha Dataset",
            "from_shape_hash": "shape-v1:old",
            "to_shape_hash": "shape-v1:new",
            "from_cycle": prior,
        }
    ]


def test_delta_file_is_idempotent_but_not_overwritable(tmp_path: Path) -> None:
    cycle = "2026-08-12T18:00"
    paths = _prepare(tmp_path, cycle=cycle, history=[_history_row("alpha", cycle)])
    first = _run_delta(cycle, *paths)
    second = _run_delta(cycle, *paths)
    assert first.returncode == second.returncode == 0

    health = paths[1]
    payload = json.loads(health.read_text(encoding="utf-8"))
    payload["datasets"][0]["status"] = "stale"
    _write_json(health, payload)
    conflict = _run_delta(cycle, *paths)

    assert conflict.returncode != 0
    assert "immutable" in conflict.stderr.lower()


def test_changelog_renamed(tmp_path: Path) -> None:
    manifest, health, _, _ = _prepare(
        tmp_path,
        cycle="2026-08-12T18:00",
        history=[],
    )
    result = subprocess.run(
        [
            "python3",
            str(SNAPSHOT_GENERATOR),
            "--manifest",
            str(manifest),
            "--health",
            str(health),
            "--output",
            str(tmp_path / "catalog-snapshot.json"),
            "--legacy-alias",
            str(tmp_path / "changelog.json"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "catalog-snapshot.json").read_bytes() == (
        tmp_path / "changelog.json"
    ).read_bytes()
