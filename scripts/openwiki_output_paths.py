#!/usr/bin/env python3
"""Print the generated OpenWiki output paths from their canonical config."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "openwiki-outputs.json"


def load_generated_paths(config: Path = CONFIG) -> list[str]:
    """Load usable generated paths, raising ValueError with the config path."""
    try:
        data: Any = json.loads(config.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read OpenWiki output config {config}: {exc}") from exc
    generated = data.get("generated") if isinstance(data, dict) else None
    if not isinstance(generated, list) or not generated or not all(
        isinstance(path, str) and path.strip() for path in generated
    ):
        raise ValueError(f"OpenWiki output config {config} has no usable 'generated' list")
    return generated


def main() -> int:
    try:
        paths = load_generated_paths()
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    print("\n".join(paths))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
