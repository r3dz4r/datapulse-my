from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "release_identity.py"
MANIFEST = "0.12.0"
OTHER_VERSION = "9.9.9"
SERVER_MARKER = "preserve-me"


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _stage(
    root: Path,
    *,
    manifest: str = MANIFEST,
    version_txt: str = MANIFEST,
    server_version: str = MANIFEST,
    tag: str | None = None,
    include_manifest: bool = True,
) -> None:
    root.mkdir(parents=True, exist_ok=True)
    if include_manifest:
        _write_json(root / ".release-please-manifest.json", {".": manifest})
    (root / "VERSION.txt").write_text(f"{version_txt}\n", encoding="utf-8")
    _write_json(
        root / "server.json",
        {
            "$schema": "https://example.test/server.schema.json",
            "name": "io.github.test/datapulse",
            "title": "DataPulse",
            "description": "fixture",
            "version": server_version,
            "websiteUrl": "https://www.data-pulse.my",
            "marker": SERVER_MARKER,
        },
    )
    if tag is not None:
        _init_git_with_tag(root, tag)


def _init_git_with_tag(root: Path, tag: str) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "commit", "-qm", "fixture"],
        cwd=root,
        check=True,
    )
    subprocess.run(["git", "tag", tag], cwd=root, check=True)


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_all_values_agree_exits_zero(tmp_path: Path) -> None:
    root = tmp_path / "agree"
    _stage(root, tag=f"v{MANIFEST}")

    result = _run(root, "--check")

    assert result.returncode == 0, result.stderr
    output = result.stdout
    assert f"manifest: {MANIFEST}" in output
    assert f"version_txt: {MANIFEST}" in output
    assert f"server_json: {MANIFEST}" in output
    assert f"tag: {MANIFEST}" in output


def test_manifest_versus_version_txt_disagree_exits_one(tmp_path: Path) -> None:
    root = tmp_path / "version-txt"
    _stage(root, version_txt=OTHER_VERSION)

    result = _run(root, "--check")

    assert result.returncode == 1
    output = result.stdout + result.stderr
    assert MANIFEST in output
    assert OTHER_VERSION in output
    assert "manifest" in output
    assert "version_txt" in output


def test_server_json_version_disagree_exits_one(tmp_path: Path) -> None:
    root = tmp_path / "server"
    _stage(root, server_version=OTHER_VERSION)

    result = _run(root, "--check")

    assert result.returncode == 1
    output = result.stdout + result.stderr
    assert MANIFEST in output
    assert OTHER_VERSION in output
    assert "server_json" in output


def test_manifest_missing_exits_two(tmp_path: Path) -> None:
    root = tmp_path / "missing"
    _stage(root, include_manifest=False)

    result = _run(root, "--check")

    assert result.returncode == 2
    assert "cannot determine" in (result.stdout + result.stderr)


def test_newest_tag_disagree_exits_one(tmp_path: Path) -> None:
    root = tmp_path / "tag"
    _stage(root, tag=f"v{OTHER_VERSION}")

    result = _run(root, "--check")

    assert result.returncode == 1
    output = result.stdout + result.stderr
    assert MANIFEST in output
    assert OTHER_VERSION in output
    assert "tag" in output


def test_write_rewrites_server_json_version_preserving_other_fields(tmp_path: Path) -> None:
    root = tmp_path / "write"
    _stage(root, server_version=OTHER_VERSION)
    original = (root / "server.json").read_text(encoding="utf-8")
    original_fields = json.loads(original)
    original_fields.pop("version")

    result = _run(root, "--write")

    assert result.returncode == 0, result.stderr
    updated = (root / "server.json").read_text(encoding="utf-8")
    updated_fields = json.loads(updated)
    assert updated_fields["version"] == MANIFEST
    updated_fields.pop("version")
    assert updated_fields == original_fields
    original_lines = [line for line in original.splitlines() if '"version"' not in line]
    updated_lines = [line for line in updated.splitlines() if '"version"' not in line]
    assert updated_lines == original_lines
    assert updated.endswith("\n")
    assert updated == original.replace(
        f'"version": "{OTHER_VERSION}"',
        f'"version": "{MANIFEST}"',
    )


def test_positive_control_agreeing_fixture_passes_and_disagreeing_fixture_fails(
    tmp_path: Path,
) -> None:
    agreeing = tmp_path / "positive-agree"
    disagreeing = tmp_path / "positive-disagree"
    _stage(agreeing)
    _stage(disagreeing, version_txt=OTHER_VERSION)

    agree_result = _run(agreeing, "--check")
    disagree_result = _run(disagreeing, "--check")

    assert agree_result.returncode == 0, agree_result.stderr
    assert disagree_result.returncode == 1
    disagree_output = disagree_result.stdout + disagree_result.stderr
    assert MANIFEST in disagree_output
    assert OTHER_VERSION in disagree_output
