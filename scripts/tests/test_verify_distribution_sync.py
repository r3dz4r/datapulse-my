from __future__ import annotations

import json
from pathlib import Path

from scripts.embed_dashboard_data import NPRA_DATASET_IDS
from scripts.verify_distribution_sync import verify_distribution_sync


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def _stage_current_surfaces(root: Path, dataset_count: int = 2) -> None:
    datasets = [{"id": f"dataset-{index}"} for index in range(dataset_count)]
    _write_json(root / "datapulse.json", {"datasets": datasets})
    _write_json(root / "health/latest.json", {"results": []})
    _write_json(
        root / "mcp.json",
        {
            "server": {"description": f"Read-only access to {dataset_count} datasets."},
            "tools": [
                {"name": "search_datasets", "description": f"Search {dataset_count} datasets."},
                {"name": "get_dataset", "description": "Read one dataset."},
            ],
        },
    )
    _write_json(
        root / "config/public-surfaces.json",
        {"pages": ["/", "/npra.html"], "artifacts": ["/llms.txt", "/agent.json", "/mcp.json"]},
    )
    (root / "README.md").write_text(f"DataPulse has {dataset_count} datasets and 2 tools.\n", encoding="utf-8")
    (root / "llms.txt").write_text(f"DataPulse has {dataset_count} datasets and 2 tools.\n", encoding="utf-8")
    _write_json(root / "agent.json", {"description": f"{dataset_count} datasets", "capabilities": {"mcp_server": {"tools": 2}}})
    _write_json(root / "server.json", {"description": f"Read-only discovery for {dataset_count} datasets."})
    _write_json(root / "glama.json", {"description": f"{dataset_count} datasets and 2 tools"})
    (root / "docs/mcp-reference.md").parent.mkdir(parents=True, exist_ok=True)
    (root / "docs/mcp-reference.md").write_text(f"{dataset_count} datasets; 2 tools.\n", encoding="utf-8")
    (root / "docs/ai-directory-listings.md").write_text(f"{dataset_count} datasets; 2 tools.\n", encoding="utf-8")
    (root / "docs/index.html").write_text(f"{dataset_count} datasets; 2 tools.\n", encoding="utf-8")
    _write_json(root / "docs/mcp/cards/search_datasets.json", {"dataset_count": dataset_count, "description": f"Search {dataset_count} datasets."})


def test_current_surfaces_match_canonical_counts(tmp_path: Path) -> None:
    _stage_current_surfaces(tmp_path)

    report = verify_distribution_sync(tmp_path)

    assert report.dataset_count == 2
    assert report.tool_count == 2
    assert report.failures == []
    assert "docs/mcp/cards/search_datasets.json" in report.checked_surfaces


def test_stale_claims_fail_without_scanning_historical_artifacts(tmp_path: Path) -> None:
    _stage_current_surfaces(tmp_path)
    (tmp_path / "README.md").write_text("DataPulse has 389 datasets.\n", encoding="utf-8")
    _write_json(tmp_path / "docs/mcp/cards/search_datasets.json", {"dataset_count": 389})
    historical = tmp_path / "docs/AUDIT-2026-01-01.md"
    historical.write_text("Historical snapshot: 389 datasets.\n", encoding="utf-8")

    report = verify_distribution_sync(tmp_path)

    assert any("README.md" in failure and "389 datasets" in failure for failure in report.failures)
    assert any("docs/mcp/cards/search_datasets.json" in failure and "dataset_count" in failure for failure in report.failures)
    assert all("AUDIT-2026-01-01.md" not in failure for failure in report.failures)
    assert "docs/AUDIT-2026-01-01.md" in report.excluded_historical_paths


def test_registered_npra_surface_allows_its_canonical_vertical_count(tmp_path: Path) -> None:
    _stage_current_surfaces(tmp_path, dataset_count=10)
    manifest = json.loads((tmp_path / "datapulse.json").read_text(encoding="utf-8"))
    manifest["datasets"] = [{"id": dataset_id} for dataset_id in NPRA_DATASET_IDS] + [
        {"id": "non-npra-one"},
        {"id": "non-npra-two"},
    ]
    _write_json(tmp_path / "datapulse.json", manifest)
    (tmp_path / "docs/npra.html").write_text("NPRA vertical: 8 datasets.\n", encoding="utf-8")

    report = verify_distribution_sync(tmp_path)

    assert report.dataset_count == 10
    assert "docs/npra.html" in report.checked_surfaces
    assert report.failures == []


def test_full_catalogue_surface_cannot_use_npra_vertical_count(tmp_path: Path) -> None:
    _stage_current_surfaces(tmp_path, dataset_count=10)
    (tmp_path / "README.md").write_text("DataPulse has 8 datasets and 2 tools.\n", encoding="utf-8")

    report = verify_distribution_sync(tmp_path)

    assert any("README.md" in failure and "8 datasets" in failure for failure in report.failures)
