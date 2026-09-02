#!/usr/bin/env python3
"""Reject stale operational facts while preserving dated historical artifacts."""

from __future__ import annotations

import argparse
from datetime import date
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

AGENT_DOCS = (
    "AGENTS.md",
    "mcp/AGENTS.md",
    "docs/AGENTS.md",
    "scripts/AGENTS.md",
    "docs/trust-layer-notebook.AGENTS.md",
)

COUNT_SCOPE = frozenset((*CURRENT_DOCS, *CANONICAL_DOCS, *AGENT_DOCS))

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
TOOL_COUNT_MENTION = re.compile(r"(?<![\d.])(\d{1,3})[ -]tools?\b")
DATASET_COUNT_MENTION = re.compile(r"(?<![\d.])(\d{1,4})[ -]datasets?\b")

REQUIRED_CLAIM_FIELDS = (
    "claim_id",
    "phrase_pattern",
    "verification_mode",
    "scope_statement",
    "evidence_source",
    "last_audit_date",
    "re_audit_trigger",
)
CLAIM_VERIFICATION_MODES = frozenset(
    {
        "forbidden_in_canonical",
        "allowed_in_canonical",
        "context_allowed",
        "allowed_in_statistical",
    }
)
CONTEXT_QUALIFIERS = {
    "authoritative-claim": frozenset({"registry", "catalogue", "machine", "marker"}),
}


def is_excluded(path: str, exclude_globs: Sequence[str]) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in exclude_globs)


def claim_glob_matches(path: str, pattern: str) -> bool:
    """Match a claim-ledger path glob, with ``**/`` also matching no directory."""
    return fnmatch.fnmatchcase(path, pattern) or fnmatch.fnmatchcase(
        path, pattern.replace("**/", "")
    )


def claim_scope_paths(root: Path, globs: Sequence[str]) -> set[str]:
    """Return top-level public-document paths selected by claim-ledger globs."""
    paths: set[str] = set()
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative_path = path.relative_to(root).as_posix()
        if relative_path in HISTORICAL_DOCS:
            continue
        if relative_path.startswith("docs/") and "/" in relative_path[5:]:
            continue
        if any(claim_glob_matches(relative_path, pattern) for pattern in globs):
            paths.add(relative_path)
    return paths


def occurrence_is_allowlisted(
    allowed_occurrences: object, relative_path: str, number: int
) -> bool:
    """Return whether one match has an exact ledger occurrence annotation."""
    if not isinstance(allowed_occurrences, list):
        return False
    for occurrence in allowed_occurrences:
        if not isinstance(occurrence, dict) or occurrence.get("path") != relative_path:
            continue
        annotation = occurrence.get("line_range_or_pattern")
        if isinstance(annotation, str) and re.search(rf"\bline {number}\b", annotation):
            return True
    return False


def has_scope_qualifier(text: str, position: int, claim_id: str) -> bool:
    """Return whether a context-controlled claim is locally scope-qualified."""
    qualifiers = CONTEXT_QUALIFIERS.get(claim_id, frozenset())
    context = text[max(0, position - 120) : position + 120]
    nearby_words = re.findall(r"[A-Za-z]+", context)
    if any(word.lower() in qualifiers for word in nearby_words):
        return True
    preceding_words = re.findall(r"[A-Za-z]+", text[max(0, position - 40) : position])
    return "not" in {word.lower() for word in preceding_words[-3:]}


def check_claims(root: Path, ledger_path: Path) -> list[str]:
    """Return claim-ledger schema and scope violations below ``root``."""
    findings: list[str] = []
    try:
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [f"{ledger_path}: claim ledger not found"]
    except json.JSONDecodeError as error:
        return [f"{ledger_path}: invalid JSON: {error.msg}"]

    claims = ledger.get("claims") if isinstance(ledger, dict) else None
    if not isinstance(claims, list):
        return [f"{ledger_path}: top-level 'claims' must be a list"]

    for index, claim in enumerate(claims, start=1):
        label = f"claim record {index}"
        if not isinstance(claim, dict):
            findings.append(f"{label}: must be an object")
            continue
        for field in REQUIRED_CLAIM_FIELDS:
            if not isinstance(claim.get(field), str) or not claim[field].strip():
                findings.append(f"{label}: missing required field '{field}'")
        if not isinstance(claim.get("allowed_occurrences"), list):
            findings.append(f"{label}: 'allowed_occurrences' must be a list")
        if not isinstance(claim.get("forbidden_in"), list):
            findings.append(f"{label}: 'forbidden_in' must be a list")
        mode = claim.get("verification_mode")
        if isinstance(mode, str) and mode not in CLAIM_VERIFICATION_MODES:
            findings.append(f"{label}: invalid verification_mode '{mode}'")
        audit_date = claim.get("last_audit_date")
        if isinstance(audit_date, str) and audit_date:
            try:
                date.fromisoformat(audit_date)
            except ValueError:
                findings.append(
                    f"{label}: invalid last_audit_date '{audit_date}'"
                )
        pattern = claim.get("phrase_pattern")
        if isinstance(pattern, str) and pattern:
            try:
                re.compile(pattern, re.IGNORECASE)
            except re.error as error:
                findings.append(f"{label}: invalid phrase_pattern: {error}")

    if findings:
        return findings

    for claim in claims:
        assert isinstance(claim, dict)
        pattern = re.compile(claim["phrase_pattern"], re.IGNORECASE)
        mode = claim["verification_mode"]
        forbidden_in = claim["forbidden_in"]
        allowed_occurrences = claim["allowed_occurrences"]
        if mode in {"forbidden_in_canonical", "allowed_in_canonical"}:
            paths = set(CURRENT_DOCS)
        elif mode == "context_allowed":
            paths = set(CURRENT_DOCS)
            paths.update(claim_scope_paths(root, forbidden_in))
            paths.update(
                occurrence["path"]
                for occurrence in allowed_occurrences
                if isinstance(occurrence, dict)
                and isinstance(occurrence.get("path"), str)
            )
        else:
            paths = claim_scope_paths(root, forbidden_in)

        for relative_path in sorted(paths):
            path = root / relative_path
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
            for match in pattern.finditer(text):
                number = line_number(text, match.start())
                phrase = match.group(0)
                if mode == "forbidden_in_canonical":
                    findings.append(
                        f"{relative_path}:{number}: forbidden claim phrase '{phrase}' "
                        f"({claim['claim_id']})"
                    )
                elif mode == "allowed_in_canonical":
                    if not occurrence_is_allowlisted(
                        allowed_occurrences, relative_path, number
                    ):
                        findings.append(
                            f"{relative_path}:{number}: unallowlisted claim phrase "
                            f"'{phrase}' ({claim['claim_id']})"
                        )
                elif mode == "context_allowed":
                    if not occurrence_is_allowlisted(
                        allowed_occurrences, relative_path, number
                    ) and not has_scope_qualifier(
                        text, match.start(), claim["claim_id"]
                    ):
                        findings.append(
                            f"{relative_path}:{number}: unscoped claim phrase "
                            f"'{phrase}' ({claim['claim_id']})"
                        )
                elif any(
                    claim_glob_matches(relative_path, glob) for glob in forbidden_in
                ):
                    findings.append(
                        f"{relative_path}:{number}: forbidden claim phrase '{phrase}' "
                        f"({claim['claim_id']})"
                    )
    return findings


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


def canonical_array_count(root: Path, filename: str, key: str) -> int | None:
    """Return a canonical JSON array's count, or ``None`` when it is absent/empty."""
    path = root / filename
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    values = payload.get(key) if isinstance(payload, dict) else None
    return len(values) if isinstance(values, list) and values else None


def lint_count_claims(
    text: str,
    relative_path: str,
    tool_count: int | None,
    dataset_count: int | None,
) -> list[str]:
    """Return stale canonical tool and dataset count claims in one document."""
    findings: list[str] = []
    in_generated_mcp_tools = False
    for number, line in enumerate(text.splitlines(), start=1):
        if "<!-- BEGIN mcp-tools -->" in line:
            in_generated_mcp_tools = True
        if not in_generated_mcp_tools:
            lowered = line.lower()
            canonical_jq_reference = (
                "canonical" in lowered
                and "jq" in lowered
                and ("mcp.json" in lowered or "datapulse.json" in lowered)
            )
            if not canonical_jq_reference:
                if tool_count is not None:
                    for match in TOOL_COUNT_MENTION.finditer(line):
                        claimed_count = int(match.group(1))
                        if claimed_count != tool_count:
                            findings.append(
                                f"{relative_path}:{number}: claims {claimed_count} tools; "
                                f"canonical mcp.json has {tool_count}"
                            )
                if dataset_count is not None:
                    for match in DATASET_COUNT_MENTION.finditer(line):
                        claimed_count = int(match.group(1))
                        if claimed_count != dataset_count:
                            findings.append(
                                f"{relative_path}:{number}: claims {claimed_count} datasets; "
                                f"canonical datapulse.json has {dataset_count}"
                            )
        if "<!-- END mcp-tools -->" in line:
            in_generated_mcp_tools = False
    return findings


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

    current_docs = tuple(current_docs)
    canonical_docs = tuple(canonical_docs)

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

    count_documents = dict.fromkeys((*current_docs, *canonical_docs, *AGENT_DOCS))
    scoped_count_documents = tuple(
        relative_path
        for relative_path in count_documents
        if relative_path in COUNT_SCOPE and not is_excluded(relative_path, exclude_globs)
    )
    existing_count_documents = tuple(
        relative_path
        for relative_path in scoped_count_documents
        if (root / relative_path).is_file()
    )
    if existing_count_documents:
        tool_count = canonical_array_count(root, "mcp.json", "tools")
        dataset_count = canonical_array_count(root, "datapulse.json", "datasets")
        if tool_count is None:
            findings.append("mcp.json: no tools array")
        if dataset_count is None:
            findings.append("datapulse.json: no datasets array")
        for relative_path in existing_count_documents:
            findings.extend(
                lint_count_claims(
                    (root / relative_path).read_text(encoding="utf-8"),
                    relative_path,
                    tool_count,
                    dataset_count,
                )
            )
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
    parser.add_argument(
        "--check-claims",
        action="store_true",
        help="validate the claim ledger and check controlled claim scope",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check_claims:
        findings = check_claims(args.root, args.root / "claims" / "claims.json")
        for finding in findings:
            print(finding)
        return 1 if findings else 0
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
