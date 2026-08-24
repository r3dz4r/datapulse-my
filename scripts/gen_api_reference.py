#!/usr/bin/env python3
"""Render the marked runtime-derived blocks in the buyer API reference."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from api.config import PAGINATION_DEFAULT, PAGINATION_MAXIMUM
from api.public_contract import PublicRoute, public_routes
from scripts.public_surface_generation import (
    GenerationError,
    atomic_write_text,
    load_json,
    load_public_surfaces,
    replace_owned_block,
)


class ApiReferenceError(GenerationError):
    """Raised when a public API reference cannot be safely regenerated."""


def _dataset_total(manifest_path: Path, health_path: Path) -> int:
    manifest = load_json(manifest_path)
    health = load_json(health_path)
    manifest_rows = manifest.get("datasets")
    health_rows = health.get("datasets")
    if not isinstance(manifest_rows, list) or not isinstance(health_rows, list):
        raise ApiReferenceError("manifest and health must contain datasets arrays")
    if len(manifest_rows) != len(health_rows):
        raise ApiReferenceError("manifest and health dataset totals disagree")
    return len(manifest_rows)


def _endpoint_row(route: PublicRoute) -> str:
    query = "" if not route.query else "?" + "&".join(f"{name}=…" for name in route.query)
    return f"| `{route.method} {route.path}{query}` | {route.family.replace('-', ' ')} route. |"


def render_blocks(origin: str, total: int) -> dict[str, str]:
    """Build all public blocks from validated, non-secret inputs."""
    routes = public_routes()
    return {
        "buyer-api-host": f"`{origin}/api/v1/`",
        "buyer-api-quickstart": "```sh\ncurl -H \"X-API-Key: $DATAPULSE_API_KEY\" " + origin + "/api/v1/health\n```",
        "buyer-api-limits": (
            f"List endpoints default `limit` to {PAGINATION_DEFAULT} and cap it at "
            f"{PAGINATION_MAXIMUM}. `cursor` defaults to `0`; dataset history `days` "
            "defaults to 30 and caps at 3650."
        ),
        "buyer-api-endpoints": "| Endpoint | Description |\n| --- | --- |\n" + "\n".join(_endpoint_row(route) for route in routes),
        "buyer-api-pagination": (
            "List responses use `{" + '"data": [...], "pagination": {"limit": ' +
            f"{PAGINATION_DEFAULT}, \"next_cursor\": \"{PAGINATION_DEFAULT}\", \"total\": {total}" +
            "}}`; `next_cursor` is `null` at the end."
        ),
    }


def render_document(root: Path, reference_path: Path, manifest_path: Path, health_path: Path) -> str:
    """Validate every input then replace only declared marker-owned regions."""
    try:
        surfaces = load_public_surfaces(root)
        expected = "/" + reference_path.relative_to(root / "docs").as_posix()
        if expected not in surfaces["artifacts"]:
            raise ApiReferenceError(f"buyer API reference is not a declared public artifact: {expected}")
        source = reference_path.read_text(encoding="utf-8")
        blocks = render_blocks(surfaces["origins"]["api"], _dataset_total(manifest_path, health_path))
        rendered = source
        for marker, content in blocks.items():
            rendered = replace_owned_block(rendered, marker, content)
        forbidden = ("api.datapulse-my.my", "127.0.0.1", "localhost", "PHARMA_API_KEY", "PADDLE_SANDBOX_WEBHOOK_SECRET")
        if any(value in "\n".join(blocks.values()) for value in forbidden):
            raise ApiReferenceError("generated buyer API reference contains a forbidden value")
        return rendered
    except GenerationError as error:
        raise ApiReferenceError(str(error)) from error


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=root)
    parser.add_argument("--reference", type=Path, default=None)
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--health", type=Path, default=None)
    parser.add_argument("--check", "--validate-only", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    reference = args.reference or root / "docs/buyer-api-reference.md"
    manifest = args.manifest or root / "datapulse.json"
    health = args.health or root / "health/latest.json"
    try:
        rendered = render_document(root, reference, manifest, health)
        changed = not reference.is_file() or reference.read_text(encoding="utf-8") != rendered
        if args.check:
            return 1 if changed else 0
        if changed:
            atomic_write_text(reference, rendered)
        return 0
    except (ApiReferenceError, GenerationError, OSError, UnicodeError, ValueError) as error:
        print(f"buyer API reference generation failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
