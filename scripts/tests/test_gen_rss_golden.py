"""Frozen output contract for the RSS generator."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from itertools import zip_longest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "scripts/tests/fixtures/gen_rss"
SCRIPT = ROOT / "scripts/gen_rss.sh"
ALLOWLIST = {
    "fresh",
    "aging",
    "stale",
    "degraded",
    "browser-dependent",
    "unreachable",
    "unknown",
    "unknown-freshness",
    "reference",
}


def _configured_path(variable: str, default: Path) -> Path:
    """Return an optional scratch override without changing the frozen default."""
    return Path(os.environ[variable]) if variable in os.environ else default


def _first_difference(expected: bytes, actual: bytes) -> str:
    """Describe the first differing line so a byte mismatch is actionable."""
    expected_lines = expected.decode("utf-8").splitlines()
    actual_lines = actual.decode("utf-8").splitlines()
    for line_number, (expected_line, actual_line) in enumerate(
        zip_longest(expected_lines, actual_lines, fillvalue="<no line>"), start=1
    ):
        if expected_line != actual_line:
            return (
                f"first differing line {line_number}:\n"
                f"expected: {expected_line!r}\n"
                f"actual:   {actual_line!r}"
            )
    return "bytes differ outside decoded lines"


def test_gen_rss_matches_frozen_feed_contract(tmp_path: Path) -> None:
    expected_path = _configured_path("GEN_RSS_GOLDEN_EXPECTED", FIXTURE / "expected-feed.xml")
    health_path = _configured_path("GEN_RSS_GOLDEN_HEALTH", FIXTURE / "health.json")
    manifest_path = _configured_path("GEN_RSS_GOLDEN_MANIFEST", FIXTURE / "manifest.json")

    result = subprocess.run(
        ["bash", str(SCRIPT), str(health_path), str(manifest_path)],
        cwd=tmp_path,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8")

    expected = expected_path.read_bytes()
    actual = (tmp_path / "feed.xml").read_bytes()
    assert actual == expected, _first_difference(expected, actual)

    root = ET.fromstring(actual)
    items = root.findall("./channel/item")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert len(items) == len(manifest["datasets"])

    for item in items:
        assert item.findtext("pubDate")
        title = item.findtext("title")
        assert title is not None
        match = re.fullmatch(r"\[([^]]+)\] .+", title)
        assert match is not None
        assert match.group(1) in ALLOWLIST
