#!/usr/bin/env python3
"""Fail closed when current discovery surfaces disagree with canonical counts."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

try:
    from scripts.embed_dashboard_data import NPRA_DATASET_IDS
except ModuleNotFoundError:  # Direct script execution puts scripts/ on sys.path.
    from embed_dashboard_data import NPRA_DATASET_IDS


ROOT = Path(__file__).resolve().parents[1]
ROOT_SURFACES = (
    "README.md",
    "llms.txt",
    "agent.json",
    "mcp.json",
    "server.json",
    "glama.json",
    "docs/mcp-reference.md",
    "docs/ai-directory-listings.md",
)
CANONICAL_EVIDENCE = frozenset({"datapulse.json", "health/latest.json"})
VERTICAL_DATASET_IDS_BY_SURFACE = {
    "docs/npra.html": NPRA_DATASET_IDS,
}
HISTORICAL_PATH_PATTERNS = (
    "docs/AUDIT-*.md",
    "docs/DESIGN-AUDIT-*.md",
    "docs/*-20??-??-??.md",
    "docs/field-notes/**",
    "notes/**",
    "archive/**",
)
DATASET_CLAIM = re.compile(
    r"(?<!\w)(\d{1,7})\s*(?:[-–]\s*)?"
    r"(?:(?:official|Malaysian|public|current|manifest|catalogue|catalog)\s+){0,4}datasets?\b",
    re.IGNORECASE,
)
TOOL_CLAIM = re.compile(
    r"(?<!\w)(\d{1,7})\s*(?:[-–]\s*)?"
    r"(?:(?:read-only|MCP|advertised|canonical)\s+){0,3}tools?\b",
    re.IGNORECASE,
)


class DistributionSyncError(Exception):
    """Raised when canonical evidence cannot be safely read."""


@dataclass(frozen=True)
class DistributionSyncReport:
    """Current-surface verification result with operator remediation context."""

    dataset_count: int
    tool_count: int
    checked_surfaces: list[str]
    excluded_historical_paths: list[str]
    failures: list[str]


def _load_object(path: Path) -> dict[str, Any]:
    """Load a JSON object or fail before checking any public claim."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DistributionSyncError(f"missing canonical input: {path}") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DistributionSyncError(f"cannot read JSON input {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise DistributionSyncError(f"{path}: expected a JSON object")
    return value


def _canonical_counts(root: Path) -> tuple[int, int]:
    """Return canonical counts from the manifest and MCP advertisement arrays."""
    manifest = _load_object(root / "datapulse.json")
    _load_object(root / "health/latest.json")
    advertisement = _load_object(root / "mcp.json")
    datasets = manifest.get("datasets")
    tools = advertisement.get("tools")
    if not isinstance(datasets, list):
        raise DistributionSyncError("datapulse.json: datasets must be an array")
    if not isinstance(tools, list):
        raise DistributionSyncError("mcp.json: tools must be an array")
    return len(datasets), len(tools)


def _is_historical(relative_path: str) -> bool:
    """Keep dated records and operator notes outside the current-surface scope."""
    candidate = Path(relative_path)
    return any(candidate.match(pattern) for pattern in HISTORICAL_PATH_PATTERNS)


def _configured_surface_paths(root: Path) -> set[Path]:
    """Resolve existing current pages/artifacts declared by public-surfaces.json."""
    config_path = root / "config/public-surfaces.json"
    if not config_path.is_file():
        return set()
    config = _load_object(config_path)
    configured: set[Path] = set()
    for key in ("pages", "artifacts"):
        values = config.get(key, [])
        if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
            raise DistributionSyncError(f"config/public-surfaces.json: {key} must be an array of paths")
        for value in values:
            if value == "/":
                candidates = (root / "docs/index.html",)
            else:
                relative = value.lstrip("/")
                if not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
                    raise DistributionSyncError(f"config/public-surfaces.json: unsafe public path {value!r}")
                candidates = (root / relative, root / "docs" / relative)
            configured.update(path for path in candidates if path.is_file())
    return configured


def current_surface_paths(root: Path) -> tuple[list[Path], list[str]]:
    """Return explicit current surfaces, never a repository-wide content scan."""
    candidates = {root / relative for relative in ROOT_SURFACES}
    candidates.update(_configured_surface_paths(root))
    cards_dir = root / "docs/mcp/cards"
    if cards_dir.is_dir():
        candidates.update(cards_dir.glob("*.json"))
    checked: list[Path] = []
    excluded: list[str] = []
    for path in sorted(candidates, key=lambda item: item.as_posix()):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative in CANONICAL_EVIDENCE:
            continue
        if _is_historical(relative):
            excluded.append(relative)
            continue
        checked.append(path)
    docs = root / "docs"
    if docs.is_dir():
        for pattern in HISTORICAL_PATH_PATTERNS:
            if not pattern.startswith("docs/"):
                continue
            excluded.extend(
                path.relative_to(root).as_posix()
                for path in root.glob(pattern)
                if path.is_file() and path.relative_to(root).as_posix() not in excluded
            )
    return checked, sorted(excluded)


def _string_claims(value: Any, path: str = "$") -> Iterator[tuple[str, str]]:
    """Yield strings in structured surfaces with a stable JSON-style location."""
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _string_claims(item, f"{path}[{index}]")
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _string_claims(item, f"{path}.{key}")


def _structured_count_failures(value: Any, dataset_count: int, tool_count: int, path: str = "$") -> list[str]:
    """Validate documented numeric count fields in JSON discovery surfaces."""
    failures: list[str] = []
    if isinstance(value, list):
        for index, item in enumerate(value):
            failures.extend(_structured_count_failures(item, dataset_count, tool_count, f"{path}[{index}]"))
    elif isinstance(value, dict):
        for key, item in value.items():
            location = f"{path}.{key}"
            expected: int | None = None
            label = ""
            if key == "dataset_count":
                expected, label = dataset_count, "dataset_count"
            elif key == "tool_count" or (key == "tools" and isinstance(item, int)):
                expected, label = tool_count, "tool count"
            if expected is not None and (not isinstance(item, int) or isinstance(item, bool) or item != expected):
                failures.append(f"{location}: {label} is {item!r}; canonical value is {expected}")
            failures.extend(_structured_count_failures(item, dataset_count, tool_count, location))
    return failures


def _prose_count_failures(text: str, dataset_count: int, tool_count: int) -> list[str]:
    """Return stale dataset/tool count claims from prose without matching ranges."""
    failures: list[str] = []
    for pattern, expected, label in ((DATASET_CLAIM, dataset_count, "datasets"), (TOOL_CLAIM, tool_count, "tools")):
        for match in pattern.finditer(text):
            claimed = int(match.group(1))
            if claimed != expected:
                failures.append(f"claims {claimed} {label}; canonical value is {expected}")
    return failures


def _dataset_count_for_surface(relative_path: str, catalogue_count: int) -> int:
    """Return the catalogue or explicitly registered vertical dataset count."""
    vertical_dataset_ids = VERTICAL_DATASET_IDS_BY_SURFACE.get(relative_path)
    return len(vertical_dataset_ids) if vertical_dataset_ids is not None else catalogue_count


def _surface_failures(path: Path, root: Path, dataset_count: int, tool_count: int) -> list[str]:
    """Validate one current surface's structured fields and human-readable claims."""
    relative = path.relative_to(root).as_posix()
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return [f"{relative}: cannot read current surface: {exc}"]
    surface_dataset_count = _dataset_count_for_surface(relative, dataset_count)
    failures = [
        f"{relative}: {message}"
        for message in _prose_count_failures(text, surface_dataset_count, tool_count)
    ]
    if path.suffix == ".json":
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            return failures + [f"{relative}: invalid JSON: {exc.msg}"]
        failures.extend(
            f"{relative}: {message}"
            for message in _structured_count_failures(value, surface_dataset_count, tool_count)
        )
        for location, claim in _string_claims(value):
            for message in _prose_count_failures(claim, surface_dataset_count, tool_count):
                failures.append(f"{relative}:{location}: {message}")
    return sorted(set(failures))


def verify_distribution_sync(root: Path) -> DistributionSyncReport:
    """Verify that explicit current discovery surfaces match canonical evidence."""
    root = root.resolve()
    dataset_count, tool_count = _canonical_counts(root)
    paths, excluded = current_surface_paths(root)
    failures = [failure for path in paths for failure in _surface_failures(path, root, dataset_count, tool_count)]
    return DistributionSyncReport(
        dataset_count=dataset_count,
        tool_count=tool_count,
        checked_surfaces=[path.relative_to(root).as_posix() for path in paths],
        excluded_historical_paths=excluded,
        failures=sorted(failures),
    )


def _remediation(path: str) -> str:
    """Return the existing generator or safe operator action for one stale surface."""
    if path.startswith("docs/mcp/cards/") or path == "docs/ai-catalog.json":
        return "python3 scripts/gen_ai_catalog.py"
    if path in {"mcp.json", "agent.json", "docs/mcp-reference.md"}:
        return "python3 scripts/gen_mcp_reference.py"
    if path in {"README.md", "llms.txt"}:
        return "python3 scripts/gen_mcp_reference.py && python3 scripts/gen_llms_summary.py"
    if path in {"docs/index.html", "docs/npra.html"}:
        return "python3 scripts/embed_dashboard_data.py"
    return "update this hand-authored current surface to remove or derive the stale claim"


def _print_report(report: DistributionSyncReport) -> None:
    """Print concise remediation evidence for release operators."""
    print("Distribution synchronization verification")
    print(f"Canonical evidence: {report.dataset_count} datasets; {report.tool_count} MCP tools")
    print("Checked current surfaces:")
    for path in report.checked_surfaces:
        print(f"- {path}")
    print("Excluded historical paths:")
    if report.excluded_historical_paths:
        for path in report.excluded_historical_paths:
            print(f"- {path}")
    else:
        print("- none matched explicit historical exclusion rules")
    if not report.failures:
        print("Result: current distribution surfaces match canonical evidence.")
        return
    print(f"Failures ({len(report.failures)}):")
    remediations: dict[str, str] = {}
    for failure in report.failures:
        path = failure.split(":", 1)[0]
        remediations[path] = _remediation(path)
        print(f"- {failure}")
    print("Remediation:")
    for path, command in sorted(remediations.items()):
        print(f"- {path}: {command}")


def main() -> int:
    """Run the read-only current-surface synchronization verifier."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        report = verify_distribution_sync(args.root)
    except DistributionSyncError as exc:
        print(f"Distribution synchronization verifier input error: {exc}")
        return 2
    _print_report(report)
    return 1 if report.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
