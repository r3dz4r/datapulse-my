from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from scripts.public_surface_generation import (
    GenerationError,
    atomic_write_json,
    atomic_write_text,
    load_public_surfaces,
    replace_owned_block,
)


def _config() -> dict:
    return {
        "schema": "datapulse/v1/public-surfaces",
        "origins": {
            "website": "https://www.data-pulse.my",
            "mcp": "https://mcp.data-pulse.my",
            "api": "https://api.data-pulse.my",
            "repository": "https://github.com/r3dz4r/datapulse-my",
        },
        "pages": ["/", "/npra.html", "/health-methodology.html"],
        "artifacts": ["/llms.txt", "/agent.json", "/mcp.json"],
        "featured_dataset_ids": ["alpha"],
    }


def _write_config(root: Path, document: dict) -> None:
    path = root / "config/public-surfaces.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(document) + "\n", encoding="utf-8")
    (root / "config/public-surfaces.schema.json").write_text(json.dumps({
        "properties": {"origins": {"properties": {
            "website": {"const": "https://www.data-pulse.my"},
            "mcp": {"const": "https://mcp.data-pulse.my"},
            "api": {"const": "https://api.data-pulse.my"},
            "repository": {"const": "https://github.com/r3dz4r/datapulse-my"},
        }, "additionalProperties": False}},
        "additionalProperties": False,
    }) + "\n", encoding="utf-8")


def test_load_public_surfaces_accepts_strict_config(tmp_path: Path) -> None:
    _write_config(tmp_path, _config())
    assert load_public_surfaces(tmp_path)["origins"]["website"] == "https://www.data-pulse.my"


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda value: value.update({"unknown": True}), "unknown"),
        (lambda value: value["origins"].update({"website": "http://data-pulse.my"}), "HTTPS"),
        (lambda value: value["pages"].append("/../private"), "path"),
        (lambda value: value["pages"].append("/"), "duplicate"),
        (lambda value: value["origins"].update({"website": "https://r3dz4r.github.io"}), "canonical"),
        (lambda value: value.update({"secret": "token"}), "unknown"),
    ],
)
def test_load_public_surfaces_rejects_unsafe_config(
    tmp_path: Path, mutation, message: str
) -> None:
    document = _config()
    mutation(document)
    _write_config(tmp_path, document)
    with pytest.raises(GenerationError, match=message):
        load_public_surfaces(tmp_path)


def test_replace_owned_block_preserves_unowned_bytes() -> None:
    source = "before\n<!-- BEGIN sample -->\nold\n<!-- END sample -->\nafter\n"
    assert replace_owned_block(source, "sample", "new") == (
        "before\n<!-- BEGIN sample -->\nnew\n<!-- END sample -->\nafter\n"
    )


@pytest.mark.parametrize(
    "source",
    [
        "missing\n",
        "<!-- END sample -->\n<!-- BEGIN sample -->\n",
        "<!-- BEGIN sample -->\n<!-- BEGIN sample -->\n<!-- END sample -->\n",
        "<!-- BEGIN sample -->\n<!-- BEGIN other -->\n<!-- END other -->\n<!-- END sample -->\n",
    ],
)
def test_replace_owned_block_rejects_invalid_markers(source: str) -> None:
    with pytest.raises(GenerationError):
        replace_owned_block(source, "sample", "new")


def test_atomic_write_preserves_mode_and_rejects_symlink(tmp_path: Path) -> None:
    target = tmp_path / "target.txt"
    target.write_text("old\n", encoding="utf-8")
    target.chmod(0o640)
    atomic_write_text(target, "new\n")
    assert target.read_text(encoding="utf-8") == "new\n"
    assert target.stat().st_mode & 0o777 == 0o640

    link = tmp_path / "link.txt"
    os.symlink(target, link)
    with pytest.raises(GenerationError, match="symlink"):
        atomic_write_text(link, "bad\n")
    assert target.read_text(encoding="utf-8") == "new\n"


def test_atomic_json_output_is_byte_stable_and_preserves_declared_key_order(tmp_path: Path) -> None:
    target = tmp_path / "surface.json"
    payload = {"schema": "datapulse/test", "zeta": 2, "alpha": {"second": 2, "first": 1}}

    atomic_write_json(target, payload)
    first = target.read_bytes()
    atomic_write_json(target, payload)

    assert target.read_bytes() == first
    assert first == (
        b'{\n  "schema": "datapulse/test",\n  "zeta": 2,\n  "alpha": {\n'
        b'    "second": 2,\n    "first": 1\n  }\n}\n'
    )


def test_manifest_schema_contract_derives_from_canonical_website_origin() -> None:
    root = Path(__file__).resolve().parents[2]
    website = load_public_surfaces(root)["origins"]["website"]
    schema = json.loads((root / "datapulse.schema.json").read_text(encoding="utf-8"))

    # The schema's own $id is a current public surface (config/public-surfaces
    # artifacts include /datapulse.schema.json) and must live at the www origin.
    assert schema["$id"] == f"{website}/datapulse.schema.json"
    # The manifest $schema contract accepts the canonical identifier first and
    # keeps exactly one documented legacy value for already-published manifests
    # whose $schema field is not republished yet.
    contract = schema["properties"]["$schema"]
    assert contract["enum"] == [
        f"{website}/datapulse.schema.json",
        "https://r3dz4r.github.io/datapulse-my/datapulse.schema.json",
    ]
    assert "legacy" in contract["description"]
