#!/usr/bin/env python3
"""Fail closed when derivative OpenWiki documentation escapes its contract."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    # Direct execution puts scripts/, rather than the repository root, on sys.path.
    sys.path.insert(0, str(ROOT))

from scripts.public_surface_generation import GenerationError, load_public_surfaces


GENERATED_PATHS = frozenset(
    {
        "openwiki/quickstart.md",
        "openwiki/datasets.md",
        "openwiki/mcp.md",
        "openwiki/operations.md",
        "openwiki/.last-update.json",
    }
)
MANAGED_INSTRUCTION_PATHS = frozenset({"AGENTS.md", "CLAUDE.md"})
REQUIRED_PAGES = GENERATED_PATHS - {"openwiki/.last-update.json"}
FORBIDDEN_CLAIMS = (
    "universal trust",
    "payment capability",
    "agent reputation",
    "regulatory certification",
)
_DATASET_COUNT_RE = re.compile(r"\b(?P<count>\d+)(?=[ -]datasets?\b)", re.IGNORECASE)
_READ_ONLY_TOOL_COUNT_RE = re.compile(r"\b(?P<count>\d+)(?=[ -]read-only[ -]tools?\b)", re.IGNORECASE)
_TOOL_COUNT_RE = re.compile(r"\b(?P<count>\d+)(?=[ -]tools?\b)", re.IGNORECASE)


class VerificationError(Exception):
    """Raised when a generated documentation contract is violated."""


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise VerificationError(f"cannot read {path}: {error}") from error
    if not isinstance(value, dict):
        raise VerificationError(f"{path} must contain a JSON object")
    return value


def _facts(root: Path) -> tuple[str, str, int, int]:
    try:
        public = load_public_surfaces(root)
        website = public["origins"]["website"]
        product_name = public["product_name"]
    except GenerationError as error:
        raise VerificationError(str(error)) from error
    manifest = _load_object(root / "datapulse.json")
    mcp = _load_object(root / "mcp.json")
    datasets = manifest.get("datasets")
    tools = mcp.get("tools")
    if not isinstance(datasets, list) or not datasets:
        raise VerificationError("datapulse.json must contain a non-empty datasets array")
    if not isinstance(tools, list) or not tools:
        raise VerificationError("mcp.json must contain a non-empty tools array")
    return product_name, website, len(datasets), len(tools)


def _has_stale_count(text: str, current: int, pattern: re.Pattern[str]) -> bool:
    return any(int(match.group("count")) != current for match in pattern.finditer(text))


def _changed_paths(root: Path, base: str) -> set[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", base], cwd=root, capture_output=True, text=True, check=False
    )
    if result.returncode:
        raise VerificationError(f"cannot read generated path diff from {base}: {result.stderr.strip()}")
    return {line for line in result.stdout.splitlines() if line}


def _managed_instruction_change(root: Path, base: str, relative: str) -> bool:
    """Allow only an explicit OpenWiki marker/pointer block in instruction files."""
    original = subprocess.run(["git", "show", f"{base}:{relative}"], cwd=root, capture_output=True, text=True, check=False)
    if original.returncode:
        return False
    try:
        updated = (root / relative).read_text(encoding="utf-8")
    except OSError:
        return False
    marker = re.compile(r"(?ims)^<!-- BEGIN OPENWIKI(?: [A-Z0-9_-]+)? -->.*?^<!-- END OPENWIKI(?: [A-Z0-9_-]+)? -->\n?")
    pointer = re.compile(r"(?im)^<!-- OPENWIKI(?: [A-Z0-9_-]+)? -->\n?")
    return pointer.sub("", marker.sub("", original.stdout)) == pointer.sub("", marker.sub("", updated))


def verify(root: Path, *, generated: bool, changed_from: str | None = None) -> None:
    """Verify canonical facts and the derivative-output ownership boundary."""
    product_name, website, datasets, tools = _facts(root)
    instructions = root / "openwiki/INSTRUCTIONS.md"
    if not instructions.is_file() or website not in instructions.read_text(encoding="utf-8"):
        raise VerificationError("openwiki/INSTRUCTIONS.md must name the canonical website origin")
    if changed_from is not None:
        changed = _changed_paths(root, changed_from)
        forbidden = changed - GENERATED_PATHS - MANAGED_INSTRUCTION_PATHS
        if forbidden:
            raise VerificationError("OpenWiki changed disallowed path(s): " + ", ".join(sorted(forbidden)))
        unmanaged = [path for path in changed & MANAGED_INSTRUCTION_PATHS if not _managed_instruction_change(root, changed_from, path)]
        if unmanaged:
            raise VerificationError("OpenWiki changed non-managed instruction content: " + ", ".join(sorted(unmanaged)))
    if not generated:
        return
    missing = [path for path in sorted(REQUIRED_PAGES) if not (root / path).is_file()]
    if missing:
        raise VerificationError("missing generated OpenWiki page(s): " + ", ".join(missing))
    required_facts = (product_name, website, f"{datasets} datasets", f"{tools} read-only tools")
    for relative in sorted(REQUIRED_PAGES):
        text = (root / relative).read_text(encoding="utf-8")
        folded = text.casefold()
        if "datapulse my" in folded:
            raise VerificationError(f"{relative} uses the obsolete public product name")
        if "https://data-pulse.my" in text:
            raise VerificationError(f"{relative} uses the obsolete apex website origin")
        if any(claim in folded for claim in FORBIDDEN_CLAIMS):
            raise VerificationError(f"{relative} contains an unsupported claim")
        if _has_stale_count(text, datasets, _DATASET_COUNT_RE):
            raise VerificationError(f"{relative} contains stale dataset count facts")
        stale_tool_count = _has_stale_count(text, tools, _READ_ONLY_TOOL_COUNT_RE) or _has_stale_count(
            text, tools, _TOOL_COUNT_RE
        )
        if stale_tool_count:
            raise VerificationError(f"{relative} contains stale MCP tool count facts")
        if not all(fact in text for fact in required_facts):
            raise VerificationError(f"{relative} is missing canonical current facts")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generated", action="store_true", help="Validate rendered pages as well as source ownership.")
    parser.add_argument("--changed-from", help="Git revision used to check the generated output allowlist.")
    args = parser.parse_args()
    try:
        verify(ROOT, generated=args.generated, changed_from=args.changed_from)
    except VerificationError as error:
        print(f"OpenWiki verification failed: {error}", file=sys.stderr)
        return 1
    print("OpenWiki verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
