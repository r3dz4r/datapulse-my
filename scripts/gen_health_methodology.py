#!/usr/bin/env python3
"""Render health methodology Markdown from prose and extracted code facts."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT_GENERATOR = ROOT / "scripts/gen_health_methodology_content.py"
TEMPLATE = ROOT / "scripts/templates/health-methodology.md.tmpl"
OUTPUT = ROOT / "docs/health-methodology.md"
EXTRACTED = ROOT / "docs/.health-methodology/extracted.md"
BLOCK = re.compile(r"(<!-- BEGIN EXTRACTED: ([a-z0-9-]+) -->.*?<!-- END EXTRACTED: \2 -->)", re.DOTALL)
PLACEHOLDER = re.compile(r"<!-- BEGIN EXTRACTED: ([a-z0-9-]+) -->")


def render(template: str, extracted: str) -> str:
    blocks = {match.group(2): match.group(1) for match in BLOCK.finditer(extracted)}
    if not blocks:
        raise ValueError("extracted content has no section blocks")
    placeholders = PLACEHOLDER.findall(template)
    missing = sorted(set(placeholders) - set(blocks))
    if missing:
        raise ValueError(f"extracted content is missing sections: {', '.join(missing)}")
    result = PLACEHOLDER.sub(lambda match: blocks[match.group(1)], template)
    return result.rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timer", type=Path, help="Override the systemd timer source for tests.")
    args = parser.parse_args()
    command = [sys.executable, str(CONTENT_GENERATOR), "--output", str(EXTRACTED)]
    if args.timer:
        command.extend(["--timer", str(args.timer)])
    completed = subprocess.run(command, cwd=ROOT)
    if completed.returncode:
        return completed.returncode
    try:
        rendered = render(TEMPLATE.read_text(encoding="utf-8"), EXTRACTED.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as error:
        print(f"Unable to render health methodology Markdown: {error}", file=sys.stderr)
        return 1
    OUTPUT.write_text(rendered, encoding="utf-8")
    print(f"Rendered {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
