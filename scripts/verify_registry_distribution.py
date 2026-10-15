#!/usr/bin/env python3
"""Fail closed when the live MCP Registry entry drifts from this repo's server.json.

A version string already present on the registry is not agreement. The listing
advertised "DataPulse MY" / 389 datasets for a month because the old guard
grepped for the version and skipped. This verifier compares title, description,
and the dataset count parsed out of each description, and treats an unverifiable
fetch as a hard failure rather than a skip.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_URL = (
    "https://registry.modelcontextprotocol.io/v0/servers/"
    "io.github.r3dz4r%2Fdatapulse-my/versions"
)
SERVER_JSON_NAME = "server.json"
# Closest integer before the word "datasets", so "418 Malaysian public datasets"
# reports 418 rather than some earlier number in the same sentence.
DATASET_COUNT_RE = re.compile(r"(\d+)(?:\D*)\bdatasets\b", re.IGNORECASE)
COMPARED_FIELDS = ("title", "description")
MAX_REGISTRY_PAGES = 100


class CannotDetermine(Exception):
    """Registry or canonical surfaces could not be read; absence is not agreement."""


@dataclass(frozen=True)
class FieldMismatch:
    """One published field that disagrees with the repo's canonical surface."""

    field: str
    published: object
    canonical: object


@dataclass(frozen=True)
class RegistryDistributionReport:
    """Comparison of one registry version against this repo's server.json."""

    version: str
    published_versions: list[str]
    entry: dict[str, Any] | None
    mismatches: list[FieldMismatch]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI flags. ``--check`` is the default (and only) mode."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        help="Repository root containing server.json (default: parent of scripts/)",
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=None,
        help="Read this saved registry JSON instead of the network",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Compare the published entry with canonical surfaces (default)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of prose",
    )
    args = parser.parse_args(argv)
    args.check = True
    return args


def parse_dataset_count(description: str) -> int | None:
    """Return the integer immediately preceding the word 'datasets', if any."""
    match = DATASET_COUNT_RE.search(description)
    if match is None:
        return None
    return int(match.group(1))


def resolve_fixture(cli_fixture: Path | None) -> Path | None:
    """Prefer --fixture; otherwise honour DATAPULSE_REGISTRY_FIXTURE so tests stay offline."""
    if cli_fixture is not None:
        return cli_fixture
    env = os.environ.get("DATAPULSE_REGISTRY_FIXTURE")
    if env:
        return Path(env)
    return None


def load_canonical_server(root: Path) -> dict[str, Any]:
    """Load title, description, and version from server.json; missing file is unknown."""
    path = root / SERVER_JSON_NAME
    if not path.is_file():
        raise CannotDetermine(f"missing {SERVER_JSON_NAME}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CannotDetermine(f"cannot read {SERVER_JSON_NAME}: {exc}") from exc
    data = _parse_json_object(text, SERVER_JSON_NAME)
    for field in ("version", "title", "description"):
        value = data.get(field)
        if not isinstance(value, str) or not value:
            raise CannotDetermine(f"{SERVER_JSON_NAME}: missing string field {field}")
    return data


def load_registry_payload(fixture: Path | None, cursor: str | None = None) -> dict[str, Any]:
    """Load one versions page from a fixture path or the live registry endpoint."""
    if fixture is not None:
        try:
            text = fixture.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise CannotDetermine(f"missing fixture {fixture}") from exc
        except OSError as exc:
            raise CannotDetermine(f"cannot read fixture: {exc}") from exc
        return _parse_json_object(text, "registry fixture")
    url = REGISTRY_URL if cursor is None else f"{REGISTRY_URL}?{urlencode({'cursor': cursor})}"
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "DataPulse-Registry-Distribution-Verify/1.0",
        },
    )
    for attempt in range(2):
        try:
            with urlopen(request, timeout=30) as response:
                raw = response.read()
            break
        except HTTPError as exc:
            if attempt == 1:
                raise CannotDetermine(f"registry HTTP {exc.code}") from exc
        except URLError as exc:
            if attempt == 1:
                raise CannotDetermine(f"registry network failure: {exc.reason}") from exc
        except (OSError, TimeoutError) as exc:
            if attempt == 1:
                raise CannotDetermine(f"registry network failure: {exc}") from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeError as exc:
        raise CannotDetermine(f"registry response is not UTF-8: {exc}") from exc
    return _parse_json_object(text, "registry response")


def extract_servers(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Return each entry's server object; a malformed list cannot be compared."""
    servers = payload.get("servers")
    if not isinstance(servers, list):
        raise CannotDetermine("registry response missing servers array")
    extracted: list[dict[str, Any]] = []
    for index, item in enumerate(servers):
        if not isinstance(item, dict):
            raise CannotDetermine(f"registry servers[{index}] is not an object")
        server = item.get("server")
        if not isinstance(server, dict):
            raise CannotDetermine(f"registry servers[{index}] missing server object")
        version = server.get("version")
        if not isinstance(version, str) or not version:
            raise CannotDetermine(f"registry servers[{index}] missing string version")
        extracted.append(server)
    return extracted


def load_published_servers(fixture: Path | None, version: str) -> list[dict[str, Any]]:
    """Read versions until the canonical one appears or the listing is exhausted."""
    published: list[dict[str, Any]] = []
    cursor: str | None = None
    seen_cursors: set[str] = set()
    for _ in range(MAX_REGISTRY_PAGES):
        payload = load_registry_payload(fixture, cursor)
        page = extract_servers(payload)
        published.extend(page)
        if any(server["version"] == version for server in page):
            return published
        metadata = payload.get("metadata", {})
        if not isinstance(metadata, dict):
            raise CannotDetermine("registry response has invalid metadata")
        next_cursor = metadata.get("nextCursor")
        if next_cursor is None or next_cursor == "":
            return published
        if not isinstance(next_cursor, str):
            raise CannotDetermine("registry response has invalid nextCursor")
        if next_cursor in seen_cursors:
            raise CannotDetermine("registry pagination repeats a cursor")
        seen_cursors.add(next_cursor)
        cursor = next_cursor
    raise CannotDetermine(f"registry pagination exceeds {MAX_REGISTRY_PAGES} pages")


def compare_entry(
    canonical: dict[str, Any],
    published_servers: list[dict[str, Any]],
) -> RegistryDistributionReport:
    """Select the repo's version and diff title, description, and dataset count."""
    version = canonical["version"]
    published_versions = [str(server["version"]) for server in published_servers]
    entry = next((server for server in published_servers if server.get("version") == version), None)
    if entry is None:
        return RegistryDistributionReport(
            version=version,
            published_versions=published_versions,
            entry=None,
            mismatches=[],
        )
    mismatches: list[FieldMismatch] = []
    for field in COMPARED_FIELDS:
        published = entry.get(field)
        expected = canonical.get(field)
        if published != expected:
            mismatches.append(FieldMismatch(field=field, published=published, canonical=expected))
    published_description = entry.get("description")
    canonical_description = canonical.get("description")
    published_count = (
        parse_dataset_count(published_description) if isinstance(published_description, str) else None
    )
    canonical_count = (
        parse_dataset_count(canonical_description) if isinstance(canonical_description, str) else None
    )
    # Report the count on its own so a 389→418 drift is obvious even when the
    # surrounding description sentence also changed.
    if published_count != canonical_count:
        mismatches.append(
            FieldMismatch(field="dataset_count", published=published_count, canonical=canonical_count)
        )
    return RegistryDistributionReport(
        version=version,
        published_versions=published_versions,
        entry=entry,
        mismatches=mismatches,
    )


def emit_report(report: RegistryDistributionReport, *, as_json: bool) -> None:
    """Print a machine-readable payload or operator-facing mismatch lines."""
    if as_json:
        payload = {
            "version": report.version,
            "published_versions": report.published_versions,
            "matched": report.entry is not None and not report.mismatches,
            "mismatches": [
                {
                    "field": item.field,
                    "published": item.published,
                    "canonical": item.canonical,
                }
                for item in report.mismatches
            ],
        }
        print(json.dumps(payload))
        return
    if report.entry is None:
        listed = ", ".join(report.published_versions) if report.published_versions else "(none)"
        print(
            f"version {report.version} is not published in fully-read registry listing; "
            f"published versions: {listed}",
            file=sys.stderr,
        )
        return
    if not report.mismatches:
        print(f"registry entry {report.version} matches canonical surfaces")
        return
    for item in report.mismatches:
        print(
            f"{item.field}: published={item.published!r} canonical={item.canonical!r}",
            file=sys.stderr,
        )


def main(argv: list[str] | None = None) -> int:
    """Compare the published registry entry; 0 identical, 1 drift, 2 unknown."""
    args = parse_args(argv)
    root = args.root.expanduser().resolve()
    try:
        canonical = load_canonical_server(root)
        published_servers = load_published_servers(resolve_fixture(args.fixture), canonical["version"])
    except CannotDetermine as exc:
        print(f"cannot determine: {exc}", file=sys.stderr)
        return 2
    report = compare_entry(canonical, published_servers)
    emit_report(report, as_json=args.json)
    if report.entry is None or report.mismatches:
        return 1
    return 0


def _parse_json_object(text: str, label: str) -> dict[str, Any]:
    try:
        value: object = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CannotDetermine(f"unparseable JSON in {label}: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise CannotDetermine(f"unparseable JSON in {label}: expected object")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
