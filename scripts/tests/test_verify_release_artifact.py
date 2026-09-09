"""Tests for deterministic Cloudflare Pages release-artifact manifests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.verify_release_artifact import (
    ManifestError,
    aggregate_digest,
    create_manifest,
    load_manifest,
    verify_manifest,
)


SOURCE_COMMIT = "a" * 40


def _site(tmp_path: Path) -> Path:
    site = tmp_path / "_site"
    site.mkdir()
    (site / "index.html").write_bytes(b"canonical dashboard\n")
    (site / "health").mkdir()
    (site / "health" / "latest.json").write_bytes(b'{"datasets": []}\n')
    return site


def _manifest(site: Path, tmp_path: Path) -> Path:
    manifest = tmp_path / "release-artifact.json"
    create_manifest(site, manifest, SOURCE_COMMIT)
    return manifest


def test_inventory_is_deterministic_and_has_stable_aggregate_digest(tmp_path: Path) -> None:
    site = _site(tmp_path)
    first = _manifest(site, tmp_path)
    second = tmp_path / "second.json"
    create_manifest(site, second, SOURCE_COMMIT)

    assert first.read_bytes() == second.read_bytes()
    manifest = load_manifest(first)
    assert manifest["schema"] == "datapulse/v1/release-artifact-manifest"
    assert manifest["source_commit"] == SOURCE_COMMIT
    assert manifest["file_count"] == 2
    assert [entry["path"] for entry in manifest["files"]] == ["health/latest.json", "index.html"]
    assert len(manifest["aggregate_sha256"]) == 64


def test_verify_detects_tampered_file_bytes(tmp_path: Path) -> None:
    site = _site(tmp_path)
    manifest = _manifest(site, tmp_path)
    (site / "index.html").write_bytes(b"canonical dashboarD\n")

    with pytest.raises(ManifestError, match="digest mismatch"):
        verify_manifest(site, manifest, SOURCE_COMMIT)


@pytest.mark.parametrize("unsafe_path", ("../outside", "/absolute", "", "health/../latest.json", "health//latest.json"))
def test_verify_rejects_path_traversal_and_unsafe_manifest_paths(tmp_path: Path, unsafe_path: str) -> None:
    site = _site(tmp_path)
    manifest_path = _manifest(site, tmp_path)
    manifest = load_manifest(manifest_path)
    manifest["files"][0]["path"] = unsafe_path
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ManifestError, match="unsafe manifest path"):
        verify_manifest(site, manifest_path, SOURCE_COMMIT)


def test_verify_rejects_missing_file(tmp_path: Path) -> None:
    site = _site(tmp_path)
    manifest = _manifest(site, tmp_path)
    (site / "health" / "latest.json").unlink()

    with pytest.raises(ManifestError, match="inventory does not match"):
        verify_manifest(site, manifest, SOURCE_COMMIT)


def test_verify_rejects_unexpected_manifest_path(tmp_path: Path) -> None:
    site = _site(tmp_path)
    manifest_path = _manifest(site, tmp_path)
    manifest = load_manifest(manifest_path)
    manifest["files"][1]["path"] = "unexpected.json"
    manifest["aggregate_sha256"] = aggregate_digest(manifest["files"])
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ManifestError, match="inventory does not match"):
        verify_manifest(site, manifest_path, SOURCE_COMMIT)


def test_verify_rejects_source_commit_mismatch(tmp_path: Path) -> None:
    site = _site(tmp_path)
    manifest = _manifest(site, tmp_path)

    with pytest.raises(ManifestError, match="source commit mismatch"):
        verify_manifest(site, manifest, "b" * 40)


def test_create_and_verify_reject_symlinks(tmp_path: Path) -> None:
    site = _site(tmp_path)
    (site / "linked.html").symlink_to(site / "index.html")

    with pytest.raises(ManifestError, match="symlink"):
        create_manifest(site, tmp_path / "release-artifact.json", SOURCE_COMMIT)
