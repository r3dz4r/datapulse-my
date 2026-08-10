#!/usr/bin/env python3
"""Reject stale operational facts while preserving dated historical artifacts."""

from __future__ import annotations

import argparse
import fnmatch
import re
from pathlib import Path
from typing import Iterable, Sequence


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

PROHIBITED_LITERALS = (
    ("92 envelopes", "305 envelopes"),
    ("136 envelopes", "305 envelopes"),
    ("122 dataset", "364 datasets"),
    ("122-dataset", "364-dataset"),
    ("166 datasets", "364 datasets"),
    ("166-dataset", "364-dataset"),
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


def is_excluded(path: str, exclude_globs: Sequence[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in exclude_globs)


def lint_documents(
    root: Path,
    current_docs: Iterable[str] = CURRENT_DOCS,
    historical_docs: Iterable[str] = HISTORICAL_DOCS,
    exclude_globs: Sequence[str] = (),
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    exclude_globs = tuple(
        pattern.strip() for pattern in args.exclude.split(",") if pattern.strip()
    )
    findings = lint_documents(ROOT, exclude_globs=exclude_globs)
    for finding in findings:
        print(finding)
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
