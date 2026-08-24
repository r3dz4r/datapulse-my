from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from scripts.gen_public_discovery import GenerationError, generate


def _stage(root: Path) -> None:
    config = {
        "schema": "datapulse/v1/public-surfaces",
        "origins": {
            "website": "https://data-pulse.my",
            "mcp": "https://mcp.data-pulse.my",
            "repository": "https://github.com/r3dz4r/datapulse-my",
        },
        "pages": ["/", "/npra.html"],
        "artifacts": ["/llms.txt", "/agent.json", "/mcp.json"],
        "featured_dataset_ids": ["alpha"],
    }
    (root / "config").mkdir()
    (root / "config/public-surfaces.json").write_text(json.dumps(config) + "\n")
    (root / "config/public-surfaces.schema.json").write_text(json.dumps({
        "properties": {"origins": {"properties": {
            "website": {"const": "https://data-pulse.my"},
            "mcp": {"const": "https://mcp.data-pulse.my"},
            "repository": {"const": "https://github.com/r3dz4r/datapulse-my"},
        }, "additionalProperties": False}},
        "additionalProperties": False,
    }) + "\n")
    (root / "README.md").write_text(
        "readme-before\n<!-- BEGIN public-discovery -->\nold\n<!-- END public-discovery -->\nreadme-after\n"
    )
    (root / "llms.txt").write_text(
        "llms-before\n<!-- BEGIN public-discovery -->\nold\n<!-- END public-discovery -->\nllms-after\n"
    )
    (root / "robots.txt").write_text(
        "robots-before\n<!-- BEGIN public-discovery -->\nold\n<!-- END public-discovery -->\nrobots-after\n"
    )


def test_generation_is_deterministic_and_preserves_unowned_prose(tmp_path: Path) -> None:
    _stage(tmp_path)
    generate(tmp_path)
    first = {name: (tmp_path / name).read_bytes() for name in ("README.md", "llms.txt", "robots.txt", "sitemap.xml")}
    generate(tmp_path)
    second = {name: (tmp_path / name).read_bytes() for name in first}
    assert first == second
    assert (tmp_path / "README.md").read_text().startswith("readme-before\n")
    assert (tmp_path / "README.md").read_text().endswith("readme-after\n")

    root = ET.fromstring(first["sitemap.xml"])
    locations = [node.text for node in root.findall("{http://www.sitemaps.org/schemas/sitemap/0.9}url/{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]
    assert locations == [
        "https://data-pulse.my/",
        "https://data-pulse.my/npra.html",
        "https://data-pulse.my/llms.txt",
        "https://data-pulse.my/agent.json",
        "https://data-pulse.my/mcp.json",
    ]


def test_marker_failure_changes_no_output(tmp_path: Path) -> None:
    _stage(tmp_path)
    before = {name: (tmp_path / name).read_bytes() for name in ("README.md", "llms.txt", "robots.txt")}
    (tmp_path / "robots.txt").write_text("missing marker\n")
    failed_before = (tmp_path / "robots.txt").read_bytes()
    with pytest.raises(GenerationError):
        generate(tmp_path)
    assert (tmp_path / "README.md").read_bytes() == before["README.md"]
    assert (tmp_path / "llms.txt").read_bytes() == before["llms.txt"]
    assert (tmp_path / "robots.txt").read_bytes() == failed_before
    assert not (tmp_path / "sitemap.xml").exists()
