#!/usr/bin/env python3
"""Generate the small public rollup derived from the latest health snapshot."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.public_surface_generation import GenerationError, atomic_write_json


STATUS_KEYS = (
    "fresh",
    "aging",
    "stale",
    "discontinued",
    "degraded",
    "browser_dependent",
    "unreachable",
    "unknown",
    "unknown_freshness",
    "reference",
)


def _now_iso() -> str:
    """Return the generation time; kept separate so tests can freeze the clock."""
    return datetime.now(timezone.utc).isoformat()


def _load_health(path: Path) -> dict[str, Any]:
    try:
        health = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise GenerationError(f"cannot read {path}: {error}") from error
    if not isinstance(health, dict):
        raise GenerationError(f"{path}: root must be an object")
    summary = health.get("_trust_summary")
    if not isinstance(summary, dict):
        raise GenerationError(f"{path}: missing _trust_summary object")
    required = {"checked_at", "datasets_total", "by_status"}
    missing = required - set(summary)
    if missing:
        raise GenerationError(f"{path}: _trust_summary missing {', '.join(sorted(missing))}")
    return summary


def _summary_from_health(root: Path) -> dict[str, Any]:
    summary = _load_health(root / "health/latest.json")
    checked_at = summary["checked_at"]
    datasets_total = summary["datasets_total"]
    by_status = summary["by_status"]
    if not isinstance(checked_at, str) or not checked_at:
        raise GenerationError("health/latest.json: _trust_summary.checked_at must be a string")
    if type(datasets_total) is not int or datasets_total < 0:
        raise GenerationError("health/latest.json: datasets_total must be a non-negative integer")
    if not isinstance(by_status, dict) or set(by_status) != set(STATUS_KEYS):
        raise GenerationError("health/latest.json: by_status must contain exactly the 10 known statuses")
    if any(type(value) is not int or value < 0 for value in by_status.values()):
        raise GenerationError("health/latest.json: by_status values must be non-negative integers")
    if sum(by_status.values()) != datasets_total:
        raise GenerationError("health/latest.json: by_status total does not match datasets_total")
    return {
        "schema": "datapulse/v0.1/public-summary",
        "generated_at": _now_iso(),
        "source_checked_at": checked_at,
        "datasets_total": datasets_total,
        "by_status": {key: by_status[key] for key in STATUS_KEYS},
    }


def _mcp_tools(root: Path) -> int | None:
    path = root / "mcp.json"
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    tools = manifest.get("tools") if isinstance(manifest, dict) else None
    return len(tools) if isinstance(tools, list) else None


def generate(root: Path) -> None:
    """Generate datapulse_summary.json from the repository's public inputs."""
    root = Path(root)
    output = _summary_from_health(root)
    output["mcp"] = {"tools_advertised": _mcp_tools(root), "source": "mcp.json"}
    output["source_artifacts"] = {
        "health": "/health/latest.json",
        "mcp_manifest": "/mcp.json",
    }
    atomic_write_json(root / "datapulse_summary.json", output)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="repo root (default: cwd)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        generate(args.root)
    except GenerationError as error:
        print(f"gen_public_summary.py: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
