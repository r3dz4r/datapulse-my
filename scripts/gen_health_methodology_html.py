#!/usr/bin/env python3
"""Render the public health-methodology HTML page with Pandoc."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:  # Support both ``python scripts/...`` and package imports in tests.
    from scripts import gen_site_nav
except ImportError:
    import gen_site_nav


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/health-methodology.md"
TEMPLATE = ROOT / "scripts/templates/health-methodology.html.tmpl"
OUTPUT = ROOT / "docs/health-methodology.html"


def extract_title(source: Path) -> str:
    """Return the first ATX level-one heading from a Markdown document."""
    for line in source.read_text(encoding="utf-8").splitlines():
        if line.startswith("# ") and line[2:].strip():
            return line[2:].strip()
    raise ValueError(f"Health methodology source has no level-one title: {source}")


def pandoc_command(pandoc: str, source: Path, template: Path, output: Path, title: str) -> list[str]:
    return [
        pandoc,
        "--standalone",
        "--from=gfm",
        "--to=html5",
        f"--metadata=title:{title}",
        f"--template={template}",
        "--output",
        str(output),
        str(source),
    ]


def main() -> int:
    for label, path in (("source", SOURCE), ("template", TEMPLATE)):
        if not path.is_file():
            print(f"Health methodology {label} is missing: {path}", file=sys.stderr)
            return 1

    try:
        title = extract_title(SOURCE)
    except (OSError, UnicodeError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1

    pandoc = shutil.which("pandoc")
    if pandoc is None:
        print("Pandoc executable not found; install pandoc 3.1.3 before rendering.", file=sys.stderr)
        return 1

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{OUTPUT.name}.", suffix=".tmp", dir=OUTPUT.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        subprocess.run(
            pandoc_command(pandoc, SOURCE, TEMPLATE, temporary, title), check=True
        )
        os.replace(temporary, OUTPUT)
    except subprocess.CalledProcessError as error:
        print(f"Pandoc failed while rendering {SOURCE}: {error}", file=sys.stderr)
        temporary.unlink(missing_ok=True)
        return error.returncode or 1
    except OSError as error:
        print(f"Unable to render health methodology HTML: {error}", file=sys.stderr)
        temporary.unlink(missing_ok=True)
        return 1

    try:
        gen_site_nav.inject_nav(OUTPUT)
    except (OSError, UnicodeError, ValueError) as error:
        print(f"Unable to inject site navigation: {error}", file=sys.stderr)
        return 1

    print(f"Rendered {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
