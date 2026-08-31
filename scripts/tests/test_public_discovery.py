from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from scripts.gen_public_discovery import GenerationError, generate
from scripts.public_surface_generation import load_public_surfaces


def _stage(root: Path) -> None:
    config = {
        "schema": "datapulse/v1/public-surfaces",
        "origins": {
            "website": "https://www.data-pulse.my",
            "mcp": "https://mcp.data-pulse.my",
            "api": "https://api.data-pulse.my",
            "repository": "https://github.com/r3dz4r/datapulse-my",
        },
        "pages": ["/", "/npra.html", "/health-methodology.html"],
        "compatibility_aliases": [{"path": "/landing.html", "target": "/"}],
        "artifacts": ["/buyer-api-reference.md", "/llms.txt", "/agent.json", "/mcp.json"],
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
        "https://www.data-pulse.my/",
        "https://www.data-pulse.my/npra.html",
        "https://www.data-pulse.my/health-methodology.html",
        "https://www.data-pulse.my/buyer-api-reference.md",
        "https://www.data-pulse.my/llms.txt",
        "https://www.data-pulse.my/agent.json",
        "https://www.data-pulse.my/mcp.json",
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


def _stage_stale_links(root: Path) -> None:
    _stage(root)
    (root / "README.md").write_text(
        "readme-before\n"
        "See [`llms.txt`](https://r3dz4r.github.io/datapulse-my/llms.txt) and\n"
        "the [NPRA engine page](https://data-pulse.my/npra.html) plus the\n"
        "[bare apex](https://data-pulse.my) origin; MCP stays\n"
        "`https://mcp.data-pulse.my/mcp` and plain text\n"
        "https://data-pulse.my/npra.html is not a markdown link target.\n"
        "<!-- BEGIN public-discovery -->\nold\n<!-- END public-discovery -->\n"
        "readme-after\n"
    )
    (root / "llms.txt").write_text(
        "llms-before\n"
        "The [NPRA engine page](https://data-pulse.my/npra.html) and\n"
        "[`mcp-deploy.md`](https://data-pulse.my/mcp-deploy.md) are public.\n"
        "The MCP endpoint `https://mcp.data-pulse.my/mcp` is unchanged.\n"
        "<!-- BEGIN public-discovery -->\nold\n<!-- END public-discovery -->\n"
        "llms-after\n"
    )
    (root / "robots.txt").write_text(
        "robots-before\n"
        "Stale [link](https://data-pulse.my/npra.html) outside canonicalization scope.\n"
        "<!-- BEGIN public-discovery -->\nold\n<!-- END public-discovery -->\n"
        "robots-after\n"
    )


def test_stale_origin_links_in_markdown_targets_are_rewritten(tmp_path: Path) -> None:
    _stage_stale_links(tmp_path)
    website = load_public_surfaces(tmp_path)["origins"]["website"]

    generate(tmp_path)

    readme = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert f"]({website}/llms.txt)" in readme
    assert f"]({website}/npra.html)" in readme
    assert f"](https://www.data-pulse.my)" in readme or f"]({website})" in readme
    assert "r3dz4r.github.io/datapulse-my" not in readme
    assert "https://mcp.data-pulse.my/mcp" in readme
    assert "https://data-pulse.my/npra.html is not a markdown link target" in readme
    assert readme.startswith("readme-before\n")
    assert readme.endswith("readme-after\n")

    llms = (tmp_path / "llms.txt").read_text(encoding="utf-8")
    assert f"]({website}/npra.html)" in llms
    assert f"]({website}/mcp-deploy.md)" in llms
    assert "https://mcp.data-pulse.my/mcp" in llms
    assert llms.startswith("llms-before\n")
    assert llms.endswith("llms-after\n")

    robots = (tmp_path / "robots.txt").read_text(encoding="utf-8")
    assert "](https://data-pulse.my/npra.html)" in robots


def test_origin_canonicalization_is_idempotent(tmp_path: Path) -> None:
    _stage_stale_links(tmp_path)
    generate(tmp_path)
    first = {name: (tmp_path / name).read_bytes() for name in ("README.md", "llms.txt", "robots.txt")}
    generate(tmp_path)
    second = {name: (tmp_path / name).read_bytes() for name in first}
    assert first == second


def test_check_mode_reports_stale_origin_links(tmp_path: Path) -> None:
    _stage_stale_links(tmp_path)
    generate(tmp_path)
    assert generate(tmp_path, check=True) is False
    current = (tmp_path / "README.md").read_text(encoding="utf-8")
    (tmp_path / "README.md").write_text(
        current.replace(
            "](https://www.data-pulse.my/npra.html)",
            "](https://data-pulse.my/npra.html)",
            1,
        ),
        encoding="utf-8",
    )
    assert generate(tmp_path, check=True) is True
