"""Tests for the narrowly owned buyer API documentation blocks."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from scripts.gen_api_reference import ApiReferenceError, render_document


ROOT = Path(__file__).resolve().parents[2]


def _stage(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    for relative in ("config", "docs", "health"):
        shutil.copytree(ROOT / relative, root / relative)
    shutil.copy2(ROOT / "datapulse.json", root / "datapulse.json")
    return root


def test_reference_is_idempotent_and_uses_canonical_dynamic_facts(tmp_path: Path) -> None:
    root = _stage(tmp_path)
    dataset_count = len(json.loads((root / "datapulse.json").read_text(encoding="utf-8"))["datasets"])
    reference = root / "docs/buyer-api-reference.md"
    first = render_document(root, reference, root / "datapulse.json", root / "health/latest.json")
    reference.write_text(first, encoding="utf-8")
    second = render_document(root, reference, root / "datapulse.json", root / "health/latest.json")
    assert first == second
    assert "https://api.data-pulse.my/api/v1/health" in first
    assert "api.datapulse-my.my" not in first
    assert f'"total": {dataset_count}' in first
    assert "cap it at 1000" in first


@pytest.mark.parametrize("mutation", [
    lambda source: source.replace("<!-- END buyer-api-host -->", "", 1),
    lambda source: source.replace("<!-- BEGIN buyer-api-host -->", "<!-- END buyer-api-host -->", 1),
    lambda source: source.replace("<!-- BEGIN buyer-api-host -->", "<!-- BEGIN buyer-api-host -->\n<!-- BEGIN nested -->", 1),
])
def test_reference_rejects_malformed_markers_without_writing(tmp_path: Path, mutation) -> None:
    root = _stage(tmp_path)
    reference = root / "docs/buyer-api-reference.md"
    original = mutation(reference.read_text(encoding="utf-8"))
    reference.write_text(original, encoding="utf-8")
    with pytest.raises(ApiReferenceError):
        render_document(root, reference, root / "datapulse.json", root / "health/latest.json")
    assert reference.read_text(encoding="utf-8") == original
