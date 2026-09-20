"""Regression coverage for the local/public parity verifier."""

from __future__ import annotations

import json
import hashlib
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


def _public_fetch(served_html: bytes, served_health: bytes, served_tools: set[str], *, index: bytes | None = None):
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
        if url == parity.PUBLIC_HEALTH_INDEX_URL:
            payload = index if index is not None else json.dumps({
                "artifacts": {"health/latest.json": {"sha256": hashlib.sha256(served_health).hexdigest()}},
            }).encode()
            return parity.Response(200, url, "application/json", payload)
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


def test_health_snapshot_digest_match_avoids_served_document_fetch() -> None:
    calls: list[tuple[str, str]] = []
    base = _public_fetch(SOURCE_INDEX, SOURCE_HEALTH, SOURCE_TOOLS)

    def fetch(url: str, **kwargs: Any) -> parity.Response:
        calls.append((url, kwargs.get("method", "GET")))
        return base(url, **kwargs)

    errors, _, passed = parity.verify(ROOT, fetch=fetch)

    assert errors == []
    assert "health_snapshot" in passed
    # Section 9 retains its canonical-route HEAD check; section 6 must not GET
    # the document merely to compute a digest.
    assert not any("/health/latest.json" in url and method == "GET" for url, method in calls)


def test_health_snapshot_digest_mismatch_warns_without_error() -> None:
    local_digest = hashlib.sha256(SOURCE_HEALTH).hexdigest()
    index_digest = "0" * 64
    index = json.dumps({"artifacts": {"health/latest.json": {"sha256": index_digest}}}).encode()

    errors, warnings, _ = parity.verify(
        ROOT, fetch=_public_fetch(SOURCE_INDEX, SOURCE_HEALTH, SOURCE_TOOLS, index=index)
    )

    assert errors == []
    warning = next(
        message
        for message in warnings
        if "health_snapshot" in message and "informational drift" in message
    )
    assert local_digest in warning
    assert index_digest in warning


def test_health_snapshot_unavailable_index_falls_back_to_served_document() -> None:
    calls: list[str] = []
    base = _public_fetch(SOURCE_INDEX, SOURCE_HEALTH, SOURCE_TOOLS)

    def fetch(url: str, **kwargs: Any) -> parity.Response:
        calls.append(url)
        if url == parity.PUBLIC_HEALTH_INDEX_URL:
            raise URLError("index unavailable")
        return base(url, **kwargs)

    errors, warnings, passed = parity.verify(ROOT, fetch=fetch)

    assert errors == []
    assert "health_snapshot" in passed
    assert parity.PUBLIC_ROOT + "/health/latest.json" in calls
    assert any("index digest unavailable" in warning and "index unavailable" in warning for warning in warnings)


def test_health_snapshot_missing_index_digest_falls_back_to_served_document() -> None:
    index = json.dumps({"artifacts": {}}).encode()
    calls: list[str] = []
    base = _public_fetch(SOURCE_INDEX, SOURCE_HEALTH, SOURCE_TOOLS, index=index)

    def fetch(url: str, **kwargs: Any) -> parity.Response:
        calls.append(url)
        return base(url, **kwargs)

    errors, warnings, passed = parity.verify(ROOT, fetch=fetch)

    assert errors == []
    assert "health_snapshot" in passed
    assert parity.PUBLIC_ROOT + "/health/latest.json" in calls
    assert any("index digest unavailable" in warning and "health/latest.json" in warning for warning in warnings)


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
