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


def test_read_token_requires_explicit_environment_without_fallback_read(monkeypatch: object) -> None:
    module = _module()
    monkeypatch.delenv(module.TOKEN_ENV, raising=False)  # type: ignore[attr-defined]

    def fail_read(*_args: object, **_kwargs: object) -> str:
        raise AssertionError("credential lookup must not read a fallback file")

    monkeypatch.setattr(module.Path, "read_text", fail_read)  # type: ignore[attr-defined]
    try:
        module.read_token()
    except module.PublishError as exc:
        assert str(exc) == "KV credential unavailable: token is unset"
    else:
        raise AssertionError("missing explicit credential should fail safely")


def test_read_token_accepts_explicit_environment_credential(monkeypatch: object) -> None:
    module = _module()
    monkeypatch.setenv(module.TOKEN_ENV, "injected-test-token")  # type: ignore[attr-defined]

    assert module.read_token() == "injected-test-token"


def test_failure_is_explicit_and_has_a_machine_readable_verdict(tmp_path: Path) -> None:
    health = tmp_path / "latest.json"
    _health(health)
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--health", str(health), "--api-base", "http://127.0.0.1:1"],
        capture_output=True,
        text=True,
        check=False,
        env={
            "DATAPULSE_KV_WRITE": "test-token",
            "DATAPULSE_KV_PUBLICATION_STATE": str(tmp_path / "publication-state.json"),
        },
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
    monkeypatch.setenv(module.PUBLISH_STATE_ENV, str(tmp_path / "publication-state.json"))
    monkeypatch.setattr(module, "publish_unchanged_aware_with_retry", lambda *_args: (2, 5))
    assert module.main(["--health", str(health)]) == 0
    assert "health index publish succeeded: 2 written, 5 unchanged" in capsys.readouterr().err  # type: ignore[attr-defined]

    message = "secret-token\n" + "x" * 250
    line = module._failure_line("health index publish failed", module.PublishError(message), "secret-token")
    assert "\n" not in line
    assert "secret-token" not in line
    assert len(line.rsplit(": ", 1)[1]) <= 200


def test_main_cadence_skip_is_successful_and_issues_no_publication(monkeypatch: object, capsys: object, tmp_path: Path) -> None:
    module = _module()
    health = tmp_path / "latest.json"
    _health(health)
    calls = 0
    monkeypatch.setattr(module, "read_token", lambda: "secret-token")
    monkeypatch.setenv(module.PUBLISH_STATE_ENV, str(tmp_path / "publication-state.json"))
    monkeypatch.setattr(module.time, "time", lambda: 1_000.0)

    def publish_once(*_args: object) -> tuple[int, int]:
        nonlocal calls
        calls += 1
        return 1, 6

    monkeypatch.setattr(module, "publish_unchanged_aware_with_retry", publish_once)
    assert module.main(["--health", str(health)]) == 0
    assert module.main(["--health", str(health)]) == 0
    assert calls == 1
    assert "health index publish skipped: cadence window active" in capsys.readouterr().err


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


def test_cadence_publishes_first_run_skips_then_recovers(tmp_path: Path) -> None:
    module = _module()
    state_path = tmp_path / "state" / "kv-publication.json"
    calls: list[float] = []

    def publish_once() -> tuple[int, int]:
        calls.append(1.0)
        return 3, 4

    assert module.publish_with_cadence(state_path, 1_000.0, 1_800.0, publish_once) == (False, 3, 4)
    assert module.publish_with_cadence(state_path, 1_100.0, 1_800.0, publish_once) == (True, 0, 0)
    assert module.publish_with_cadence(state_path, 2_800.0, 1_800.0, publish_once) == (False, 3, 4)
    assert len(calls) == 2


def test_cadence_missing_or_corrupt_state_allows_one_publication(tmp_path: Path) -> None:
    module = _module()
    state_path = tmp_path / "kv-publication.json"
    calls: list[float] = []

    def publish_once() -> tuple[int, int]:
        calls.append(1.0)
        return 0, 7

    assert module.publish_with_cadence(state_path, 1_000.0, 1_800.0, publish_once) == (False, 0, 7)
    state_path.write_text("not-json", encoding="utf-8")
    assert module.publish_with_cadence(state_path, 1_100.0, 1_800.0, publish_once) == (False, 0, 7)
    assert len(calls) == 2


def test_cadence_reservation_survives_http_failure(tmp_path: Path) -> None:
    module = _module()
    state_path = tmp_path / "kv-publication.json"
    calls = 0

    def fail_publish() -> tuple[int, int]:
        nonlocal calls
        calls += 1
        raise module.PublishError("HTTP 429")

    try:
        module.publish_with_cadence(state_path, 1_000.0, 1_800.0, fail_publish)
    except module.PublishError:
        pass
    else:
        raise AssertionError("HTTP failure must be returned")
    assert module.publish_with_cadence(state_path, 1_100.0, 1_800.0, fail_publish) == (True, 0, 0)
    assert calls == 1


def test_default_daily_kv_write_budget_is_below_free_quota() -> None:
    module = _module()
    assert module.MAX_PUBLISH_ATTEMPTS == 2
    assert module.max_daily_kv_writes() == len(module.HEALTH_ARTIFACTS + (module.KEY,)) * 48 * 2
    assert module.max_daily_kv_writes() == 672
    assert module.max_daily_kv_writes() < 1_000


def test_invalid_cadence_interval_is_rejected(monkeypatch: object) -> None:
    module = _module()
    monkeypatch.setenv(module.PUBLISH_INTERVAL_ENV, "0")
    try:
        module.publication_interval_seconds()
    except module.PublishError as exc:
        assert "positive number" in str(exc)
    else:
        raise AssertionError("non-positive cadence must be rejected")
