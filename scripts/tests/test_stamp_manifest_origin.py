from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.public_surface_generation import load_public_surfaces
from scripts.stamp_manifest_origin import GenerationError, canonical_schema_url, stamp


STALE_MANIFEST = (
    "{\n"
    '  "$schema": "https://r3dz4r.github.io/datapulse-my/datapulse.schema.json",\n'
    '  "datasets": [\n'
    '    {"id": "alpha"}\n'
    "  ]\n"
    "}\n"
)

CANONICAL_SCHEMA_URL = "https://www.data-pulse.my/datapulse.schema.json"


def _stage(root: Path, manifest: str = STALE_MANIFEST) -> None:
    config = {
        "schema": "datapulse/v1/public-surfaces",
        "origins": {
            "website": "https://www.data-pulse.my",
            "mcp": "https://mcp.data-pulse.my",
            "api": "https://api.data-pulse.my",
            "repository": "https://github.com/r3dz4r/datapulse-my",
        },
        "pages": ["/", "/npra.html"],
        "artifacts": ["/datapulse.json", "/datapulse.schema.json"],
        "featured_dataset_ids": ["alpha"],
    }
    (root / "config").mkdir()
    (root / "config/public-surfaces.json").write_text(json.dumps(config) + "\n")
    (root / "config/public-surfaces.schema.json").write_text(json.dumps({
        "properties": {"origins": {"properties": {
            "website": {"const": "https://www.data-pulse.my"},
            "mcp": {"const": "https://mcp.data-pulse.my"},
            "api": {"const": "https://api.data-pulse.my"},
            "repository": {"const": "https://github.com/r3dz4r/datapulse-my"},
        }, "required": ["website", "mcp", "api", "repository"], "additionalProperties": False}},
        "additionalProperties": False,
    }) + "\n")
    (root / "datapulse.json").write_text(manifest, encoding="utf-8")


def test_stamp_rewrites_schema_pointer_preserving_other_bytes(tmp_path: Path) -> None:
    _stage(tmp_path)

    value = stamp(tmp_path)

    assert value == CANONICAL_SCHEMA_URL
    assert value == canonical_schema_url(load_public_surfaces(tmp_path))
    after = (tmp_path / "datapulse.json").read_text(encoding="utf-8")
    assert after == STALE_MANIFEST.replace(
        "https://r3dz4r.github.io/datapulse-my/datapulse.schema.json",
        CANONICAL_SCHEMA_URL,
    )
    document = json.loads(after)
    assert document["$schema"] == CANONICAL_SCHEMA_URL
    assert document["datasets"] == [{"id": "alpha"}]


def test_stamp_is_idempotent(tmp_path: Path) -> None:
    _stage(tmp_path)

    first = stamp(tmp_path)
    after_first = (tmp_path / "datapulse.json").read_bytes()
    second = stamp(tmp_path)

    assert first == second == CANONICAL_SCHEMA_URL
    assert (tmp_path / "datapulse.json").read_bytes() == after_first


def test_stamp_leaves_already_canonical_manifest_untouched(tmp_path: Path) -> None:
    canonical = STALE_MANIFEST.replace(
        "https://r3dz4r.github.io/datapulse-my/datapulse.schema.json",
        CANONICAL_SCHEMA_URL,
    )
    _stage(tmp_path, canonical)

    assert stamp(tmp_path) == CANONICAL_SCHEMA_URL
    assert (tmp_path / "datapulse.json").read_text(encoding="utf-8") == canonical


def test_stamp_preserves_manifest_without_trailing_comma(tmp_path: Path) -> None:
    _stage(tmp_path, '{\n  "$schema": "fixture"\n}\n')

    value = stamp(tmp_path)

    assert value == CANONICAL_SCHEMA_URL
    assert (tmp_path / "datapulse.json").read_text(encoding="utf-8") == (
        '{\n  "$schema": "https://www.data-pulse.my/datapulse.schema.json"\n}\n'
    )


def test_stamp_rejects_malformed_manifest(tmp_path: Path) -> None:
    _stage(tmp_path, '{"$schema":')
    with pytest.raises(GenerationError):
        stamp(tmp_path)


def test_stamp_rejects_manifest_without_schema_pointer(tmp_path: Path) -> None:
    _stage(tmp_path, '{\n  "datasets": [{"id": "alpha"}]\n}\n')
    with pytest.raises(GenerationError):
        stamp(tmp_path)
