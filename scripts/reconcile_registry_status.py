#!/usr/bin/env python3
"""Deprecate superseded MCP Registry versions so exactly one stays active.

publish-mcp.yml publishes the new version but never changed the status of
earlier ones, so the registry accumulated active versions ranked by version
number: 3.4.6 stayed active AND isLatest with stale content while 0.13.0 held
the canonical content. This reconciler deprecates every other active version
after each release. It never uses ``deleted`` and never mutates the target.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SERVER_NAME = "io.github.r3dz4r/datapulse-my"
DEFAULT_REGISTRY_URL = "https://registry.modelcontextprotocol.io"
DEFAULT_PUBLISHER_BIN = "./mcp-publisher"
META_KEY = "io.modelcontextprotocol.registry/official"
ACTIVE_STATUS = "active"
APPLIED_STATUS = "deprecated"
STATUS_MESSAGE_TEMPLATE = "Superseded by {target}; canonical surfaces updated"
MAX_STATUS_MESSAGE_CHARS = 500
IDEMPOTENT_FAILURE_MARKER = "already deprecated"


class CannotDetermine(Exception):
    """The versions payload could not be read; absence is not reconciliation."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI flags."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        required=True,
        help="Version that must end up as the single active registry version",
    )
    parser.add_argument(
        "--server-name",
        default=DEFAULT_SERVER_NAME,
        help=f"Registry server name (default: {DEFAULT_SERVER_NAME})",
    )
    parser.add_argument(
        "--registry-url",
        default=DEFAULT_REGISTRY_URL,
        help=f"Registry base URL (default: {DEFAULT_REGISTRY_URL})",
    )
    parser.add_argument(
        "--publisher-bin",
        default=DEFAULT_PUBLISHER_BIN,
        help=f"mcp-publisher binary (default: {DEFAULT_PUBLISHER_BIN})",
    )
    parser.add_argument(
        "--from-file",
        type=Path,
        default=None,
        help="Read the versions payload from this file instead of the registry",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the plan without invoking the publisher or writing anything",
    )
    return parser.parse_args(argv)


def load_versions_payload(
    from_file: Path | None,
    server_name: str,
    registry_url: str,
) -> dict[str, Any]:
    """Load the versions payload from --from-file, or from the public read API."""
    if from_file is not None:
        try:
            text = from_file.read_text(encoding="utf-8")
        except OSError as exc:
            raise CannotDetermine(f"cannot read {from_file}: {exc}") from exc
    else:
        url = f"{registry_url.rstrip('/')}/v0/servers/{quote(server_name, safe='')}/versions"
        request = Request(url, headers={"Accept": "application/json"})
        try:
            with urlopen(request) as response:
                text = response.read().decode("utf-8")
        except (HTTPError, URLError, OSError) as exc:
            raise CannotDetermine(f"cannot fetch {url}: {exc}") from exc
    return _parse_json_object(text, from_file.name if from_file else url)


def extract_entries(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the ``servers`` list; anything else is not a versions payload."""
    servers = payload.get("servers")
    if not isinstance(servers, list):
        raise CannotDetermine("versions payload has no servers list")
    entries: list[dict[str, Any]] = []
    for item in servers:
        if isinstance(item, dict):
            entries.append(item)
    return entries


def entry_version(entry: dict[str, Any]) -> str | None:
    """The server.version of one entry, if present."""
    server = entry.get("server")
    if not isinstance(server, dict):
        return None
    version = server.get("version")
    return version if isinstance(version, str) else None


def entry_status(entry: dict[str, Any]) -> str | None:
    """The official-registry status of one entry, if present."""
    meta = entry.get("_meta")
    if not isinstance(meta, dict):
        return None
    official = meta.get(META_KEY)
    if not isinstance(official, dict):
        return None
    status = official.get("status")
    return status if isinstance(status, str) else None


def active_versions(entries: list[dict[str, Any]]) -> list[str]:
    """Versions whose official status is exactly ``active``, in payload order."""
    active: list[str] = []
    for entry in entries:
        version = entry_version(entry)
        if version is not None and entry_status(entry) == ACTIVE_STATUS:
            active.append(version)
    return active


def build_plan(entries: list[dict[str, Any]], target: str) -> list[str]:
    """Versions to deprecate: active and not the target, in payload order."""
    plan: list[str] = []
    for entry in entries:
        version = entry_version(entry)
        if version is None:
            continue
        if version == target:
            # Hard guard: the released version must never deprecate itself,
            # whatever its recorded status.
            continue
        if entry_status(entry) == "active":
            plan.append(version)
    return plan


def deprecation_message(target: str) -> str:
    """The statusMessage sent with every deprecation (registry cap: 500 chars)."""
    message = STATUS_MESSAGE_TEMPLATE.format(target=target)
    if len(message) > MAX_STATUS_MESSAGE_CHARS:
        raise CannotDetermine(
            f"status message exceeds {MAX_STATUS_MESSAGE_CHARS} chars for target {target}"
        )
    return message


def apply_plan(plan: list[str], args: argparse.Namespace, message: str) -> int:
    """Invoke the publisher once per planned version, in plan order."""
    for version in plan:
        command = [
            args.publisher_bin,
            "status",
            "--status",
            APPLIED_STATUS,
            "--message",
            message,
            args.server_name,
            version,
        ]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
        output = (completed.stdout or "") + (completed.stderr or "")
        if completed.returncode == 0:
            print(f"deprecated {version}")
            continue
        if IDEMPOTENT_FAILURE_MARKER in output:
            print(f"{version} already deprecated; treating as success")
            continue
        print(
            f"publisher failed for {version} with exit {completed.returncode}:",
            file=sys.stderr,
        )
        print(output, file=sys.stderr)
        return completed.returncode or 1
    return 0


def main(argv: list[str] | None = None) -> int:
    """Reconcile lifecycle status; 0 success, 1 reconciliation failure, 2 unknown."""
    args = parse_args(argv)
    try:
        payload = load_versions_payload(args.from_file, args.server_name, args.registry_url)
        entries = extract_entries(payload)
    except CannotDetermine as exc:
        print(f"cannot determine: {exc}", file=sys.stderr)
        return 2

    plan = build_plan(entries, args.target)

    if args.dry_run:
        for version in plan:
            print(f"would deprecate {version}")
        print(
            f"total: {len(plan)} version(s) would be deprecated "
            f"(dry-run, no changes made)"
        )
        return 0

    if not plan:
        print("no superseded active versions to deprecate")
    else:
        try:
            message = deprecation_message(args.target)
        except CannotDetermine as exc:
            print(f"cannot determine: {exc}", file=sys.stderr)
            return 2
        applied = apply_plan(plan, args, message)
        if applied != 0:
            return applied

    try:
        payload = load_versions_payload(args.from_file, args.server_name, args.registry_url)
        entries = extract_entries(payload)
    except CannotDetermine as exc:
        print(f"cannot determine: {exc}", file=sys.stderr)
        return 2
    observed = active_versions(entries)
    if observed != [args.target]:
        print(
            "post-state check failed: expected exactly one active version "
            f"({args.target}), observed {len(observed)}: {', '.join(observed) or '(none)'}",
            file=sys.stderr,
        )
        return 1
    print(f"registry reconciled: single active version {args.target}")
    return 0


def _parse_json_object(text: str, source: str) -> dict[str, Any]:
    try:
        value: object = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CannotDetermine(f"unparseable JSON from {source}") from exc
    if not isinstance(value, dict):
        raise CannotDetermine(f"expected a JSON object from {source}")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
