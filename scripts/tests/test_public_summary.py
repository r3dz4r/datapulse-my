from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from scripts.gen_public_summary import GenerationError, STATUS_KEYS, generate


def _write_health(root: Path, *, extra_status: bool = False) -> None:
    statuses = {key: 0 for key in STATUS_KEYS}
    statuses["fresh"] = 1
    if extra_status:
        statuses["alien_status"] = 3
    health = {
        "schema": "datapulse/v0.4/dataset-health",
        "_trust_summary": {
            "checked_at": "2026-09-10T00:00:00Z",
            "datasets_total": 1,
            "by_status": statuses,
        },
    }
    path = root / "health/latest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(health) + "\n", encoding="utf-8")


def test_emits_expected_keys_and_counts_from_real_health_fixture(tmp_path: Path) -> None:
    _write_health(tmp_path)
    (tmp_path / "mcp.json").write_text(json.dumps({"tools": [{"name": "x"}]}), encoding="utf-8")

    generate(tmp_path)

    summary = json.loads((tmp_path / "datapulse_summary.json").read_text(encoding="utf-8"))
    assert summary["schema"] == "datapulse/v0.1/public-summary"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T.*(?:Z|[+-]\d{2}:\d{2})", summary["source_checked_at"])
    assert summary["datasets_total"] == 1
    assert set(summary["by_status"]) == set(STATUS_KEYS)
    assert all(type(value) is int for value in summary["by_status"].values())
    assert sum(summary["by_status"].values()) == summary["datasets_total"]
    assert summary["mcp"]["tools_advertised"] == 1


def test_is_byte_deterministic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_health(tmp_path)
    monkeypatch.setattr("scripts.gen_public_summary._now_iso", lambda: "2026-09-10T00:00:00+00:00")

    generate(tmp_path)
    first = (tmp_path / "datapulse_summary.json").read_bytes()
    generate(tmp_path)

    assert first == (tmp_path / "datapulse_summary.json").read_bytes()


def test_missing_health_raises_GenerationError(tmp_path: Path) -> None:
    with pytest.raises(GenerationError):
        generate(tmp_path)


def test_missing_mcp_manifest_still_emits_with_null_tools(tmp_path: Path) -> None:
    _write_health(tmp_path)

    generate(tmp_path)

    summary = json.loads((tmp_path / "datapulse_summary.json").read_text(encoding="utf-8"))
    assert summary["mcp"]["tools_advertised"] is None


def test_handles_unexpected_status_keys(tmp_path: Path) -> None:
    _write_health(tmp_path, extra_status=True)

    with pytest.raises(GenerationError):
        generate(tmp_path)


def test_committed_summary_matches_committed_health_snapshot() -> None:
    root = Path(__file__).resolve().parents[2]
    summary = json.loads((root / "datapulse_summary.json").read_text(encoding="utf-8"))
    health = json.loads((root / "health/latest.json").read_text(encoding="utf-8"))
    trust = health["_trust_summary"]
    remediations = "python3 scripts/gen_public_summary.py"
    assert summary["source_checked_at"] == trust["checked_at"], remediations
    assert summary["datasets_total"] == trust["datasets_total"], remediations
    assert summary["by_status"] == trust["by_status"], remediations
