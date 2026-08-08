import json
import subprocess
import sys
from pathlib import Path


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
