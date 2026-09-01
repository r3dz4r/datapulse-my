#!/usr/bin/env python3

import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.fact_lint import CANONICAL_DOCS, lint_documents


def lint_fixture(
    tmp_path: Path,
    *,
    current_text: str | None = None,
    historical_text: str | None = None,
) -> list[str]:
    current_docs: tuple[str, ...] = ()
    historical_docs: tuple[str, ...] = ()

    if current_text is not None:
        (tmp_path / "current.md").write_text(current_text, encoding="utf-8")
        current_docs = ("current.md",)
    if historical_text is not None:
        (tmp_path / "historical.md").write_text(historical_text, encoding="utf-8")
        historical_docs = ("historical.md",)

    return lint_documents(tmp_path, current_docs, historical_docs)


def write_count_surfaces(
    tmp_path: Path, *, tool_count: int = 18, dataset_count: int = 389
) -> None:
    """Write minimal canonical machine surfaces for count-claim tests."""
    (tmp_path / "mcp.json").write_text(
        json.dumps({"tools": [{} for _ in range(tool_count)]}), encoding="utf-8"
    )
    (tmp_path / "datapulse.json").write_text(
        json.dumps({"datasets": [{} for _ in range(dataset_count)]}),
        encoding="utf-8",
    )


def lint_count_fixture(tmp_path: Path, relative_path: str, text: str) -> list[str]:
    """Lint one file against the count surfaces written by a test."""
    path = tmp_path / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return lint_documents(tmp_path, (relative_path,), ())


def test_current_doc_with_stale_economy_count_is_flagged(tmp_path: Path) -> None:
    errors = lint_fixture(tmp_path, current_text="Filters: Economy (45)\n")

    assert errors == [
        "current.md:1: prohibited literal 'Economy (45)' in current doc "
        "(current: 'Economy (134)')"
    ]


def test_current_doc_with_stale_missing_count_is_flagged(tmp_path: Path) -> None:
    errors = lint_fixture(tmp_path, current_text="The audit found 74 missing files.\n")

    assert errors == [
        "current.md:1: prohibited literal '74 missing' in current doc "
        "(current: '0 missing')"
    ]


def test_historical_doc_without_date_stamp_is_flagged(tmp_path: Path) -> None:
    errors = lint_fixture(tmp_path, historical_text="# Historical report\n\nNo date here.\n")

    assert errors == ["historical.md: missing date stamp in first 5 lines"]


def test_historical_doc_with_date_stamp_in_first_five_lines_passes(
    tmp_path: Path,
) -> None:
    errors = lint_fixture(
        tmp_path,
        historical_text="# Historical report\n\nObserved on 2026-08-05.\n",
    )

    assert errors == []


def test_stale_166_dataset_count_is_flagged(tmp_path: Path) -> None:
    errors = lint_fixture(tmp_path, current_text="The registry contains 166 datasets.\n")

    assert errors == [
        "current.md:1: prohibited literal '166 datasets' in current doc "
        "(current: '372 datasets')"
    ]


def test_clean_current_doc_passes(tmp_path: Path) -> None:
    errors = lint_fixture(tmp_path, current_text="The registry contains 372 datasets.\n")

    assert errors == []


def test_stale_tool_count_fails(tmp_path: Path) -> None:
    write_count_surfaces(tmp_path)

    errors = lint_count_fixture(tmp_path, "README.md", "The server has 16 tools.\n")

    assert errors == [
        "README.md:1: claims 16 tools; canonical mcp.json has 18"
    ]


def test_current_tool_count_passes(tmp_path: Path) -> None:
    write_count_surfaces(tmp_path)

    errors = lint_count_fixture(tmp_path, "README.md", "The server has 18 tools.\n")

    assert errors == []


def test_hyphenated_tool_count_flagged(tmp_path: Path) -> None:
    write_count_surfaces(tmp_path)

    errors = lint_count_fixture(tmp_path, "README.md", "The 16-tool surface.\n")

    assert errors == [
        "README.md:1: claims 16 tools; canonical mcp.json has 18"
    ]


def test_stale_dataset_count_fails(tmp_path: Path) -> None:
    write_count_surfaces(tmp_path)

    errors = lint_count_fixture(tmp_path, "README.md", "The registry has 388 datasets.\n")

    assert errors == [
        "README.md:1: claims 388 datasets; canonical datapulse.json has 389"
    ]


def test_current_dataset_count_passes(tmp_path: Path) -> None:
    write_count_surfaces(tmp_path)

    errors = lint_count_fixture(tmp_path, "README.md", "The registry has 389 datasets.\n")

    assert errors == []


def test_notes_directory_exempt(tmp_path: Path) -> None:
    write_count_surfaces(tmp_path)

    errors = lint_count_fixture(
        tmp_path, "notes/2026-09-01-x.md", "The server had 16 tools.\n"
    )

    assert errors == []


def test_historical_audit_document_exempt(tmp_path: Path) -> None:
    write_count_surfaces(tmp_path)

    errors = lint_count_fixture(
        tmp_path, "docs/AUDIT-2026-09-01.md", "The server had 16 tools.\n"
    )

    assert errors == []


def test_generated_block_exempt(tmp_path: Path) -> None:
    write_count_surfaces(tmp_path)

    errors = lint_count_fixture(
        tmp_path,
        "README.md",
        "<!-- BEGIN mcp-tools -->\nThe server has 16 tools.\n<!-- END mcp-tools -->\n",
    )

    assert errors == []


def test_missing_mcp_json_reports_and_skips(tmp_path: Path) -> None:
    (tmp_path / "datapulse.json").write_text(
        '{"datasets": [{}]}\n', encoding="utf-8"
    )

    errors = lint_count_fixture(tmp_path, "README.md", "The server has 16 tools.\n")

    assert errors == ["mcp.json: no tools array"]


def canonical_fixture(tmp_path: Path, quickstart_text: str = "# Quickstart\n") -> list[str]:
    """Create the canonical public-document set plus a minimal manifest."""
    for relative_path in CANONICAL_DOCS:
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            quickstart_text if relative_path.endswith("agent-quickstart.md") else "# Doc\n",
            encoding="utf-8",
        )
    (tmp_path / "datapulse.json").write_text(
        '{"datasets": [{"id": "fuelprice"}]}\n', encoding="utf-8"
    )
    (tmp_path / "mcp.json").write_text('{"tools": [{}]}\n', encoding="utf-8")
    return lint_documents(tmp_path, (), (), canonical_docs=CANONICAL_DOCS)


def test_missing_canonical_document_is_reported(tmp_path: Path) -> None:
    canonical_fixture(tmp_path)
    (tmp_path / "docs/glossary.md").unlink()

    errors = lint_documents(tmp_path, (), (), canonical_docs=CANONICAL_DOCS)

    assert "docs/glossary.md: canonical doc not found" in errors


def test_broken_canonical_relative_link_is_reported(tmp_path: Path) -> None:
    errors = canonical_fixture(tmp_path, "[Missing](missing.md)\n")

    assert errors == [
        "docs/agent-quickstart.md:1: broken relative link 'missing.md'"
    ]


@pytest.mark.parametrize(
    "text, reason",
    [
        ("Use `list_datasets`.\n", "legacy MCP name 'list_datasets'"),
        ('Send {"tool": "get_dataset"}.\n', "legacy direct MCP tool payload"),
    ],
)
def test_legacy_mcp_contract_is_reported(
    tmp_path: Path, text: str, reason: str
) -> None:
    errors = canonical_fixture(tmp_path, text)

    assert errors == [f"docs/agent-quickstart.md:1: {reason}"]


def test_unknown_dataset_id_in_canonical_example_is_reported(tmp_path: Path) -> None:
    errors = canonical_fixture(tmp_path, 'Use dataset_id: "missing-dataset".\n')

    assert errors == [
        "docs/agent-quickstart.md:1: unknown dataset ID 'missing-dataset' "
        "in canonical example"
    ]


def test_clean_canonical_documents_pass(tmp_path: Path) -> None:
    errors = canonical_fixture(tmp_path, 'Use dataset_id: "fuelprice".\n')

    assert errors == []


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
