#!/usr/bin/env python3
"""Verify that local release inputs agree with public DataPulse surfaces."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from jsonschema import Draft202012Validator


PUBLIC_ROOT = "https://www.data-pulse.my"
MCP_ENDPOINT = "https://mcp.data-pulse.my/mcp"
USER_AGENT = "DataPulse-Local-Public-Parity/1.0"
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
CANONICAL_ROUTES = (
    "/",
    "/health/latest.json",
    "/llms.txt",
    "/agent.json",
    "/mcp/cards/search_datasets.json",
)


@dataclass(frozen=True)
class Response:
    """Bounded public HTTP response used by the parity checks."""

    status: int
    url: str
    content_type: str
    body: bytes
    headers: dict[str, str] = field(default_factory=dict)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _fetch(url: str, *, method: str = "GET", body: bytes | None = None,
           headers: dict[str, str] | None = None) -> Response:
    request_headers = {"User-Agent": USER_AGENT, **(headers or {})}
    request = Request(url, data=body, headers=request_headers, method=method)
    with urlopen(request, timeout=30) as raw:  # nosec B310: URLs are module constants.
        payload = b"" if method == "HEAD" else raw.read(MAX_RESPONSE_BYTES + 1)
        if len(payload) > MAX_RESPONSE_BYTES:
            raise ValueError(f"response exceeds {MAX_RESPONSE_BYTES} byte limit")
        return Response(raw.status, raw.url, raw.headers.get_content_type(), payload, dict(raw.headers.items()))


def _mcp_tools(fetch: Callable[..., Response]) -> set[str]:
    """Return deployed tool names or raise a descriptive probe error."""
    def post(message: dict[str, Any], session: str | None = None) -> Response:
        headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
        if session:
            headers["Mcp-Session-Id"] = session
        return fetch(MCP_ENDPOINT, method="POST", body=json.dumps(message).encode(), headers=headers)

    initialized = post({"jsonrpc": "2.0", "method": "initialize", "params": {
        "protocolVersion": "2025-03-26", "capabilities": {},
        "clientInfo": {"name": "verify-local-public-parity", "version": "1"},
    }, "id": 1})
    if initialized.status != 200:
        raise ValueError(f"initialize returned HTTP {initialized.status}")
    session = initialized.headers.get("Mcp-Session-Id")
    if not session:
        session = initialized.body and json.loads(initialized.body).get("result", {}).get("sessionId")
    # FastMCP returns the session id as a header in production; absence is harmless for
    # implementations which do not require a notification session.
    post({"jsonrpc": "2.0", "method": "notifications/initialized"}, session)
    tools = post({"jsonrpc": "2.0", "method": "tools/list", "id": 2}, session)
    if tools.status != 200:
        raise ValueError(f"tools/list returned HTTP {tools.status}")
    parsed = json.loads(tools.body)
    values = parsed.get("result", {}).get("tools")
    if not isinstance(values, list) or not all(isinstance(item, dict) and isinstance(item.get("name"), str) for item in values):
        raise ValueError("tools/list omitted a valid tools array")
    return {item["name"] for item in values}


def verify(root: Path, *, fetch: Callable[..., Response] = _fetch) -> tuple[list[str], list[str], list[str]]:
    """Return (errors, warnings, passed dimensions) for a repository root."""
    errors: list[str] = []
    warnings: list[str] = []
    passed: list[str] = []
    required = ("datapulse.json", "mcp.json", "health.schema.json", "health/latest.json", "docs/index.html")
    missing = [name for name in required if not (root / name).is_file()]
    if missing:
        return ([f"ERROR: operator_error: missing required input(s): {', '.join(missing)}"], warnings, passed)
    try:
        manifest, mcp, health, health_schema = (_read_json(root / name) for name in ("datapulse.json", "mcp.json", "health/latest.json", "health.schema.json"))
        local_datasets = manifest["datasets"]
        local_tools = {tool["name"] for tool in mcp["tools"]}
        taxonomy = health_schema["properties"]["datasets"]["items"]["properties"]["status"]["enum"]
        if not isinstance(local_datasets, list) or not isinstance(taxonomy, list):
            raise ValueError("manifest datasets or taxonomy is not an array")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return ([f"ERROR: operator_error: unreadable local parity input: {exc}"], warnings, passed)

    # 1. Dataset count.
    try:
        served_html = fetch(PUBLIC_ROOT + "/").body.decode("utf-8")
        served_count = served_html.count('class="register-row"')
        if len(local_datasets) != served_count:
            errors.append(f"ERROR: dataset_count parity failure: local={len(local_datasets)} served={served_count}")
        else:
            passed.append("dataset_count")
    except (HTTPError, URLError, TimeoutError, UnicodeError, ValueError) as exc:
        errors.append(f"ERROR: dataset_count parity failure: public root unavailable: {exc}")

    # 2. Tools are intentionally non-gating when the independently verified MCP probe is unavailable.
    try:
        served_tools = _mcp_tools(fetch)
        if local_tools != served_tools:
            errors.append("ERROR: mcp_tool parity failure: " f"local_names={sorted(local_tools)} served_names={sorted(served_tools)}")
        else:
            passed.append("tool_count")
    except (HTTPError, URLError, TimeoutError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        warnings.append(f"WARNING: mcp_tool probe skipped: {exc}")

    # 3. Only status-bearing fields are scanned; ordinary prose such as 'verified' is not a status.
    for path, text, pattern in (
        ("docs/index.html", (root / "docs/index.html").read_text(encoding="utf-8"), r'data-status="([\w-]+)"'),
        ("health/latest.json", (root / "health/latest.json").read_text(encoding="utf-8"), r'"status"\s*:\s*"([\w-]+)"'),
    ):
        for match in re.finditer(pattern, text):
            token = match.group(1)
            # The dashboard's serialized data attributes predate the public schema
            # and use underscores; accept that representation only for canonical values.
            if token not in taxonomy and token.replace("_", "-") not in taxonomy:
                errors.append(f'ERROR: status_taxonomy violation: {path} mentions "{token}" at offset {match.start(1)}')
    if not any("status_taxonomy" in error for error in errors):
        passed.append("taxonomy")

    # 4. Deployment identity is informational until Pages exposes a commit field.
    try:
        local_sha = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        remote_sha = subprocess.check_output(["git", "-C", str(root), "rev-parse", "origin/main"], text=True).strip()
        if local_sha != remote_sha:
            warnings.append(f"WARNING: source_commit informational drift: local={local_sha} origin/main={remote_sha}")
        else:
            passed.append("source_commit")
    except (OSError, subprocess.CalledProcessError):
        warnings.append("WARNING: source_commit probe skipped: git origin/main is unavailable")

    # 5. Parse and validate the schemas whose schema documents are local.
    for name, schema_name in (("datapulse.json", "datapulse.schema.json"), ("health/latest.json", "health.schema.json")):
        try:
            Draft202012Validator(_read_json(root / schema_name)).validate(_read_json(root / name))
        except Exception as exc:  # jsonschema supplies several specific validation classes.
            errors.append(f"ERROR: manifest_invalid: {name}: {exc}")
    for name in ("mcp.json", "agent.json", "docs/ai-catalog.json"):
        try:
            _read_json(root / name)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"ERROR: manifest_invalid: {name}: {exc}")
    if not any("manifest_invalid" in error for error in errors):
        passed.append("manifest_schema")

    # 6. Served health remains non-gating during independently scheduled health publication.
    local_digest = hashlib.sha256((root / "health/latest.json").read_bytes()).hexdigest()
    try:
        served = fetch(PUBLIC_ROOT + "/health/latest.json")
        served_digest = hashlib.sha256(served.body).hexdigest()
        if local_digest != served_digest:
            warnings.append(f"WARNING: health_snapshot informational drift: local_sha={local_digest} served_sha={served_digest}")
        else:
            passed.append("health_snapshot")
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        warnings.append(f"WARNING: health_snapshot probe skipped: {exc}")

    # 7. Attestation chain (current layouts use attestations/, older layouts used .attestations/).
    attestation_root = root / "attestations" if (root / "attestations").is_dir() else root / ".attestations"
    chain_head = attestation_root / "latest/chain_head.json"
    try:
        envelope = _read_json(chain_head)
        if not isinstance(envelope, dict) or not envelope.get("chain_head") or not envelope.get("dataset_links"):
            raise ValueError("chain head lacks chain_head or dataset_links subject")
        passed.append("attestation_subject")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"ERROR: attestation chain_head missing or unreadable: {exc}")

    # 8. Receipt publication is optional in this checkout, but if present it must be JSON objects.
    receipts = sorted((root / "data").glob("*.receipt.*.json"))
    for receipt in receipts:
        try:
            parsed = _read_json(receipt)
            if not isinstance(parsed, dict):
                raise ValueError("receipt must be a JSON object")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"ERROR: receipt_parse failure for {receipt.stem.split('.')[0]}: {exc}")
    if not any("receipt_parse" in error for error in errors):
        passed.append("receipts")

    # 9. Canonical public routes must be 200 with a final effective URL.
    for route in CANONICAL_ROUTES:
        url = PUBLIC_ROOT + route
        try:
            response = fetch(url, method="HEAD")
            if response.status != 200:
                errors.append(f"ERROR: route_parity failure: {url} returned {response.status} (effective {response.url})")
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            errors.append(f"ERROR: route_parity failure: {url} returned unavailable (effective {url}): {exc}")
    if not any("route_parity" in error for error in errors):
        passed.append("public_routes")

    # Regen parity is intentionally NOT a dimension of this verifier. The
    # on-disk docs/index.html is produced by health-cycle commits which may be
    # one probe cycle behind the live `health/latest.json`, so a byte-exact
    # comparison will report a false drift. The deterministic-safety-net's
    # `verify_release_reproducible.py` is the canonical home for regen parity
    # since it controls the regen timing.
    return errors, warnings, passed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    errors, warnings, passed = verify(args.root.resolve())
    for name in passed:
        print(f"PASS: {name}")
    for message in warnings + errors:
        print(message)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
