"""Tests for the deterministic catalogue relationship graph."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.gen_catalog_graph import build_graph, generate_catalog_graph

ROOT = Path(__file__).resolve().parents[2]


def _manifest(*datasets: dict[str, object]) -> dict[str, object]:
    return {
        "$schema": "https://example.invalid/datapulse.schema.json",
        "datasets": list(datasets),
    }


def _dataset(dataset_id: str, **metadata: object) -> dict[str, object]:
    return {"id": dataset_id, "name": dataset_id.title(), **metadata}


def _health(*dataset_ids: str) -> dict[str, object]:
    return {
        "checked_at": "2026-08-12T12:00:00Z",
        "datasets": [{"dataset_id": dataset_id} for dataset_id in dataset_ids],
    }


def test_graph_includes_same_steward_edge() -> None:
    graph = build_graph(
        _manifest(
            _dataset("alpha", steward="Agency A", source="Publisher Unit"),
            _dataset("beta", steward="Agency A", source="Publisher Unit"),
        ),
        _health("alpha", "beta"),
    )

    assert graph["edges"] == [
        {
            "kind": "same_steward",
            "from": "alpha",
            "to": "beta",
            "weight": 2,
            "provenance": {
                "matched_fields": ["source", "steward"],
                "manifest_version": "https://example.invalid/datapulse.schema.json",
            },
        }
    ]


def test_graph_omits_edge_when_field_missing() -> None:
    graph = build_graph(
        _manifest(
            _dataset("alpha", steward="Agency A"),
            _dataset("beta", steward="Agency A", source="Publisher Unit"),
        ),
        _health("alpha", "beta"),
    )

    assert [(edge["kind"], edge["weight"]) for edge in graph["edges"]] == [
        ("same_agency", 1)
    ]


def test_graph_idempotent(tmp_path: Path) -> None:
    manifest_path = tmp_path / "datapulse.json"
    health_path = tmp_path / "health.json"
    output_path = tmp_path / "catalog-graph.json"
    manifest_path.write_text(
        json.dumps(
            _manifest(
                _dataset("beta", series_code="example"),
                _dataset("alpha", series_code="example"),
            )
        ),
        encoding="utf-8",
    )
    health_path.write_text(json.dumps(_health("alpha", "beta")), encoding="utf-8")

    generate_catalog_graph(manifest_path, health_path, output_path)
    first = output_path.read_bytes()
    generate_catalog_graph(manifest_path, health_path, output_path)

    assert output_path.read_bytes() == first


def test_graph_coverage_metric() -> None:
    graph = build_graph(
        json.loads((ROOT / "datapulse.json").read_text(encoding="utf-8")),
        json.loads((ROOT / "health/latest.json").read_text(encoding="utf-8")),
    )

    assert graph["coverage"]["datasets_with_at_least_one_edge"] >= 2
    assert any(
        edge["kind"] == "canonical_series"
        and {edge["from"], edge["to"]}
        == {"dosm_cpi_core_inflation", "cpi_core_inflation"}
        for edge in graph["edges"]
    )


def test_graph_sorted_order() -> None:
    graph = build_graph(
        _manifest(
            _dataset("zeta", steward="Agency A", source="Unit A", schema_id="s1"),
            _dataset("alpha", steward="Agency A", source="Unit B", schema_id="s1"),
            _dataset("middle", steward="Agency A", source="Unit B"),
        ),
        _health("middle", "zeta", "alpha"),
    )

    assert [node["dataset_id"] for node in graph["nodes"]] == [
        "alpha",
        "middle",
        "zeta",
    ]
    assert [
        (edge["kind"], edge["from"], edge["to"]) for edge in graph["edges"]
    ] == sorted(
        (edge["kind"], edge["from"], edge["to"]) for edge in graph["edges"]
    )


def test_successor_edge_is_directional() -> None:
    graph = build_graph(
        _manifest(
            _dataset("old"),
            _dataset("new", supersedes="old"),
        ),
        _health("old", "new"),
    )

    assert [(edge["kind"], edge["from"], edge["to"], edge["weight"]) for edge in graph["edges"]] == [
        ("successor_to", "new", "old", 3)
    ]
