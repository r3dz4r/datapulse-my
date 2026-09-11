import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import gen_json_envelope as envelope


ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "scripts/gen_json_envelope.py"
CANONICAL_KEYS = [
    "schema",
    "id",
    "status",
    "last_checked",
    "freshness_days",
    "next_expected_update",
    "refresh_frequency",
    "record_count",
    "date_range",
    "fields",
    "checks",
    "known_quirks",
    "breaking_changes",
    "reproducibility",
    "licence",
    "attribution",
]


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _cache_paths(cache_dir: Path, url: str) -> tuple[Path, Path]:
    key = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return cache_dir / f"{key}.bin", cache_dir / f"{key}.json"


def _stub_urlopen(payload: bytes, content_type: str | None = "text/csv"):
    calls: list[object] = []

    class Headers:
        def get_content_type(self) -> str | None:
            return content_type

    class Response:
        headers = Headers()

        def read(self, _size: int) -> bytes:
            return payload

        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def urlopen(request: object, timeout: object = None) -> Response:
        calls.append((request, timeout))
        return Response()

    urlopen.calls = calls
    return urlopen


def test_generator_writes_canonical_envelopes_from_two_row_fixture(tmp_path: Path) -> None:
    csv_source = tmp_path / "alpha.csv"
    csv_source.write_text("date,count,active\n2026-08-01,12,true\n", encoding="utf-8")
    json_source = tmp_path / "beta.json"
    write_json(json_source, [{"name": "example", "score": 2.5}])
    manifest = {
        "datasets": [
            {
                "id": "alpha",
                "source": "Fixture CSV",
                "url": csv_source.as_uri(),
                "refresh_frequency": "daily",
                "licence": "CC BY 4.0",
                "namespace": "fixture",
                "health_report": "data/alpha.md",
            },
            {
                "id": "beta",
                "source": "Fixture JSON",
                "url": json_source.as_uri(),
                "refresh_frequency": "monthly",
                "licence": "OGL",
                "namespace": "fixture",
                "health_report": "data/beta.md",
                "probe_note": "Probe pending",
            },
        ]
    }
    health = {
        "datasets": [
            {
                "dataset_id": "alpha",
                "status": "fresh",
                "last_checked": "2026-08-09T00:00:00Z",
                "staleness_days": 1,
                "record_count": 1,
                "date_range": {"start": "2026-08-01", "end": "2026-08-01"},
                "http_status": 200,
                "access_method": "direct curl GET",
                "column_count": 3,
                "content_shape_changed": False,
            },
            {
                "dataset_id": "beta",
                "status": "unknown-freshness",
                "last_checked": "2026-08-08T00:00:00Z",
                "staleness_days": None,
                "record_count": None,
                "estimated_record_count": 1,
                "date_range": None,
                "http_status": 200,
                "access_method": "direct curl GET",
                "column_count": 2,
                "content_shape_changed": False,
            },
        ]
    }
    write_json(tmp_path / "datapulse.json", manifest)
    write_json(tmp_path / "health/latest.json", health)
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data/alpha.md").write_text(
        "## Known quirks\n\n- Dates are daily.\n\n## Breaking changes\n\n- None.\n",
        encoding="utf-8",
    )
    (tmp_path / "data/beta.md").write_text("# Beta\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(GENERATOR), "--root", str(tmp_path)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Generated 2 envelope(s)." in result.stdout
    alpha = json.loads((tmp_path / "data/json/alpha.json").read_text(encoding="utf-8"))
    beta = json.loads((tmp_path / "data/json/beta.json").read_text(encoding="utf-8"))
    assert list(alpha) == CANONICAL_KEYS
    assert list(beta) == CANONICAL_KEYS
    assert alpha["schema"] == "datapulse/v0.1/dataset-health"
    assert alpha["id"] == "alpha"
    assert alpha["status"] == "fresh"
    assert alpha["freshness_days"] == 1
    assert alpha["record_count"] == 1
    assert alpha["date_range"] == {"start": "2026-08-01", "end": "2026-08-01"}
    assert alpha["fields"] == [
        {"name": "date", "type": "date"},
        {"name": "count", "type": "integer"},
        {"name": "active", "type": "boolean"},
    ]
    assert alpha["known_quirks"] == ["Dates are daily."]
    assert alpha["breaking_changes"] == []
    assert alpha["reproducibility"] == {
        "url": csv_source.as_uri(),
        "access_method": "curl",
    }
    assert alpha["licence"] == "CC BY 4.0"
    assert alpha["attribution"] == "Fixture CSV (fixture)"
    assert beta["record_count"] == 1
    assert beta["fields"] == [
        {"name": "name", "type": "string"},
        {"name": "score", "type": "number"},
    ]
    assert [check["name"] for check in beta["checks"]] == [
        "file_reachable",
        "row_count",
        "freshness",
        "schema_stable",
    ]


def test_fetch_source_uses_preseeded_cache_without_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = "https://example.test/alpha.csv"
    payload = b"date,count\n2026-08-01,1\n"
    cache = tmp_path / "cache"
    cache.mkdir()
    bin_path, json_path = _cache_paths(cache, url)
    bin_path.write_bytes(payload)
    json_path.write_text(json.dumps({"content_type": "text/csv"}), encoding="utf-8")
    monkeypatch.setenv("DATAPULSE_ENVELOPE_SOURCE_CACHE", str(cache))
    monkeypatch.setenv("DATAPULSE_ISOLATED_REPRODUCIBILITY_BUILD", "1")
    calls: list[object] = []

    def urlopen(*args: object, **kwargs: object) -> None:
        calls.append((args, kwargs))
        raise AssertionError("urlopen should not be called on cache hit")

    monkeypatch.setattr(envelope.urllib.request, "urlopen", urlopen)
    assert envelope.fetch_source(url) == (payload, "text/csv")
    assert calls == []


def test_fetch_source_second_call_is_served_from_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = "https://example.test/alpha.csv"
    payload = b"date,count\n2026-08-01,1\n"
    cache = tmp_path / "cache"
    monkeypatch.setenv("DATAPULSE_ENVELOPE_SOURCE_CACHE", str(cache))
    monkeypatch.setenv("DATAPULSE_ISOLATED_REPRODUCIBILITY_BUILD", "1")
    stub = _stub_urlopen(payload, "text/csv")
    monkeypatch.setattr(envelope.urllib.request, "urlopen", stub)
    assert envelope.fetch_source(url) == (payload, "text/csv")
    assert stub.calls

    calls: list[object] = []

    def urlopen(*args: object, **kwargs: object) -> None:
        calls.append((args, kwargs))
        raise AssertionError("urlopen should not be called on cache hit")

    monkeypatch.setattr(envelope.urllib.request, "urlopen", urlopen)
    assert envelope.fetch_source(url) == (payload, "text/csv")
    assert calls == []


def test_fetch_source_failure_does_not_write_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = "https://example.test/alpha.csv"
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setenv("DATAPULSE_ENVELOPE_SOURCE_CACHE", str(cache))
    monkeypatch.setenv("DATAPULSE_ISOLATED_REPRODUCIBILITY_BUILD", "1")

    def urlopen(*args: object, **kwargs: object) -> None:
        raise OSError("upstream down")

    monkeypatch.setattr(envelope.urllib.request, "urlopen", urlopen)
    with pytest.raises(OSError, match="upstream down"):
        envelope.fetch_source(url)
    assert list(cache.iterdir()) == []


def test_fetch_source_ignores_cache_when_isolated_build_switch_is_off(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = "https://example.test/alpha.csv"
    live_payload = b"live-bytes"
    cached_payload = b"cached-bytes"
    cache = tmp_path / "cache"
    cache.mkdir()
    bin_path, json_path = _cache_paths(cache, url)
    bin_path.write_bytes(cached_payload)
    json_path.write_text(json.dumps({"content_type": "text/csv"}), encoding="utf-8")
    before = {path.name: path.read_bytes() for path in cache.iterdir()}
    monkeypatch.setenv("DATAPULSE_ENVELOPE_SOURCE_CACHE", str(cache))
    monkeypatch.delenv("DATAPULSE_ISOLATED_REPRODUCIBILITY_BUILD", raising=False)
    stub = _stub_urlopen(live_payload, "text/plain")
    monkeypatch.setattr(envelope.urllib.request, "urlopen", stub)
    assert envelope.fetch_source(url) == (live_payload, "text/plain")
    assert stub.calls
    assert {path.name: path.read_bytes() for path in cache.iterdir()} == before


def test_fetch_source_without_cache_env_fetches_live(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DATAPULSE_ENVELOPE_SOURCE_CACHE", raising=False)
    monkeypatch.chdir(tmp_path)
    payload = b"live-bytes"
    stub = _stub_urlopen(payload, "text/plain")
    monkeypatch.setattr(envelope.urllib.request, "urlopen", stub)
    assert envelope.fetch_source("https://example.test/alpha.csv") == (payload, "text/plain")
    assert stub.calls
    assert list(tmp_path.iterdir()) == []


def test_fetch_source_partial_or_unreadable_cache_falls_back_to_live(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = "https://example.test/alpha.csv"
    payload = b"live-bytes"
    cache = tmp_path / "cache"
    cache.mkdir()
    bin_path, json_path = _cache_paths(cache, url)
    monkeypatch.setenv("DATAPULSE_ENVELOPE_SOURCE_CACHE", str(cache))
    monkeypatch.setenv("DATAPULSE_ISOLATED_REPRODUCIBILITY_BUILD", "1")
    stub = _stub_urlopen(payload, "text/csv")
    monkeypatch.setattr(envelope.urllib.request, "urlopen", stub)

    json_path.write_text(json.dumps({"content_type": "text/csv"}), encoding="utf-8")
    assert envelope.fetch_source(url) == (payload, "text/csv")
    assert len(stub.calls) == 1

    bin_path.write_bytes(b"stale")
    json_path.write_text("{", encoding="utf-8")
    assert envelope.fetch_source(url) == (payload, "text/csv")
    assert len(stub.calls) == 2
