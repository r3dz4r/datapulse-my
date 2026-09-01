#!/usr/bin/env python3
"""Reject stale operational facts while preserving dated historical artifacts."""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
from pathlib import Path
from typing import Iterable, Sequence
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]

CURRENT_DOCS = (
    "README.md",
    "CONTRIBUTING.md",
    "docs/architecture.md",
    "docs/release-process.md",
    "docs/operations.md",
    "docs/troubleshooting.md",
    "docs/health-methodology.md",
    "docs/mcp-reference.md",
    "docs/mcp-deploy.md",
    "docs/adoption-seeding.md",
    "docs/ai-directory-listings.md",
    "llms.txt",
    "mcp.json",
)

HISTORICAL_DOCS = (
    "docs/AUDIT-2026-08-05.md",
    "docs/data-json-workspace-proposal-2026-08-08.md",
    "docs/health-compatibility-report-2026-08-08.md",
    "docs/mcp-self-grade-2026-08-08.md",
)

CANONICAL_DOCS = (
    "docs/documentation-map.md",
    "docs/source-of-truth-map.md",
    "docs/glossary.md",
    "docs/trust-contract.md",
    "docs/status-semantics.md",
    "docs/evidence-receipt-spec.md",
    "docs/agent-quickstart.md",
    "docs/agent-workflows.md",
    "docs/dataset-lifecycle.md",
    "docs/incident-response.md",
    "docs/reproducibility.md",
    "docs/enterprise-governance.md",
    "docs/integration-patterns.md",
)

LEGACY_MCP_NAMES = (
    "list_datasets",
    "get_health_snapshot",
    "get_attestation",
    "list_machine_surfaces",
)

PROHIBITED_LITERALS = (
    ("92 envelopes", "305 envelopes"),
    ("136 envelopes", "305 envelopes"),
    ("122 dataset", "372 datasets"),
    ("122-dataset", "372-dataset"),
    ("166 datasets", "372 datasets"),
    ("166-dataset", "372-dataset"),
    ("Economy (45)", "Economy (134)"),
    ("Economy (70)", "Economy (134)"),
    ("Transport (30)", "Transport (48)"),
    ("Transport (37)", "Transport (48)"),
    ("Environment (3)", "Environment (12)"),
    ("Environment (5)", "Environment (12)"),
    ("Healthcare (1)", "Healthcare (28)"),
    ("Healthcare (11)", "Healthcare (28)"),
    ("74 missing", "0 missing"),
    ("74-file gap", "0-file gap"),
    (
        "as-required datasets age automatically",
        "as-required datasets do not age automatically",
    ),
    (
        "data.gov.my has been down",
        "dataset availability is evaluated per probe",
    ),
)

DATE_STAMP = re.compile(r"202[56]-\d{2}-\d{2}")
LITERAL_PATTERNS = tuple(
    (
        literal,
        current_value,
        re.compile(rf"(?<!\w){re.escape(literal)}(?!\w)"),
    )
    for literal, current_value in PROHIBITED_LITERALS
)
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
LEGACY_DIRECT_TOOL_PAYLOAD = re.compile(r'\{\s*"tool"\s*:')
DATASET_ID_ARGUMENT = re.compile(
    r"\bdataset_id\s*[:=]\s*[\"`]([a-z0-9][a-z0-9_-]*)[\"`]"
)
DATASET_MARKDOWN_PATH = re.compile(r"(?:^|/)data/([a-z0-9][a-z0-9_-]*)\.md$")


def is_excluded(path: str, exclude_globs: Sequence[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in exclude_globs)


def line_number(text: str, position: int) -> int:
    """Return the one-based line number at ``position`` in ``text``."""
    return text.count("\n", 0, position) + 1


def relative_link_target(link: str) -> str | None:
    """Return a local link target, excluding URLs and fragment-only links."""
    target = link.strip().split(maxsplit=1)[0].strip("<>")
    if not target or target.startswith(("#", "//")) or urlparse(target).scheme:
        return None
    return target.split("#", maxsplit=1)[0].split("?", maxsplit=1)[0]


def manifest_dataset_ids(root: Path) -> set[str] | None:
    """Load canonical dataset identifiers, or return ``None`` for no manifest."""
    path = root / "datapulse.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        dataset["id"]
        for dataset in payload.get("datasets", [])
        if isinstance(dataset, dict) and isinstance(dataset.get("id"), str)
    }


def lint_canonical_documents(
    root: Path,
    canonical_docs: Iterable[str],
    exclude_globs: Sequence[str],
) -> list[str]:
    """Return link, legacy-contract, and dataset-example findings."""
    findings: list[str] = []
    existing_docs: list[tuple[str, Path, str]] = []
    for relative_path in canonical_docs:
        if is_excluded(relative_path, exclude_globs):
            continue
        path = root / relative_path
        if not path.is_file():
            findings.append(f"{relative_path}: canonical doc not found")
            continue
        existing_docs.append((relative_path, path, path.read_text(encoding="utf-8")))

    dataset_ids = manifest_dataset_ids(root)
    if existing_docs and dataset_ids is None:
        findings.append("datapulse.json: dataset manifest not found")

    for relative_path, path, text in existing_docs:
        for match in MARKDOWN_LINK.finditer(text):
            target = relative_link_target(match.group(1))
            if target is None:
                continue
            resolved = path.parent / target
            if not resolved.is_file():
                findings.append(
                    f"{relative_path}:{line_number(text, match.start(1))}: "
                    f"broken relative link '{target}'"
                )
        for legacy_name in LEGACY_MCP_NAMES:
            for match in re.finditer(rf"(?<!\w){re.escape(legacy_name)}(?!\w)", text):
                findings.append(
                    f"{relative_path}:{line_number(text, match.start())}: "
                    f"legacy MCP name '{legacy_name}'"
                )
        for match in LEGACY_DIRECT_TOOL_PAYLOAD.finditer(text):
            findings.append(
                f"{relative_path}:{line_number(text, match.start())}: "
                "legacy direct MCP tool payload"
            )
        for literal, current_value, pattern in LITERAL_PATTERNS:
            for match in pattern.finditer(text):
                findings.append(
                    f"{relative_path}:{line_number(text, match.start())}: prohibited "
                    f"literal '{literal}' in canonical doc (current: '{current_value}')"
                )
        if dataset_ids is not None:
            examples = [
                *(
                    (match.group(1), match.start(1))
                    for match in DATASET_ID_ARGUMENT.finditer(text)
                ),
                *(
                    (match.group(1), match.start(1))
                    for match in DATASET_MARKDOWN_PATH.finditer(text)
                ),
            ]
            for dataset_id, position in examples:
                if dataset_id not in dataset_ids:
                    findings.append(
                        f"{relative_path}:{line_number(text, position)}: unknown "
                        f"dataset ID '{dataset_id}' in canonical example"
                    )
    return findings


def lint_documents(
    root: Path,
    current_docs: Iterable[str] = CURRENT_DOCS,
    historical_docs: Iterable[str] = HISTORICAL_DOCS,
    exclude_globs: Sequence[str] = (),
    canonical_docs: Iterable[str] = (),
) -> list[str]:
    """Return deterministic fact-lint findings for files below ``root``."""
    findings: list[str] = []

    for relative_path in current_docs:
        if is_excluded(relative_path, exclude_globs):
            continue
        path = root / relative_path
        if not path.is_file():
            findings.append(f"{relative_path}: current doc not found")
            continue
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            for literal, current_value, pattern in LITERAL_PATTERNS:
                if pattern.search(line):
                    findings.append(
                        f"{relative_path}:{line_number}: prohibited literal "
                        f"'{literal}' in current doc (current: '{current_value}')"
                    )

    for relative_path in historical_docs:
        if is_excluded(relative_path, exclude_globs):
            continue
        path = root / relative_path
        if not path.is_file():
            findings.append(f"{relative_path}: historical doc not found")
            continue
        first_five_lines = "\n".join(
            path.read_text(encoding="utf-8").splitlines()[:5]
        )
        if not DATE_STAMP.search(first_five_lines):
            findings.append(f"{relative_path}: missing date stamp in first 5 lines")

    findings.extend(lint_canonical_documents(root, canonical_docs, exclude_globs))
    return findings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Lint current documentation for stale facts."
    )
    parser.add_argument(
        "--exclude",
        default="",
        help="comma-separated file globs to skip",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="repository root to lint (default: this script's repository)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    exclude_globs = tuple(
        pattern.strip() for pattern in args.exclude.split(",") if pattern.strip()
    )
    findings = lint_documents(
        args.root,
        exclude_globs=exclude_globs,
        canonical_docs=CANONICAL_DOCS,
    )
    for finding in findings:
        print(finding)
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
