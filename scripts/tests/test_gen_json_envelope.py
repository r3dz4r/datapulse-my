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


def _refuse_urlopen(calls: list[object]):
    def urlopen(*args: object, **kwargs: object) -> None:
        calls.append((args, kwargs))
        raise AssertionError("an isolated build must not call urlopen")

    return urlopen


def _seed_root(tmp_path: Path, urls: list[str]) -> Path:
    root = tmp_path / "root"
    write_json(
        root / "datapulse.json",
        {"datasets": [{"id": f"set_{index}", "url": url} for index, url in enumerate(urls)]
         + [{"id": "rapid_gtfs", "url": "https://example.test/gtfs.zip"}]},
    )
    return root


def test_seeded_cache_serves_isolated_build_without_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = "https://example.test/alpha.csv"
    payload = b"date,count\n2026-08-01,1\n"
    cache = tmp_path / "cache"
    monkeypatch.delenv("DATAPULSE_ISOLATED_REPRODUCIBILITY_BUILD", raising=False)
    stub = _stub_urlopen(payload, "text/csv")
    monkeypatch.setattr(envelope.urllib.request, "urlopen", stub)
    assert envelope.seed_source_cache(_seed_root(tmp_path, [url]), cache) == 1
    assert len(stub.calls) == 1

    calls: list[object] = []
    monkeypatch.setattr(envelope.urllib.request, "urlopen", _refuse_urlopen(calls))
    monkeypatch.setenv("DATAPULSE_ENVELOPE_SOURCE_CACHE", str(cache))
    monkeypatch.setenv("DATAPULSE_ISOLATED_REPRODUCIBILITY_BUILD", "1")
    assert envelope.fetch_source(url) == (payload, "text/csv")
    assert calls == []


def test_seed_pins_failure_so_both_isolated_builds_degrade_identically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    url = "https://example.test/alpha.csv"
    cache = tmp_path / "cache"
    monkeypatch.delenv("DATAPULSE_ISOLATED_REPRODUCIBILITY_BUILD", raising=False)

    def urlopen(*args: object, **kwargs: object) -> None:
        raise OSError("upstream down")

    monkeypatch.setattr(envelope.urllib.request, "urlopen", urlopen)
    envelope.seed_source_cache(_seed_root(tmp_path, [url]), cache)
    assert "alpha.csv: upstream down" in capsys.readouterr().err
    bin_path, json_path = _cache_paths(cache, url)
    assert not bin_path.exists()
    assert json.loads(json_path.read_text(encoding="utf-8")) == {"unavailable": "upstream down"}

    calls: list[object] = []
    monkeypatch.setattr(envelope.urllib.request, "urlopen", _refuse_urlopen(calls))
    monkeypatch.setenv("DATAPULSE_ENVELOPE_SOURCE_CACHE", str(cache))
    monkeypatch.setenv("DATAPULSE_ISOLATED_REPRODUCIBILITY_BUILD", "1")
    with pytest.raises(OSError, match="unavailable when the source cache was seeded: upstream down"):
        envelope.fetch_source(url)
    first = envelope.build_envelope(tmp_path, {"id": "alpha", "url": url}, {})
    second = envelope.build_envelope(tmp_path, {"id": "alpha", "url": url}, {})
    assert first == second
    assert first["fields"] == []
    assert "Fields are inferred at the next probe run." in first["known_quirks"]
    assert calls == []


def test_seed_cache_write_failure_is_loud(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("", encoding="utf-8")
    monkeypatch.delenv("DATAPULSE_ISOLATED_REPRODUCIBILITY_BUILD", raising=False)
    monkeypatch.setattr(envelope.urllib.request, "urlopen", _stub_urlopen(b"a\n1\n"))
    with pytest.raises(OSError):
        envelope.seed_source_cache(_seed_root(tmp_path, ["https://example.test/a.csv"]), blocker)


def test_seed_refuses_inside_isolated_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[object] = []
    monkeypatch.setattr(envelope.urllib.request, "urlopen", _refuse_urlopen(calls))
    monkeypatch.setenv("DATAPULSE_ISOLATED_REPRODUCIBILITY_BUILD", "1")
    with pytest.raises(envelope.SourceCacheMiss, match="must not seed"):
        envelope.seed_source_cache(_seed_root(tmp_path, ["https://example.test/a.csv"]), tmp_path / "cache")
    assert calls == []


def test_isolated_miss_fails_loudly_without_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = "https://example.test/alpha.csv"
    cache = tmp_path / "cache"
    cache.mkdir()
    calls: list[object] = []
    monkeypatch.setattr(envelope.urllib.request, "urlopen", _refuse_urlopen(calls))
    monkeypatch.setenv("DATAPULSE_ISOLATED_REPRODUCIBILITY_BUILD", "1")

    monkeypatch.delenv("DATAPULSE_ENVELOPE_SOURCE_CACHE", raising=False)
    with pytest.raises(envelope.SourceCacheMiss, match=r"no DATAPULSE_ENVELOPE_SOURCE_CACHE .*alpha\.csv"):
        envelope.fetch_source(url)

    monkeypatch.setenv("DATAPULSE_ENVELOPE_SOURCE_CACHE", str(cache))
    with pytest.raises(envelope.SourceCacheMiss, match=r"no cached source for https://example\.test/alpha\.csv"):
        envelope.fetch_source(url)
    with pytest.raises(envelope.SourceCacheMiss):
        envelope.build_envelope(tmp_path, {"id": "alpha", "url": url}, {})
    assert calls == []


def test_isolated_generator_exits_nonzero_naming_the_missed_source(tmp_path: Path) -> None:
    url = "https://example.test/alpha.csv"
    write_json(tmp_path / "datapulse.json", {"datasets": [{"id": "alpha", "url": url}]})
    write_json(tmp_path / "health/latest.json", {"datasets": [{"dataset_id": "alpha", "status": "fresh"}]})
    cache = tmp_path / "cache"
    cache.mkdir()

    result = subprocess.run(
        [sys.executable, str(GENERATOR), "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        env={
            "PATH": "/usr/bin:/bin",
            "DATAPULSE_ISOLATED_REPRODUCIBILITY_BUILD": "1",
            "DATAPULSE_ENVELOPE_SOURCE_CACHE": str(cache),
        },
    )

    assert result.returncode == 1
    assert f"no cached source for {url}" in result.stderr
    assert not (tmp_path / "data/json/alpha.json").exists()


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


def test_isolated_partial_or_unreadable_cache_is_a_miss_not_a_live_fetch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = "https://example.test/alpha.csv"
    cache = tmp_path / "cache"
    cache.mkdir()
    bin_path, json_path = _cache_paths(cache, url)
    monkeypatch.setenv("DATAPULSE_ENVELOPE_SOURCE_CACHE", str(cache))
    monkeypatch.setenv("DATAPULSE_ISOLATED_REPRODUCIBILITY_BUILD", "1")
    calls: list[object] = []
    monkeypatch.setattr(envelope.urllib.request, "urlopen", _refuse_urlopen(calls))

    json_path.write_text(json.dumps({"content_type": "text/csv"}), encoding="utf-8")
    with pytest.raises(envelope.SourceCacheMiss, match="alpha.csv"):
        envelope.fetch_source(url)

    bin_path.write_bytes(b"stale")
    json_path.write_text("{", encoding="utf-8")
    with pytest.raises(envelope.SourceCacheMiss, match="alpha.csv"):
        envelope.fetch_source(url)

    json_path.write_text(json.dumps({"unavailable": "upstream down"}), encoding="utf-8")
    with pytest.raises(envelope.SourceCacheMiss, match="alpha.csv"):
        envelope.fetch_source(url)
    assert calls == []
