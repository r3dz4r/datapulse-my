"""Regression coverage for the local/public parity verifier."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError

from scripts import verify_local_public_parity as parity


ROOT = Path(__file__).resolve().parents[2]
SOURCE_INDEX = (ROOT / "docs/index.html").read_bytes()
SOURCE_HEALTH = (ROOT / "health/latest.json").read_bytes()
SOURCE_TOOLS = {
    tool["name"] for tool in json.loads((ROOT / "mcp.json").read_text(encoding="utf-8"))["tools"]
}


def _fixture_root(tmp_path: Path) -> Path:
    for relative in (
        "datapulse.json",
        "mcp.json",
        "health.schema.json",
        "health/latest.json",
        "docs/index.html",
        "datapulse.schema.json",
        "agent.json",
        "docs/ai-catalog.json",
        "attestations/latest/chain_head.json",
    ):
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    return tmp_path


def _public_fetch(served_html: bytes, served_health: bytes, served_tools: set[str], *, index: bytes | None = None,
                  card_content_type: str = "application/mcp-server-card+json"):
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
        if url.startswith(parity.PUBLIC_ROOT + "/mcp/cards/"):
            # Every advertised card, answered under the type the catalogue
            # declares unless a test asks for the extension-derived default.
            return parity.Response(200, url, card_content_type, b"{}")
        return parity.Response(200, url, "application/json", b"{}")
    return fetch


def _run_clean(root: Path = ROOT) -> tuple[list[str], list[str], list[str]]:
    return parity.verify(
        root,
        fetch=_public_fetch(SOURCE_INDEX, SOURCE_HEALTH, SOURCE_TOOLS),
    )


def test_clean_state_passes() -> None:
    errors, _, passed = _run_clean()
    assert errors == []
    assert {"dataset_count", "tool_count", "taxonomy", "card_media_type"} <= set(passed)


def test_card_served_under_extension_default_fails() -> None:
    """A card served as application/json contradicts the catalogue's declared type."""
    errors, _, passed = parity.verify(
        ROOT,
        fetch=_public_fetch(SOURCE_INDEX, SOURCE_HEALTH, SOURCE_TOOLS, card_content_type="application/json"),
    )

    failure = next(error for error in errors if "card_media_type failure" in error)
    assert "/mcp/cards/" in failure
    assert "'application/json'" in failure
    assert "'application/mcp-server-card+json'" in failure
    # One error per advertised card, never a sample.
    declared_cards = json.loads((ROOT / "docs/ai-catalog.json").read_text(encoding="utf-8"))["entries"]
    assert sum(1 for error in errors if "card_media_type failure" in error) == len(declared_cards)
    assert "card_media_type" not in passed


def test_unavailable_card_fails_closed() -> None:
    base = _public_fetch(SOURCE_INDEX, SOURCE_HEALTH, SOURCE_TOOLS)
    missing = parity.PUBLIC_ROOT + "/mcp/cards/get_dataset.json"

    def fetch(url: str, *, method: str = "GET", body: bytes | None = None,
              headers: dict[str, str] | None = None) -> parity.Response:
        if url == missing:
            raise HTTPError(url, 404, "Not Found", {}, None)
        return base(url, method=method, body=body, headers=headers)

    errors, _, passed = parity.verify(ROOT, fetch=fetch)

    assert any("card_media_type failure" in error and missing in error and "unavailable" in error for error in errors)
    assert "card_media_type" not in passed


def test_wrong_dataset_count_fails(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    path = root / "datapulse.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["datasets"] = payload["datasets"][:-1]
    path.write_text(json.dumps(payload), encoding="utf-8")
    errors, _, _ = _run_clean(root)
    assert any("dataset_count parity failure" in error for error in errors)


def test_wrong_tool_count_fails(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    path = root / "mcp.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    removed = payload["tools"].pop()["name"]
    path.write_text(json.dumps(payload), encoding="utf-8")
    errors, _, _ = _run_clean(root)
    assert any("mcp_tool parity failure" in error and removed in error for error in errors)


def test_taxonomy_violation_fails(tmp_path: Path) -> None:
    root = _fixture_root(tmp_path)
    path = root / "docs/index.html"
    path.write_text(
        path.read_text(encoding="utf-8") + '<article data-status="verified"></article>',
        encoding="utf-8",
    )
    errors, _, _ = _run_clean(root)
    assert any("status_taxonomy violation" in error and '"verified"' in error for error in errors)


def _root_flaky_fetch(exc: Exception, *, failures: int | None) -> tuple[Any, dict[str, int]]:
    """Fail the public-root fetch, leaving every other route healthy.

    ``failures`` counts how many initial root calls raise; ``None`` means every
    root call raises. The counter records root attempts so a test can prove the
    retry boundary, not just the final verdict.
    """
    base = _public_fetch(SOURCE_INDEX, SOURCE_HEALTH, SOURCE_TOOLS)
    counter = {"calls": 0}

    def fetch(url: str, *, method: str = "GET", body: bytes | None = None,
              headers: dict[str, str] | None = None) -> parity.Response:
        # Only the dataset-count GET is made flaky; the later HEAD route probe
        # for the same URL must keep succeeding.
        if method == "GET" and url == parity.PUBLIC_ROOT + "/":
            counter["calls"] += 1
            if failures is None or counter["calls"] <= failures:
                raise exc
        return base(url, method=method, body=body, headers=headers)

    return fetch, counter


def test_transient_transport_failure_is_retried(monkeypatch: Any) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr("time.sleep", sleeps.append)
    fetch, counter = _root_flaky_fetch(URLError("connection reset by peer"), failures=2)

    errors, _, passed = parity.verify(ROOT, fetch=fetch)

    assert errors == []
    assert "dataset_count" in passed
    assert counter["calls"] == 3
    assert sleeps == [0.5, 1.5]


def test_exhausted_transport_retries_report_documented_failure(monkeypatch: Any) -> None:
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    fetch, counter = _root_flaky_fetch(URLError("connection reset by peer"), failures=None)

    errors, _, _ = parity.verify(ROOT, fetch=fetch)

    assert counter["calls"] == 3
    failure = next(error for error in errors if "dataset_count parity failure" in error)
    assert failure.startswith("ERROR: dataset_count parity failure: public root unavailable: ")


def test_http_error_is_not_retried(monkeypatch: Any) -> None:
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    fetch, counter = _root_flaky_fetch(
        HTTPError(parity.PUBLIC_ROOT + "/", 404, "Not Found", {}, None),
        failures=None,
    )

    errors, _, _ = parity.verify(ROOT, fetch=fetch)

    # A real server answer must surface after one call, never three.
    assert counter["calls"] == 1
    assert any("dataset_count parity failure" in error and "public root unavailable" in error for error in errors)


def test_retry_warning_names_attempt_and_error(monkeypatch: Any, capsys: Any) -> None:
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    fetch, counter = _root_flaky_fetch(URLError("connection reset by peer"), failures=1)

    errors, _, _ = parity.verify(ROOT, fetch=fetch)

    assert errors == []
    assert counter["calls"] == 2
    warnings = [line for line in capsys.readouterr().out.splitlines() if line.startswith("WARNING:")]
    assert len(warnings) == 1
    assert "2/3" in warnings[0]
    assert "URLError" in warnings[0]
