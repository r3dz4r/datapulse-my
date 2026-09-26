#!/usr/bin/env python3
"""Verify public Markdown links, generated surfaces, and volatile documentation claims.

Marker-owned blocks and dated statements are legitimate exemptions for volatile
facts.  ``--strict-frontmatter`` becomes the CI default once every registered
Markdown artifact carries ownership front matter; until then those findings are
deliberately visible reports rather than gate failures.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


BANNED_PHRASES = (
    "category-defining",
    "industry-leading",
    "first mover",
    "uncrowded",
    "world-class",
    "best-in-class",
    "revolutionary",
    "regulator-approved",
    "cryptographically proves the truth",
)
REQUIRED_FRONT_MATTER = ("audience", "canonical", "volatility", "owner", "review_trigger", "last_verified")
INLINE_LINK = re.compile(r"!?\[[^\]]*\]\(\s*(?:<([^>]+)>|([^\s)]+))")
REFERENCE_LINK = re.compile(r"^\s*\[[^\]]+\]:\s*(?:<([^>]+)>|(\S+))", re.MULTILINE)
AUTO_LINK = re.compile(r"<((?:\.?\.?/)?[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*\.[A-Za-z0-9_-]+(?:#[^ >]+)?)>")
VOLATILE_LITERAL = re.compile(r"\b\d+\s+(?:datasets|tools|statuses)\b", re.IGNORECASE)
DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
MARKER = re.compile(r"<!--\s*(BEGIN|END)\s+.+?\s*-->", re.IGNORECASE)
CHECK_ARGUMENT = re.compile(r"add_argument\s*\(\s*['\"]--check['\"]")

# These scripts have a no-write check that compares their real public outputs.
# The mapping is intentionally injectable so tests never invoke repository generators.
GENERATED_CHECK_COMMANDS: dict[str, tuple[str, ...]] = {
    f"scripts/{name}": (sys.executable, f"scripts/{name}", "--check")
    for name in (
        "gen_public_discovery.py",
        "gen_llms_summary.py",
        "gen_landing_page.py",
        "gen_readme.py",
        "gen_site_nav.py",
        "gen_mcp_reference.py",
    )
}


@dataclass(frozen=True)
class VerificationResult:
    """Diagnostics and whether any fail-capable check found an error."""

    findings: list[str]
    informational: list[str]
    exit_code: int


def _markdown_paths(root: Path) -> list[Path]:
    return sorted((root / "docs").glob("*.md"))


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _local_target(target: str) -> str | None:
    target = target.strip().strip("<>")
    if not target or target.startswith(("http://", "https://", "mailto:", "tel:", "#")):
        return None
    return target.split("#", 1)[0]


def _link_findings(root: Path, path: Path) -> list[str]:
    findings: list[str] = []
    docs_root = (root / "docs").resolve()
    source = path.read_text(encoding="utf-8")
    targets = [match.group(1) or match.group(2) for match in INLINE_LINK.finditer(source)]
    targets.extend(match.group(1) or match.group(2) for match in REFERENCE_LINK.finditer(source))
    targets.extend(match.group(1) for match in AUTO_LINK.finditer(source))
    for raw_target in targets:
        target = _local_target(raw_target)
        if target is None:
            continue
        if Path(target).is_absolute():
            findings.append(f"{_relative(root, path)} -> {raw_target}: absolute filesystem path")
            continue
        candidate = (path.parent / target).resolve()
        if not candidate.is_relative_to(docs_root):
            findings.append(f"{_relative(root, path)} -> {raw_target}: path escapes docs/")
        elif not candidate.exists():
            findings.append(f"{_relative(root, path)} -> {raw_target}")
    return findings


def _terminology_findings(root: Path, path: Path) -> list[str]:
    findings: list[str] = []
    marker_depth = 0
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        for phrase in BANNED_PHRASES:
            if phrase in line.lower():
                findings.append(f"{_relative(root, path)}:{line_number}: banned claim: {phrase}")
        marker_match = MARKER.search(line)
        in_owned_block = marker_depth > 0 or marker_match is not None
        if not in_owned_block and DATE.search(line) is None and "as of" not in line.lower():
            for match in VOLATILE_LITERAL.finditer(line):
                findings.append(f"{_relative(root, path)}:{line_number}: volatile literal: {match.group(0)}")
        if marker_match is not None:
            marker_depth += 1 if marker_match.group(1).upper() == "BEGIN" else -1
            marker_depth = max(marker_depth, 0)
    return findings


def _front_matter_findings(root: Path) -> list[str]:
    config_path = root / "config/public-surfaces.json"
    try:
        artifacts = json.loads(config_path.read_text(encoding="utf-8"))["artifacts"]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as error:
        return [f"REPORT config/public-surfaces.json: cannot read artifacts: {error}"]
    findings: list[str] = []
    for artifact in artifacts:
        if not isinstance(artifact, str) or not artifact.endswith(".md"):
            continue
        path = root / "docs" / artifact.lstrip("/")
        label = f"docs/{artifact.lstrip('/')}"
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            findings.append(f"REPORT {label}: missing front matter (file missing)")
            continue
        if not lines or lines[0] != "---":
            findings.append(f"REPORT {label}: missing front matter")
            continue
        try:
            end = lines.index("---", 1)
        except ValueError:
            findings.append(f"REPORT {label}: missing front matter terminator")
            continue
        keys = {line.split(":", 1)[0].strip() for line in lines[1:end] if ":" in line}
        for key in REQUIRED_FRONT_MATTER:
            if key not in keys:
                findings.append(f"REPORT {label}: missing front matter key: {key}")
    return findings


def _discovered_generators(root: Path) -> set[str]:
    scripts = root / "scripts"
    discovered: set[str] = set()
    for path in scripts.glob("gen_*.py"):
        try:
            if CHECK_ARGUMENT.search(path.read_text(encoding="utf-8")):
                discovered.add(path.relative_to(root).as_posix())
        except OSError:
            continue
    return discovered


def _generated_surface_findings(
    root: Path, generated_checks: Mapping[str, Sequence[str]]
) -> tuple[list[str], list[str]]:
    findings: list[str] = []
    informational: list[str] = []
    discovered = _discovered_generators(root)
    for script in sorted(discovered | set(generated_checks)):
        command = generated_checks.get(script)
        if command is None:
            informational.append(f"skipped (no check mode): {script}")
            continue
        result = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False)
        if result.returncode:
            output = (result.stderr or result.stdout).strip().replace("\n", " | ")
            findings.append(f"{script}: check failed: {output or f'exit {result.returncode}'}")
    for script in sorted((root / "scripts").glob("gen_*.py")):
        relative = script.relative_to(root).as_posix()
        if relative not in discovered:
            informational.append(f"skipped (no check mode): {relative}")
    return findings, informational


def verify(
    root: Path, *, strict_frontmatter: bool = False,
    generated_checks: Mapping[str, Sequence[str]] | None = None,
) -> VerificationResult:
    """Run all documentation checks without changing files."""
    root = root.resolve()
    checks = GENERATED_CHECK_COMMANDS if generated_checks is None else generated_checks
    findings: list[str] = []
    for path in _markdown_paths(root):
        findings.extend(_link_findings(root, path))
        findings.extend(_terminology_findings(root, path))
    generated, informational = _generated_surface_findings(root, checks)
    findings.extend(generated)
    reports = _front_matter_findings(root)
    findings.extend(reports)
    failed = bool([finding for finding in findings if not finding.startswith("REPORT ")])
    if strict_frontmatter and reports:
        failed = True
    return VerificationResult(findings, informational, int(failed))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--strict-frontmatter", action="store_true")
    args = parser.parse_args()
    result = verify(args.root, strict_frontmatter=args.strict_frontmatter)
    for line in result.informational:
        print(line)
    for finding in result.findings:
        print(finding)
    if result.exit_code:
        print("Documentation verification failed.")
    else:
        print("Documentation verification passed (front matter is report-only unless --strict-frontmatter is set).")
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
