from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "verify_registry_distribution.py"
VERSION = "0.12.0"
TITLE = "DataPulse"
DESCRIPTION = (
    "Read-only discovery for 418 Malaysian public datasets with freshness, licence, and provenance."
)
STALE_TITLE = "DataPulse MY"
STALE_DESCRIPTION = (
    "Read-only discovery for 389 Malaysian public datasets with freshness, licence, and provenance."
)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _server_json(*, title: str = TITLE, description: str = DESCRIPTION, version: str = VERSION) -> dict[str, object]:
    return {
        "name": "io.github.r3dz4r/datapulse-my",
        "title": title,
        "description": description,
        "version": version,
    }


def _registry(*servers: dict[str, object]) -> dict[str, object]:
    return {"servers": [{"server": server, "_meta": {}} for server in servers], "metadata": {}}


def _stage(
    root: Path,
    registry: dict[str, object],
    *,
    server: dict[str, object] | None = None,
    write_server: bool = True,
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    if write_server:
        _write_json(root / "server.json", server if server is not None else _server_json())
    fixture = root / "registry-versions.json"
    _write_json(fixture, registry)
    return fixture


def _run(root: Path, fixture: Path | None, *args: str) -> subprocess.CompletedProcess[str]:
    """Same CLI path for every case so a hardcoded exit cannot satisfy both controls."""
    environment = os.environ.copy()
    environment.pop("DATAPULSE_REGISTRY_FIXTURE", None)
    command = [sys.executable, str(SCRIPT), "--root", str(root), "--check", *args]
    if fixture is not None:
        command.extend(["--fixture", str(fixture)])
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )


def _pass(label: str) -> None:
    # Write past pytest capture so `pytest -q` still prints PASS lines.
    print(f"PASS: {label}", file=sys.__stdout__, flush=True)


def test_identical_fixture_exits_zero(tmp_path: Path) -> None:
    root = tmp_path / "identical"
    fixture = _stage(root, _registry(_server_json()))

    result = _run(root, fixture)

    assert result.returncode == 0, result.stderr
    assert "matches canonical surfaces" in result.stdout
    _pass("identical fixture → 0")


def test_title_mismatch_exits_one_and_names_the_field(tmp_path: Path) -> None:
    root = tmp_path / "title"
    fixture = _stage(root, _registry(_server_json(title=STALE_TITLE)))

    result = _run(root, fixture)

    assert result.returncode == 1
    output = result.stdout + result.stderr
    assert "title" in output
    assert STALE_TITLE in output
    assert TITLE in output
    _pass("title mismatch → 1 (names the field)")


def test_description_dataset_count_mismatch_exits_one(tmp_path: Path) -> None:
    root = tmp_path / "count"
    fixture = _stage(root, _registry(_server_json(description=STALE_DESCRIPTION)))

    result = _run(root, fixture)

    assert result.returncode == 1
    output = result.stdout + result.stderr
    assert "dataset_count" in output
    assert "389" in output
    assert "418" in output
    _pass("description dataset-count mismatch → 1")


def test_version_absent_exits_one_and_lists_published_versions(tmp_path: Path) -> None:
    root = tmp_path / "absent"
    published = _server_json(version="3.4.6", title=STALE_TITLE, description=STALE_DESCRIPTION)
    older = _server_json(version="3.4.5", title=STALE_TITLE, description=STALE_DESCRIPTION)
    fixture = _stage(root, _registry(published, older))

    result = _run(root, fixture)

    assert result.returncode == 1
    output = result.stdout + result.stderr
    assert VERSION in output
    assert "3.4.6" in output
    assert "3.4.5" in output
    _pass("version absent → 1 listing published versions")


def test_malformed_fixture_exits_two(tmp_path: Path) -> None:
    root = tmp_path / "malformed"
    root.mkdir(parents=True, exist_ok=True)
    _write_json(root / "server.json", _server_json())
    fixture = root / "registry-versions.json"
    fixture.write_text("{not-json", encoding="utf-8")

    result = _run(root, fixture)

    assert result.returncode == 2
    assert "cannot determine" in (result.stdout + result.stderr)
    _pass("malformed fixture → 2")


def test_missing_server_json_exits_two(tmp_path: Path) -> None:
    root = tmp_path / "missing-server"
    fixture = _stage(root, _registry(_server_json()), write_server=False)

    result = _run(root, fixture)

    assert result.returncode == 2
    output = result.stdout + result.stderr
    assert "cannot determine" in output
    assert "server.json" in output
    _pass("missing server.json → 2")


def test_positive_control_identical_and_mismatch_assert_opposite_exits(tmp_path: Path) -> None:
    identical_root = tmp_path / "positive-identical"
    mismatch_root = tmp_path / "positive-mismatch"
    identical_fixture = _stage(identical_root, _registry(_server_json()))
    mismatch_fixture = _stage(mismatch_root, _registry(_server_json(title=STALE_TITLE)))

    identical = _run(identical_root, identical_fixture)
    mismatch = _run(mismatch_root, mismatch_fixture)

    assert identical.returncode == 0, identical.stderr
    assert mismatch.returncode == 1
    assert identical.returncode != mismatch.returncode
    assert "title" in (mismatch.stdout + mismatch.stderr)
    _pass("positive control opposite exits from the same code path")
