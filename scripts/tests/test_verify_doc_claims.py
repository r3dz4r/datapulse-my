from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.verify_doc_claims import verify_doc_claims


def _fixture(root: Path) -> None:
    (root / "docs").mkdir()
    (root / "datapulse.json").write_text(json.dumps({"datasets": [{}, {}]}), encoding="utf-8")
    (root / "mcp.json").write_text(json.dumps({"tools": [{}]}), encoding="utf-8")
    (root / "AGENTS.md").write_text("2 datasets and 1 tool.\n", encoding="utf-8")
    (root / "docs" / "AUDIT-2026-08-05.md").write_text("389 datasets and 16 tools.\n", encoding="utf-8")
    (root / "scripts").mkdir()
    (root / "scripts" / "doc_claims.json").write_text(
        json.dumps({
            "live_documents": ["AGENTS.md", "docs/*.md"],
            "dated_exemptions": ["docs/AUDIT-*.md"],
            "claims": [
                {"name": "datasets", "derive": "jq '.datasets | length' datapulse.json", "source": "datapulse.json", "pattern": r"(?P<count>\d+) datasets?\b"},
                {"name": "tools", "derive": "jq '.tools | length' mcp.json", "source": "mcp.json", "pattern": r"(?P<count>\d+) tools?\b"},
            ],
        }), encoding="utf-8",
    )


def test_current_claims_pass_and_dated_records_are_exempt(tmp_path: Path) -> None:
    _fixture(tmp_path)

    assert verify_doc_claims(tmp_path) == []


def test_reports_every_drift_with_file_line_and_source(tmp_path: Path) -> None:
    _fixture(tmp_path)
    (tmp_path / "AGENTS.md").write_text("Header\n3 datasets and 2 tools.\n", encoding="utf-8")

    assert verify_doc_claims(tmp_path) == [
        "AGENTS.md:2 claims 3 datasets, datapulse.json holds 2",
        "AGENTS.md:2 claims 2 tools, mcp.json holds 1",
    ]


def test_taxonomy_list_disagreement_is_reported(tmp_path: Path) -> None:
    _fixture(tmp_path)
    (tmp_path / "health.schema.json").write_text(json.dumps({"statuses": ["fresh", "stale"]}), encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("2-status taxonomy (`fresh | aging`).\n", encoding="utf-8")
    manifest_path = tmp_path / "scripts" / "doc_claims.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["claims"] = [{
        "name": "statuses",
        "derive": "jq -r '.statuses[]' health.schema.json",
        "source": "health.schema.json",
        "pattern": r"(?P<count>\d+)-status\b",
        "list_pattern": r"\d+-status taxonomy \(`(?P<items>[^`]+)`\)",
    }]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    assert verify_doc_claims(tmp_path) == [
        "AGENTS.md:1 claims [fresh, aging], health.schema.json holds [fresh, stale]"
    ]


def test_failed_pipeline_derivation_cannot_appear_as_zero(tmp_path: Path) -> None:
    _fixture(tmp_path)
    manifest_path = tmp_path / "scripts" / "doc_claims.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["claims"][0]["derive"] = "find absent -name '*.py' | wc -l"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="derivation failed"):
        verify_doc_claims(tmp_path)
