#!/usr/bin/env python3
"""Generate the deterministic DataPulse MY AI resource directory catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LOGGER = logging.getLogger(__name__)
CATALOG_VERSION = "1.0.0"
PUBLIC_ORIGIN = "https://www.data-pulse.my"
MCP_ENDPOINT = "https://mcp.data-pulse.my/mcp"
TRUST_MODEL = "Signed probe attestation (Ed25519 L1, git-tag L2 anchor, per-dataset cosign keyless Sigstore bundle)"
VERIFICATION_COMMAND = "cosign verify-blob --bundle <dataset>.sigstore.json --certificate-identity <oidc-identity> --certificate-oidc-issuer https://token.actions.githubusercontent.com"
TAGS: dict[str, list[str]] = {
    "search_datasets": ["discovery", "malaysia", "public-data", "read-only", "trust-layer"],
    "get_dataset": ["dataset", "malaysia", "provenance", "read-only", "trust-layer"],
    "find_stale": ["freshness", "malaysia", "read-only", "risk", "trust-layer"],
    "find_anomalies": ["anomalies", "freshness", "malaysia", "read-only", "trust-layer"],
    "find_deteriorating": ["freshness", "malaysia", "read-only", "trends", "trust-layer"],
    "find_recovering": ["freshness", "malaysia", "read-only", "trends", "trust-layer"],
    "find_unreliable": ["malaysia", "read-only", "reliability", "risk", "trust-layer"],
    "find_schema_drift": ["malaysia", "read-only", "schema", "trust-layer", "validation"],
    "check_reconciliation": ["malaysia", "read-only", "reconciliation", "trust-layer", "validation"],
    "get_provenance": ["evidence", "malaysia", "provenance", "read-only", "trust-layer"],
    "get_evidence": ["evidence", "malaysia", "read-only", "receipts", "trust-layer"],
    "verify_dataset": ["evidence", "malaysia", "read-only", "trust-layer", "verification"],
    "get_freshness_summary": ["freshness", "malaysia", "read-only", "summary", "trust-layer"],
    "verify_evidence": ["evidence", "malaysia", "read-only", "transport", "verification"],
    "trust_verdict": ["evidence", "malaysia", "read-only", "trust", "verification"],
    "verify_attestation": ["attestation", "evidence", "malaysia", "read-only", "verification"],
    "find_by_licence": ["compliance", "discovery", "licence", "malaysia", "read-only"],
    "usage_summary": ["audit", "malaysia", "read-only", "summary", "usage"],
}


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be a JSON object")
    return value


def _source_commit_sha(root: Path, mcp: dict[str, Any]) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=False
    )
    if result.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", result.stdout.strip()):
        return result.stdout.strip()
    # Fixtures are deliberately not git worktrees; retain a pinned advertised source there.
    server = mcp.get("server")
    fallback = server.get("source_commit_sha") if isinstance(server, dict) else None
    if isinstance(fallback, str) and re.fullmatch(r"[0-9a-f]{40}", fallback):
        return fallback
    raise ValueError(f"could not resolve source commit SHA for {root}")


def _tools(mcp: dict[str, Any]) -> list[dict[str, Any]]:
    tools = mcp.get("tools")
    if not isinstance(tools, list):
        raise ValueError("mcp.json must contain a tools array")
    normalized: list[dict[str, Any]] = []
    for tool in tools:
        if not isinstance(tool, dict):
            raise ValueError("mcp.json tools must be objects")
        name, description, schema = tool.get("name"), tool.get("description"), tool.get("inputSchema")
        if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", name):
            raise ValueError("mcp.json tool names must be safe lowercase identifiers")
        if not isinstance(description, str) or not isinstance(schema, dict):
            raise ValueError(f"mcp.json tool {name} must have description and inputSchema")
        normalized.append(tool)
    names = [tool["name"] for tool in normalized]
    if len(names) != len(set(names)):
        raise ValueError("mcp.json contains duplicate tool names")
    missing_tags = set(names) - set(TAGS)
    if missing_tags:
        raise ValueError(f"missing static tags for tool(s): {', '.join(sorted(missing_tags))}")
    return sorted(normalized, key=lambda tool: tool["name"])


def _identifier(name: str) -> str:
    return f"urn:air:data-pulse.my:mcp:{name}"


def _capabilities(tool: dict[str, Any]) -> list[str]:
    properties = tool["inputSchema"].get("properties", {})
    if not isinstance(properties, dict) or not all(isinstance(key, str) for key in properties):
        raise ValueError(f"mcp.json tool {tool['name']} has invalid inputSchema.properties")
    return sorted([tool["name"], *(f"{tool['name']}.{key}" for key in properties)])


def _representative_queries(tool: dict[str, Any]) -> list[str]:
    properties = tool["inputSchema"].get("properties", {})
    if not isinstance(properties, dict):
        return []
    queries: list[str] = []
    for key in sorted(properties):
        property_schema = properties[key]
        examples = property_schema.get("examples") if isinstance(property_schema, dict) else None
        if isinstance(examples, list) and examples and isinstance(examples[0], (str, int, float, bool)):
            queries.append(f"{tool['name']}({key}={examples[0]!r})")
    return queries


def _verification() -> dict[str, str]:
    return {
        "model": TRUST_MODEL,
        "verification_command": VERIFICATION_COMMAND,
        "verification_metadata_url": f"{PUBLIC_ORIGIN}/llms.txt",
    }


def build_outputs(root: Path) -> tuple[bytes, dict[str, bytes]]:
    """Return canonical catalog and card bytes without writing public artifacts."""
    mcp = _read_object(root / "mcp.json")
    manifest = _read_object(root / "datapulse.json")
    datasets = manifest.get("datasets")
    if not isinstance(datasets, list):
        raise ValueError("datapulse.json must contain a datasets array")
    tools = _tools(mcp)
    source_commit_sha = _source_commit_sha(root, mcp)
    entries: list[dict[str, Any]] = []
    cards: dict[str, bytes] = {}
    for tool in tools:
        name = tool["name"]
        identifier = _identifier(name)
        capabilities = _capabilities(tool)
        tags = sorted(TAGS[name])
        entries.append({
            "identifier": identifier,
            "displayName": name,
            "type": "application/mcp-server-card+json",
            "url": f"{PUBLIC_ORIGIN}/mcp/cards/{name}.json",
            "description": tool["description"],
            "representativeQueries": _representative_queries(tool),
            "capabilities": capabilities,
            "tags": tags,
        })
        card = {
            "specVersion": "1.0",
            "contract_version": CATALOG_VERSION,
            "identifier": identifier,
            "displayName": name,
            "tool_type": "mcp-tool",
            "annotations": tool.get("annotations", {}),
            "description": tool["description"],
            "input_schema": tool["inputSchema"],
            "capabilities": capabilities,
            "endpoint": {"url": MCP_ENDPOINT, "transport": "streamable-http", "method": "POST"},
            "verification": _verification(),
            "dataset_count": len(datasets),
            "tags": tags,
            "source": {"commit_sha": source_commit_sha, "manifest": "mcp.json"},
        }
        cards[name] = _json_bytes(card)
    catalog = {
        "specVersion": "1.0",
        "ard_spec_version": "0.9",
        "contract_version": CATALOG_VERSION,
        "host": {"displayName": "DataPulse MY", "homepage": f"{PUBLIC_ORIGIN}/", "repository": "https://github.com/r3dz4r/datapulse-my"},
        "publisher": {"name": "DataPulse MY"},
        "endpoint": {"url": MCP_ENDPOINT, "transport": "streamable-http", "method": "POST", "auth_required": False},
        "trust": _verification(),
        "dataset_count": len(datasets),
        "taxonomy": mcp.get("taxonomy"),
        "license": "MIT (catalog); dataset licences as declared per dataset",
        "entries": entries,
    }
    return _json_bytes(catalog), cards


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    try:
        temporary.write_bytes(content)
        os.rename(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def generate(root: Path) -> list[Path]:
    catalog, cards = build_outputs(root)
    outputs = [root / "docs/ai-catalog.json"]
    _atomic_write(outputs[0], catalog)
    for name, content in cards.items():
        path = root / "docs/mcp/cards" / f"{name}.json"
        _atomic_write(path, content)
        outputs.append(path)
    return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        outputs = generate(args.root.resolve())
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        LOGGER.error("AI catalog generation failed: %s", exc)
        return 1
    LOGGER.info("generated %d deterministic AI catalog artifacts", len(outputs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
