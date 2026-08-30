#!/usr/bin/env python3
"""Generate MCP discovery documents and reference text from canonical local inputs."""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(os.environ.get("DATAPULSE_REPO_ROOT", Path(__file__).resolve().parents[1])).resolve()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "mcp"))

import server  # noqa: E402
from jsonschema import Draft202012Validator, FormatChecker  # noqa: E402
from mcp.types import LATEST_PROTOCOL_VERSION  # noqa: E402

from scripts.public_surface_generation import (  # noqa: E402
    GenerationError,
    load_json,
    load_public_surfaces,
    publish_text_outputs,
    replace_owned_block,
    serialize_json,
)


REQUIRED_ANNOTATIONS = ("readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _source_identity(sha: str | None, date: str | None) -> tuple[str, str]:
    resolved_sha = sha or os.environ.get("DATAPULSE_SOURCE_COMMIT_SHA")
    resolved_date = date or os.environ.get("DATAPULSE_SOURCE_COMMIT_DATE")
    if not resolved_sha or not SHA_RE.fullmatch(resolved_sha):
        raise GenerationError("source commit SHA must be explicitly injected as 40 lowercase hex characters")
    if not resolved_date or not DATE_RE.fullmatch(resolved_date):
        raise GenerationError("source commit date must be explicitly injected as YYYY-MM-DD")
    return resolved_sha, resolved_date


def _manifest(root: Path) -> list[dict[str, Any]]:
    datasets = load_json(root / "datapulse.json").get("datasets")
    if not isinstance(datasets, list) or not datasets or not all(isinstance(row, dict) and isinstance(row.get("id"), str) for row in datasets):
        raise GenerationError("datapulse.json: datasets must be a non-empty array of objects with ids")
    ids = [row["id"] for row in datasets]
    if len(ids) != len(set(ids)):
        raise GenerationError("datapulse.json: dataset ids must be unique")
    return datasets


def _taxonomy(root: Path) -> list[str]:
    try:
        value = load_json(root / "health.schema.json")["properties"]["datasets"]["items"]["properties"]["status"]["enum"]
    except (KeyError, TypeError) as error:
        raise GenerationError(f"health.schema.json: missing status enum: {error}") from error
    if not isinstance(value, list) or not value or not all(isinstance(item, str) for item in value) or len(value) != len(set(value)):
        raise GenerationError("health.schema.json: status enum must be a unique non-empty string array")
    return value


def _annotations(tool: object) -> dict[str, bool]:
    annotations = getattr(tool, "annotations", None)
    if annotations is None:
        raise GenerationError(f"MCP tool {tool.name!r} is missing all four required annotations")
    value = annotations.model_dump(by_alias=True, exclude_none=True)
    missing = [name for name in REQUIRED_ANNOTATIONS if name not in value]
    if missing:
        raise GenerationError(f"MCP tool {tool.name!r} is missing annotations: {', '.join(missing)}")
    return {name: bool(value[name]) for name in REQUIRED_ANNOTATIONS}


def _resource(resource: object, *, template: bool = False) -> dict[str, Any]:
    uri = resource.uri_template if template else str(resource.uri)
    return {
        "uriTemplate" if template else "uri": uri,
        "name": getattr(resource, "name", uri),
        "description": resource.description,
        "mimeType": getattr(resource, "mime_type", "application/json"),
    }


def render_mcp_document(
    *, config: dict[str, Any], datasets: list[dict[str, Any]], taxonomy: list[str],
    tools: list[object], resources: list[object], templates: list[object],
    source_sha: str, source_date: str,
) -> dict[str, Any]:
    """Render the complete MCP advertisement in public insertion order."""
    website = config["origins"]["website"]
    repository = config["origins"]["repository"]
    return {
        "$schema": f"{website}/mcp.schema.json",
        "schema": "datapulse/v1/mcp-advertisement",
        "mcp_version": LATEST_PROTOCOL_VERSION,
        "server": {
            "name": "DataPulse MY",
            "version": server.FASTMCP_VERSION,
            "source_commit_sha": source_sha,
            "source_commit_date": source_date,
            "description": (
                "Read-only access to DataPulse MY's Malaysian public dataset catalogue "
                f"({len(datasets)} datasets, {len(taxonomy)}-status health taxonomy, licence/attribution metadata)."
            ),
            "vendor": "DataPulse MY (open source)",
            "homepage": f"{website}/",
            "repository": repository,
        },
        "endpoint": {
            "url": f"{config['origins']['mcp']}/mcp",
            "transport": "streamable-http",
            "method": "POST",
            "auth_required": False,
        },
        "taxonomy": list(taxonomy),
        "tools": [
            {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.parameters,
                "annotations": _annotations(tool),
            }
            for tool in tools
        ],
        "resources": [_resource(resource) for resource in resources],
        "resource_templates": [_resource(template, template=True) for template in templates],
    }


def render_agent_document(
    *, config: dict[str, Any], datasets: list[dict[str, Any]], tools: list[object],
    resources: list[object], templates: list[object], source_sha: str, source_date: str,
    include_trust_model: bool = False, include_verification_capabilities: bool = False,
) -> dict[str, Any]:
    """Render the complete agent manifest without retaining stale JSON fields."""
    website = config["origins"]["website"]
    document = {
        "$schema": f"{website}/agent.schema.json",
        "schema": "datapulse/v1/agent-manifest",
        "@context": "https://schema.org/docs/jsonldcontext.jsonld",
        "@type": "WebSite",
        "@id": f"{website}/#agent",
        "name": "DataPulse MY",
        "description": f"Open-source trust layer for Malaysian public data with {len(datasets)} official datasets and agent-native discovery.",
        "url": f"{website}/",
        "capabilities": {
            "data_access": {"read": True, "write": False},
            "mcp_server": {
                "endpoint": f"{config['origins']['mcp']}/mcp",
                "transport": "streamable-http",
                "tools": len(tools),
                "resources": len(resources),
                "resource_templates": len(templates),
            },
        },
        "resources": {
            "manifest": f"{website}/datapulse.json",
            "health": f"{website}/health/latest.json",
            "llms": f"{website}/llms.txt",
            "mcp": f"{website}/mcp.json",
            "robots": f"{website}/robots.txt",
            "sitemap": f"{website}/sitemap.xml",
        },
        "source": {"commit_sha": source_sha, "commit_date": source_date},
        "last_updated": source_date,
    }
    if include_trust_model:
        document["trust_model"] = {
            "signed_receipts": "per-dataset-sigstore",
            "verification": "cosign verify-blob --bundle ...",
        }
    if include_verification_capabilities:
        document["capabilities"].update({
            "verify_dataset": True,
            "get_freshness_summary": True,
        })
    return document


def _signature(tool: object) -> str:
    properties = tool.parameters.get("properties", {})
    required = set(tool.parameters.get("required", []))
    arguments = [f"{name}{'[]' if item.get('type') == 'array' else ''}{'' if name in required else '?'}" for name, item in properties.items()]
    return f"{tool.name}({', '.join(arguments)})"


def _mcp_block(tools: list[object]) -> str:
    rows = ["### Tools", "", "| Tool | Use when |", "|---|---|"]
    for tool in tools:
        description = (tool.description or "").replace("|", "\\|").replace("\n", " ")
        rows.append(f"| `{_signature(tool)}` | {description} |")
    return "\n".join(rows)


def _reference(config: dict[str, Any], datasets: list[dict[str, Any]], taxonomy: list[str], tools: list[object], resources: list[object], templates: list[object]) -> str:
    lines = [
        "# MCP reference", "", "<!-- Generated by scripts/gen_mcp_reference.py from canonical local inputs. -->", "",
        f"DataPulse MY exposes {len(tools)} read-only tools over {len(datasets)} datasets and the {len(taxonomy)}-status health taxonomy at",
        f"`{config['origins']['mcp']}/mcp`.", "", "## Tools", "",
    ]
    for tool in tools:
        lines.extend([f"### `{tool.name}`", "", tool.description or "", "", "Input schema:", "", "```json", serialize_json(tool.parameters).rstrip(), "```", ""])
    lines.extend(["## Resources", ""])
    lines.extend(f"- `{resource.uri}` — {resource.description}" for resource in resources)
    lines.extend(["", "## Resource templates", ""])
    lines.extend(f"- `{template.uri_template}` — {template.description}" for template in templates)
    return "\n".join(lines).rstrip() + "\n"


async def generate(root: Path, *, source_sha: str | None = None, source_date: str | None = None, check: bool = False, validate_only: bool = False) -> bool:
    """Validate and render every MCP-owned output before publishing any of them."""
    config = load_public_surfaces(root)
    schemas: dict[str, dict[str, Any]] = {}
    for schema_name in ("mcp.schema.json", "agent.schema.json"):
        schema = load_json(root / schema_name)
        if schema.get("additionalProperties") is not False:
            raise GenerationError(f"{schema_name}: root additionalProperties must be false")
        schemas[schema_name] = schema
    datasets = _manifest(root)
    taxonomy = _taxonomy(root)
    featured = set(config["featured_dataset_ids"])
    missing_featured = featured - {row["id"] for row in datasets}
    if missing_featured:
        raise GenerationError(f"featured dataset id(s) missing from manifest: {', '.join(sorted(missing_featured))}")
    resolved_sha, resolved_date = _source_identity(source_sha, source_date)
    tools = list(await server.mcp.list_tools())
    resources = list(await server.mcp.list_resources())
    templates = list(await server.mcp.list_resource_templates())
    for tool in tools:
        _annotations(tool)

    mcp_document = render_mcp_document(config=config, datasets=datasets, taxonomy=taxonomy, tools=tools, resources=resources, templates=templates, source_sha=resolved_sha, source_date=resolved_date)
    agent_document = render_agent_document(
        config=config, datasets=datasets, tools=tools, resources=resources,
        templates=templates, source_sha=resolved_sha, source_date=resolved_date,
        include_trust_model="trust_model" in schemas["agent.schema.json"].get("properties", {}),
        include_verification_capabilities={"verify_dataset", "get_freshness_summary"}.issubset(
            schemas["agent.schema.json"].get("properties", {}).get("capabilities", {}).get("properties", {})
        ),
    )
    for label, document, schema in (
        ("mcp.json", mcp_document, schemas["mcp.schema.json"]),
        ("agent.json", agent_document, schemas["agent.schema.json"]),
    ):
        failures = sorted(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(document), key=lambda item: list(item.path))
        if failures:
            failure = failures[0]
            location = ".".join(str(part) for part in failure.absolute_path) or "<root>"
            raise GenerationError(f"{label}:{location}: schema violation: {failure.message}")
    outputs: dict[Path, str] = {
        root / "mcp.json": serialize_json(mcp_document),
        root / "agent.json": serialize_json(agent_document),
        root / "docs/mcp-reference.md": _reference(config, datasets, taxonomy, tools, resources, templates),
    }
    block = _mcp_block(tools)
    readme_body = f"- {len(tools)} tools: " + ", ".join(f"`{tool.name}`" for tool in tools) + f"\n\nThe public endpoint serves all {len(tools)} read-only tools over the\n{len(datasets)}-dataset catalogue."
    deploy_body = (
        f"The stable public endpoint is `{config['origins']['mcp']}/mcp`. Its local contract registers "
        f"{len(tools)} tools ({', '.join(f'`{tool.name}`' for tool in tools)}), "
        f"{len(resources)} concrete resources, and {len(templates)} resource templates."
    )
    for relative, body in (("llms.txt", block), ("README.md", readme_body), ("docs/mcp-deploy.md", deploy_body)):
        path = root / relative
        try:
            original = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            raise GenerationError(f"cannot read {path}: {error}") from error
        outputs[path] = replace_owned_block(original, "mcp-tools", body)
    if validate_only:
        return False
    return publish_text_outputs(outputs, check=check)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--source-commit-sha")
    parser.add_argument("--source-commit-date")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        changed = asyncio.run(generate(args.root.resolve(), source_sha=args.source_commit_sha, source_date=args.source_commit_date, check=args.check, validate_only=args.validate_only))
    except GenerationError as error:
        print(f"gen_mcp_reference.py: {error}", file=sys.stderr)
        return 1
    if args.check and changed:
        print("gen_mcp_reference.py: outputs are stale", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
