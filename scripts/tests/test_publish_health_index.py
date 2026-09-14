from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/publish_health_index.py"


def _module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("publish_health_index_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _health(path: Path) -> None:
    path.write_text(json.dumps({
        "schema": "datapulse/v1/health",
        "checked_at": "2026-09-13T00:00:00Z",
        "_trust_summary": {"datasets_total": 1},
        "datasets": [{
            "dataset_id": "sample", "status": "fresh", "content_freshness_date": "2026-09-12",
            "last_checked": "2026-09-13T00:00:00Z", "access_method": "api", "record_count": 7,
            "staleness_status": "fresh", "publisher": "Publisher", "category": "Category",
            "name": "Name", "url": "https://example.test", "quality_profile": {"large": True},
        }],
    }), encoding="utf-8")
    for name in (
        "history_daily.json",
        "drift.json",
        "trends.json",
        "reconciliation.json",
        "evidence-coverage.json",
    ):
        (path.parent / name).write_text(json.dumps({"name": name}), encoding="utf-8")


def test_projection_is_exactly_allowlisted_and_stable(tmp_path: Path) -> None:
    module = _module()
    health = tmp_path / "latest.json"
    _health(health)

    first = module.build_projection(health)
    second = module.build_projection(health)
    projection = json.loads(first)

    assert first == second
    assert set(projection) == {"schema", "checked_at", "_trust_summary", "datasets"}
    assert set(projection["datasets"][0]) == set(module.DATASET_KEYS)
    assert not {"publisher", "category", "name", "url"} & set(projection["datasets"][0])


def test_failure_is_explicit_and_has_a_machine_readable_verdict(tmp_path: Path) -> None:
    health = tmp_path / "latest.json"
    _health(health)
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--health", str(health), "--api-base", "http://127.0.0.1:1"],
        capture_output=True, text=True, check=False, env={"DATAPULSE_KV_WRITE": "test-token"},
    )

    assert result.returncode == 2
    assert "health index publish failed: PublishError:" in result.stderr


def test_request_uses_operation_socket_timeout_not_connect_timeout(monkeypatch: object) -> None:
    module = _module()
    constructed: list[float] = []
    socket_timeouts: list[float] = []

    class Socket:
        def settimeout(self, timeout: float) -> None:
            socket_timeouts.append(timeout)

    class Response:
        status = 200

        def read(self) -> bytes:
            return b"ok"

    class Connection:
        sock = Socket()

        def __init__(self, _host: str, _port: int | None, timeout: float) -> None:
            constructed.append(timeout)
            self.timeout = timeout

        def connect(self) -> None:
            return None

        def request(self, *_args: object, **_kwargs: object) -> None:
            return None

        def getresponse(self) -> Response:
            return Response()

        def close(self) -> None:
            return None

    monkeypatch.setattr(module.http.client, "HTTPConnection", Connection)  # type: ignore[attr-defined]
    module.request_bytes("GET", "http://example.test/value", "token")

    assert constructed == [module.SOCKET_TIMEOUT_SECONDS]
    assert socket_timeouts == [module.SOCKET_TIMEOUT_SECONDS]


def test_publish_retries_once_after_timeout_then_succeeds(monkeypatch: object) -> None:
    module = _module()
    attempts = 0

    def publish_once(*_args: object) -> tuple[int, int]:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise TimeoutError("read timed out")
        return 3, 4

    monkeypatch.setattr(module, "publish_unchanged_aware", publish_once)
    assert module.publish_unchanged_aware_with_retry("api", "token", {"key": b"value"}) == (3, 4)
    assert attempts == 2


def test_publish_does_not_retry_http_4xx(monkeypatch: object) -> None:
    module = _module()
    attempts = 0

    def publish_once(*_args: object) -> tuple[int, int]:
        nonlocal attempts
        attempts += 1
        raise module.PublishError("HTTP 403")

    monkeypatch.setattr(module, "publish_unchanged_aware", publish_once)
    try:
        module.publish_unchanged_aware_with_retry("api", "token", {"key": b"value"})
    except module.PublishError:
        pass
    else:
        raise AssertionError("HTTP 4xx should fail")
    assert attempts == 1


def test_main_returns_zero_after_success_and_failure_line_is_bounded(monkeypatch: object, capsys: object, tmp_path: Path) -> None:
    module = _module()
    health = tmp_path / "latest.json"
    _health(health)
    monkeypatch.setattr(module, "read_token", lambda: "secret-token")
    monkeypatch.setattr(module, "publish_unchanged_aware_with_retry", lambda *_args: (2, 5))
    assert module.main(["--health", str(health)]) == 0
    assert "health index publish succeeded: 2 written, 5 unchanged" in capsys.readouterr().err  # type: ignore[attr-defined]

    message = "secret-token\n" + "x" * 250
    line = module._failure_line("health index publish failed", module.PublishError(message), "secret-token")
    assert "\n" not in line
    assert "secret-token" not in line
    assert len(line.rsplit(": ", 1)[1]) <= 200


def test_dry_run_makes_no_network_call(tmp_path: Path, monkeypatch: object) -> None:
    module = _module()
    health = tmp_path / "latest.json"
    _health(health)

    def fail_request(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("network call during dry-run")

    monkeypatch.setattr(module, "request_bytes", fail_request)  # type: ignore[attr-defined]
    assert module.main(["--health", str(health), "--dry-run"]) == 0


def test_publish_skips_byte_identical_values(tmp_path: Path, monkeypatch: object) -> None:
    module = _module()
    health = tmp_path / "latest.json"
    _health(health)
    payloads = module.health_payloads(health)
    writes: list[str] = []

    monkeypatch.setattr(module, "resolve_account_id", lambda *_args: "account")
    monkeypatch.setattr(module, "read_value", lambda _base, _account, _token, key: payloads[key])
    monkeypatch.setattr(module, "publish_value", lambda _base, _account, _token, key, _payload: writes.append(key))

    assert module.publish_unchanged_aware("https://api.example.test", "token", payloads) == (0, len(payloads))
    assert writes == []
