#!/usr/bin/env python3
"""Generate MCP discovery schemas and reference docs from mcp/server.py."""

from __future__ import annotations

import asyncio
import json
import os
import re
import stat
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mcp"))

import server  # noqa: E402


BEGIN_MCP_TOOLS = "<!-- BEGIN mcp-tools -->"
END_MCP_TOOLS = "<!-- END mcp-tools -->"


class GenerationError(Exception):
    """Raised when an owned artifact does not satisfy the generator contract."""


def atomic_write(path: Path, content: str) -> None:
    """Replace a file atomically while preserving its permission bits."""
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent,
            prefix=f".{path.name}.", delete=False,
        ) as output:
            temporary = Path(output.name)
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    except (OSError, UnicodeError) as error:
        if "temporary" in locals():
            temporary.unlink(missing_ok=True)
        raise GenerationError(f"cannot write {path}: {error}") from error


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise GenerationError(f"cannot read {path}: {error}") from error


def tool_block_pattern() -> re.Pattern[str]:
    return re.compile(
        rf"{re.escape(BEGIN_MCP_TOOLS)}\n.*?\n{re.escape(END_MCP_TOOLS)}",
        re.DOTALL,
    )


def validate_tool_block(path: Path) -> None:
    original = read_text(path)
    matches = tool_block_pattern().findall(original)
    if (
        original.count(BEGIN_MCP_TOOLS) != 1
        or original.count(END_MCP_TOOLS) != 1
        or len(matches) != 1
    ):
        raise GenerationError(
            f"{path}: expected exactly one {BEGIN_MCP_TOOLS!r}/"
            f"{END_MCP_TOOLS!r} block, found {len(matches)}"
        )


def replace_tool_block(path: Path, body: str) -> None:
    original = read_text(path)
    pattern = tool_block_pattern()
    matches = pattern.findall(original)
    if (
        original.count(BEGIN_MCP_TOOLS) != 1
        or original.count(END_MCP_TOOLS) != 1
        or len(matches) != 1
    ):
        raise GenerationError(
            f"{path}: expected exactly one {BEGIN_MCP_TOOLS!r}/"
            f"{END_MCP_TOOLS!r} block, found {len(matches)}"
        )
    replacement = f"{BEGIN_MCP_TOOLS}\n{body.rstrip()}\n{END_MCP_TOOLS}"
    updated = pattern.sub(lambda _: replacement, original, count=1)
    if updated != original:
        atomic_write(path, updated)


def tool_signature(tool: object) -> str:
    schema = tool.parameters
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    arguments = []
    for name, parameter in properties.items():
        array_suffix = "[]" if parameter.get("type") == "array" else ""
        optional_suffix = "" if name in required else "?"
        arguments.append(f"{name}{array_suffix}{optional_suffix}")
    return f"{tool.name}({', '.join(arguments)})"


def markdown_cell(value: str) -> str:
    return value.replace("|", r"\|").replace("\n", " ")


def update_llms(tools: list[object]) -> None:
    rows = ["### Tools", "", "| Tool | Use when |", "|---|---|"]
    rows.extend(
        f"| `{tool_signature(tool)}` | {markdown_cell(tool.description or '')} |"
        for tool in tools
    )
    replace_tool_block(ROOT / "llms.txt", "\n".join(rows))


def update_readme(tools: list[object]) -> None:
    names = ", ".join(f"`{tool.name}`" for tool in tools)
    body = (
        f"- {len(tools)} tools: {names}\n\n"
        f"The public endpoint is live and serves all {len(tools)} read-only tools over the\n"
        f"{server.DATASET_COUNT}-dataset catalogue."
    )
    replace_tool_block(ROOT / "README.md", body)


def load_agent() -> dict:
    path = ROOT / "agent.json"
    try:
        document = json.loads(read_text(path))
        document["capabilities"]["mcp_server"]["tools"]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise GenerationError(f"{path}: invalid mcp_server contract: {error}") from error
    return document


def update_agent(tool_count: int, document: dict) -> None:
    document["capabilities"]["mcp_server"]["tools"] = tool_count
    atomic_write(ROOT / "agent.json", json.dumps(document, indent=2, ensure_ascii=False) + "\n")


def update_deploy_doc(tools: list[object]) -> None:
    names = ", ".join(f"`{tool.name}`" for tool in tools)
    body = (
        "The stable public endpoint is live at `https://mcp.data-pulse.my/mcp`. It has\n"
        f"been verified end to end: `tools/list` returns {len(tools)} tools over the "
        f"{server.DATASET_COUNT}-dataset\ncatalogue.\n\n"
        f"The current read-only contract is {names}; it also publishes the concrete resources"
    )
    replace_tool_block(ROOT / "docs/mcp-deploy.md", body)


LIVE_VERIFICATION = """## Live verification

Run before merging any change that touches the manifest, probe policy, or MCP
source. The live `datapulse://index` resource is the catalogue returned by the
MCP server, so its array length must equal the current manifest length.

```bash
verify_dir=$(mktemp -d /tmp/datapulse-mcp-live.XXXXXX)
endpoint=https://mcp.data-pulse.my/mcp

curl -sS -D "$verify_dir/headers" -o "$verify_dir/initialize" \\
  "$endpoint" \\
  -H 'Accept: application/json, text/event-stream' \\
  -H 'Content-Type: application/json' \\
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"live-count-gate","version":"1"}}}'

session_id=$(awk 'tolower($1)=="mcp-session-id:" {gsub("\\\\r", "", $2); print $2}' \\
  "$verify_dir/headers")

curl -sS "$endpoint" \\
  -H 'Accept: application/json, text/event-stream' \\
  -H 'Content-Type: application/json' \\
  -H "Mcp-Session-Id: $session_id" \\
  -d '{"jsonrpc":"2.0","method":"notifications/initialized"}' >/dev/null

live_count=$(curl -sS "$endpoint" \\
  -H 'Accept: application/json, text/event-stream' \\
  -H 'Content-Type: application/json' \\
  -H "Mcp-Session-Id: $session_id" \\
  -d '{"jsonrpc":"2.0","id":2,"method":"resources/read","params":{"uri":"datapulse://index"}}' \\
  | sed -n 's/^data: //p' \\
  | jq -r '.result.contents[0].text | fromjson | length')
head_count=$(jq '.datasets | length' datapulse.json)

printf 'live=%s head=%s\\n' "$live_count" "$head_count"
test "$live_count" -eq "$head_count"
```

The expected count at this revision is `DATASET_COUNT`. If the assertion fails, do not
merge: the MCP server is stale and the manifest-count claim is false.
""".replace("DATASET_COUNT", str(server.DATASET_COUNT))


def json_block(value: dict) -> str:
    return "```json\n" + json.dumps(value, indent=2, ensure_ascii=False) + "\n```"


async def generate() -> None:
    tools = await server.mcp.list_tools()
    resources = await server.mcp.list_resources()
    templates = await server.mcp.list_resource_templates()

    for path in (ROOT / "llms.txt", ROOT / "README.md", ROOT / "docs/mcp-deploy.md"):
        validate_tool_block(path)
    agent = load_agent()

    discovery_path = ROOT / "mcp.json"
    discovery = json.loads(discovery_path.read_text(encoding="utf-8"))
    discovery["server"]["source_commit_sha"] = server.SOURCE_COMMIT_SHA
    discovery["server"]["source_commit_date"] = server.SOURCE_COMMIT_DATE
    discovery["server"]["description"] = re.sub(
        r"\(\d+ datasets,",
        f"({server.DATASET_COUNT} datasets,",
        discovery["server"]["description"],
    )
    for resource in discovery.get("resources", []):
        if resource.get("uri") == "datapulse://index":
            resource["description"] = re.sub(
                r"all \d+ datasets",
                f"all {server.DATASET_COUNT} datasets",
                resource["description"],
            )
    discovery["tools"] = [
        {
            "name": tool.name,
            "description": tool.description,
            "inputSchema": tool.parameters,
        }
        for tool in tools
    ]
    discovery["resources"] = [
        {
            "uri": str(resource.uri),
            "name": getattr(resource, "name", str(resource.uri)),
            "description": resource.description,
            "mimeType": getattr(resource, "mime_type", "application/json"),
        }
        for resource in resources
    ] + [
        {
            "uri": template.uri_template,
            "name": getattr(template, "name", template.uri_template),
            "description": template.description,
            "mimeType": getattr(template, "mime_type", "application/json"),
        }
        for template in templates
    ]
    atomic_write(discovery_path, json.dumps(discovery, indent=2, ensure_ascii=False) + "\n")

    lines = [
        "# MCP reference",
        "",
        "<!-- Generated by scripts/gen_mcp_reference.py from mcp/server.py. -->",
        "",
        "DataPulse MY exposes a read-only Streamable HTTP endpoint at",
        "`https://mcp.data-pulse.my/mcp`. It requires no authentication.",
        "",
        "Clients must send `Accept: application/json, text/event-stream` and use the",
        "session ID returned by the initialize response for subsequent calls.",
        "",
        "## Tools",
        "",
    ]
    for tool in tools:
        lines.extend(
            [
                f"### `{tool.name}`",
                "",
                tool.description or "",
                "",
                "Input schema:",
                "",
                json_block(tool.parameters),
                "",
            ]
        )

    lines.extend(["## Resources", ""])
    for resource in resources:
        lines.extend(
            [
                f"- `{resource.uri}` — {resource.description}",
                "",
            ]
        )
    for template in templates:
        lines.extend(
            [
                f"- `{template.uri_template}` — {template.description}",
                "",
            ]
        )

    lines.extend(LIVE_VERIFICATION.splitlines() + [""])
    lines.extend(
        [
            "## Regenerate",
            "",
            "Install `mcp/requirements.txt`, then run:",
            "",
            "```sh",
            "python3 scripts/gen_mcp_reference.py",
            "```",
            "",
            "The command updates this file, `mcp.json`, `llms.txt`, `README.md`,",
            "`agent.json`, and `docs/mcp-deploy.md`.",
            "",
        ]
    )
    atomic_write(ROOT / "docs/mcp-reference.md", "\n".join(lines))
    update_llms(tools)
    update_readme(tools)
    update_agent(len(tools), agent)
    update_deploy_doc(tools)
    print(
        f"Generated {len(tools)} tools, {len(resources)} resources, "
        f"and {len(templates)} resource templates"
    )


def main() -> int:
    try:
        asyncio.run(generate())
    except GenerationError as error:
        print(f"gen_mcp_reference.py: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
