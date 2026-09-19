"""Store and history roots must honour their environment override.

Pins the second production residual: ``observation_store.py`` and
``gen_health_history.py`` pointed their defaults at a fixed operator home, so a
service identity whose ``HOME`` differs silently resolved to a directory that
did not exist. The override takes precedence; with it unset the result is
identical to today's default.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import gen_health_history  # noqa: E402
import observation_store  # noqa: E402

WRITER = ROOT / "scripts/gen_health_history.py"
FIXTURE = ROOT / "scripts/tests/fixtures/health-history-snapshot.json"


def test_store_root_honours_environment_override(monkeypatch, tmp_path: Path) -> None:
    override = tmp_path / "store"
    monkeypatch.setenv(observation_store.ROOT_ENVIRONMENT_VARIABLE, str(override))

    assert observation_store.resolve_root(None) == override


def test_store_root_falls_back_to_today_default(monkeypatch) -> None:
    monkeypatch.delenv(observation_store.ROOT_ENVIRONMENT_VARIABLE, raising=False)

    assert observation_store.resolve_root(None) == observation_store.DEFAULT_ROOT
    assert observation_store.DEFAULT_ROOT == Path("/home/redza/runtime/datapulse-observations")


def test_history_root_honours_environment_override(monkeypatch, tmp_path: Path) -> None:
    override = tmp_path / "archives"
    monkeypatch.setenv(gen_health_history.ARCHIVES_ENVIRONMENT_VARIABLE, str(override))

    assert gen_health_history.resolve_archives_dir() == override


def test_history_root_falls_back_to_today_default(monkeypatch) -> None:
    monkeypatch.delenv(gen_health_history.ARCHIVES_ENVIRONMENT_VARIABLE, raising=False)

    assert gen_health_history.resolve_archives_dir() == gen_health_history.DEFAULT_ARCHIVES_DIR
    assert gen_health_history.DEFAULT_ARCHIVES_DIR == Path.home() / "runtime/datapulse-history"


def test_explicit_archives_dir_beats_the_environment(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv(gen_health_history.ARCHIVES_ENVIRONMENT_VARIABLE, str(tmp_path / "env"))
    explicit = tmp_path / "explicit"

    assert gen_health_history.resolve_archives_dir(explicit) == explicit


def test_history_cli_writes_archives_to_the_environment_root(
    tmp_path: Path, monkeypatch
) -> None:
    override = tmp_path / "env-archives"
    monkeypatch.setenv(gen_health_history.ARCHIVES_ENVIRONMENT_VARIABLE, str(override))
    history = tmp_path / "history.jsonl"
    history.write_text(
        "".join(
            json.dumps(
                {
                    "dataset_id": "dataset-000",
                    "observed_at": f"2026-05-{day:02d}T00:00:05Z",
                    "cycle": f"2026-05-{day:02d}T08:00",
                    "status": "fresh",
                    "probe_outcome": "success",
                    "record_count": day,
                }
            )
            + "\n"
            for day in range(1, 10)
        ),
        encoding="utf-8",
    )
    snapshot = tmp_path / "latest.json"
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["checked_at"] = "2026-08-16T00:00:05Z"
    snapshot.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    result = subprocess.run(
        [
            "python3",
            str(WRITER),
            "--snapshot",
            str(snapshot),
            "--history",
            str(history),
            "--daily",
            str(tmp_path / "history_daily.json"),
            "--cycle",
            "2026-08-16T00:00",
            "--retention-days",
            "1",
            "--now",
            "2030-01-01T00:00:00+00:00",
            "--compact",
        ],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "DATAPULSE_ARCHIVES_DIR": str(override)},
    )

    assert result.returncode == 0, result.stderr
    assert list(override.glob("*.jsonl.gz")), result.stderr
