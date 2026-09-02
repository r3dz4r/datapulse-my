"""Regression coverage for the local/public parity verifier."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts import verify_local_public_parity as parity


ROOT = Path(__file__).resolve().parents[2]
SOURCE_INDEX = (ROOT / "docs/index.html").read_bytes()
SOURCE_HEALTH = (ROOT / "health/latest.json").read_bytes()
SOURCE_TOOLS = {
    tool["name"] for tool in json.loads((ROOT / "mcp.json").read_text(encoding="utf-8"))["tools"]
}


def _public_fetch(served_html: bytes, served_health: bytes, served_tools: set[str]):
    """Return a deterministic public-only substitute for the verifier's transport."""
    def fetch(url: str, *, method: str = "GET", body: bytes | None = None,
              headers: dict[str, str] | None = None) -> parity.Response:
        del headers
        if method == "HEAD":
            return parity.Response(200, url, "text/html", b"")
        if url == parity.PUBLIC_ROOT + "/":
            return parity.Response(200, url, "text/html", served_html)
        if url == parity.PUBLIC_ROOT + "/health/latest.json":
            return parity.Response(200, url, "application/json", served_health)
        if url == parity.MCP_ENDPOINT:
            # The verifier performs initialize, notification, then tools/list.
            if body and b'"tools/list"' in body:
                payload: dict[str, Any] = {"result": {"tools": [{"name": name} for name in sorted(served_tools)]}}
            else:
                payload = {"result": {"sessionId": "fixture"}}
            return parity.Response(200, url, "application/json", json.dumps(payload).encode())
        return parity.Response(200, url, "application/json", b"{}")
    return fetch


def _run_clean() -> tuple[list[str], list[str], list[str]]:
    return parity.verify(
        ROOT,
        fetch=_public_fetch(SOURCE_INDEX, SOURCE_HEALTH, SOURCE_TOOLS),
    )


def test_clean_state_passes() -> None:
    errors, _, passed = _run_clean()
    assert errors == []
    assert {"dataset_count", "tool_count", "taxonomy"} <= set(passed)


def test_wrong_dataset_count_fails() -> None:
    path = ROOT / "datapulse.json"
    original = path.read_text(encoding="utf-8")
    try:
        payload = json.loads(original)
        payload["datasets"] = payload["datasets"][:-1]
        path.write_text(json.dumps(payload), encoding="utf-8")
        errors, _, _ = _run_clean()
        assert any("dataset_count parity failure" in error for error in errors)
    finally:
        path.write_text(original, encoding="utf-8")


def test_wrong_tool_count_fails() -> None:
    path = ROOT / "mcp.json"
    original = path.read_text(encoding="utf-8")
    try:
        payload = json.loads(original)
        removed = payload["tools"].pop()["name"]
        path.write_text(json.dumps(payload), encoding="utf-8")
        errors, _, _ = _run_clean()
        assert any("mcp_tool parity failure" in error and removed in error for error in errors)
    finally:
        path.write_text(original, encoding="utf-8")


def test_taxonomy_violation_fails() -> None:
    path = ROOT / "docs/index.html"
    original = path.read_text(encoding="utf-8")
    try:
        path.write_text(original + '<article data-status="verified"></article>', encoding="utf-8")
        errors, _, _ = _run_clean()
        assert any("status_taxonomy violation" in error and '"verified"' in error for error in errors)
    finally:
        path.write_text(original, encoding="utf-8")
