#!/usr/bin/env python3
"""Generate deterministic dataset-level catalogue relationships.

Only literal, declared metadata values are compared. This generator performs no
normalization, fuzzy matching, record linkage, or network access.
"""

from __future__ import annotations

import argparse
import itertools
import json
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EDGE_KINDS = (
    "same_steward",
    "same_agency",
    "same_geography",
    "canonical_series",
    "successor_to",
    "shared_schema",
)
WEIGHTS = {
    "same_steward": 2,
    "same_agency": 1,
    "same_geography": 1,
    "canonical_series": 2,
    "successor_to": 3,
    "shared_schema": 1,
}


def _index(rows: Any, field: str, label: str) -> dict[str, dict[str, Any]]:
    if not isinstance(rows, list):
        raise TypeError(f"{label} must be an array")
    indexed: dict[str, dict[str, Any]] = {}
    for position, row in enumerate(rows):
        if not isinstance(row, dict):
            raise TypeError(f"{label}[{position}] must be an object")
        identifier = row.get(field)
        if not isinstance(identifier, str) or not identifier:
            raise ValueError(f"{label}[{position}] must have a non-empty {field}")
        if identifier in indexed:
            raise ValueError(f"duplicate dataset identifier: {identifier}")
        indexed[identifier] = row
    return indexed


def _declared_string(row: dict[str, Any], field: str) -> str | None:
    value = row.get(field)
    return value if isinstance(value, str) and value else None


def _provenance(fields: Iterable[str], manifest_version: str) -> dict[str, Any]:
    return {
        "matched_fields": list(fields),
        "manifest_version": manifest_version,
    }


def _edge(
    kind: str,
    source: str,
    target: str,
    fields: Iterable[str],
    manifest_version: str,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "from": source,
        "to": target,
        "weight": WEIGHTS[kind],
        "provenance": _provenance(fields, manifest_version),
    }


def _literal_group_edges(
    datasets: dict[str, dict[str, Any]],
    *,
    field: str,
    kind: str,
    manifest_version: str,
) -> list[dict[str, Any]]:
    groups: dict[str, list[str]] = defaultdict(list)
    for dataset_id, row in datasets.items():
        value = _declared_string(row, field)
        if value is not None:
            groups[value].append(dataset_id)
    return [
        _edge(kind, source, target, (field,), manifest_version)
        for dataset_ids in groups.values()
        for source, target in itertools.combinations(sorted(dataset_ids), 2)
    ]


def build_graph(manifest: dict[str, Any], health: dict[str, Any]) -> dict[str, Any]:
    """Build a deterministic graph from already-loaded manifest and health JSON."""
    if not isinstance(manifest, dict) or not isinstance(health, dict):
        raise TypeError("manifest and health must be JSON objects")
    manifest_version = manifest.get("$schema")
    if not isinstance(manifest_version, str) or not manifest_version:
        raise ValueError("manifest must declare a non-empty $schema")
    generated_at = health.get("checked_at")
    if not isinstance(generated_at, str) or not generated_at:
        raise ValueError("health must declare a non-empty checked_at")

    datasets = _index(manifest.get("datasets"), "id", "manifest.datasets")
    health_rows = _index(health.get("datasets"), "dataset_id", "health.datasets")
    if set(datasets) != set(health_rows):
        missing = sorted(set(datasets) - set(health_rows))
        extra = sorted(set(health_rows) - set(datasets))
        raise ValueError(f"manifest/health dataset IDs differ; missing={missing}, extra={extra}")

    nodes = [
        {
            "dataset_id": dataset_id,
            "title": row.get("name", dataset_id),
            "steward": row.get("steward"),
            "agency": row.get("source"),
        }
        for dataset_id, row in sorted(datasets.items())
    ]
    edges: list[dict[str, Any]] = []

    steward_groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    agency_groups: dict[str, list[str]] = defaultdict(list)
    for dataset_id, row in datasets.items():
        agency = _declared_string(row, "steward")
        publisher = _declared_string(row, "source")
        if agency is not None:
            agency_groups[agency].append(dataset_id)
        if agency is not None and publisher is not None:
            steward_groups[(publisher, agency)].append(dataset_id)

    for dataset_ids in steward_groups.values():
        for source, target in itertools.combinations(sorted(dataset_ids), 2):
            edges.append(
                _edge(
                    "same_steward",
                    source,
                    target,
                    ("source", "steward"),
                    manifest_version,
                )
            )

    for dataset_ids in agency_groups.values():
        for source, target in itertools.combinations(sorted(dataset_ids), 2):
            source_publisher = _declared_string(datasets[source], "source")
            target_publisher = _declared_string(datasets[target], "source")
            if source_publisher is not None and source_publisher == target_publisher:
                continue
            edges.append(
                _edge("same_agency", source, target, ("steward",), manifest_version)
            )

    edges.extend(
        _literal_group_edges(
            datasets,
            field="geography",
            kind="same_geography",
            manifest_version=manifest_version,
        )
    )
    edges.extend(
        _literal_group_edges(
            datasets,
            field="series_code",
            kind="canonical_series",
            manifest_version=manifest_version,
        )
    )
    edges.extend(
        _literal_group_edges(
            datasets,
            field="schema_id",
            kind="shared_schema",
            manifest_version=manifest_version,
        )
    )

    for source, row in datasets.items():
        raw_targets = row.get("supersedes", [])
        targets = [raw_targets] if isinstance(raw_targets, str) else raw_targets
        if not isinstance(targets, list) or not all(
            isinstance(target, str) and target for target in targets
        ):
            raise ValueError(f"{source}.supersedes must be a dataset ID or array of IDs")
        for target in sorted(targets):
            if target not in datasets:
                raise ValueError(f"{source}.supersedes references unknown dataset: {target}")
            if target == source:
                raise ValueError(f"{source}.supersedes cannot reference itself")
            edges.append(
                _edge("successor_to", source, target, ("supersedes",), manifest_version)
            )

    edges.sort(key=lambda edge: (edge["kind"], edge["from"], edge["to"]))
    edge_keys = [(edge["kind"], edge["from"], edge["to"]) for edge in edges]
    if len(edge_keys) != len(set(edge_keys)):
        raise ValueError("duplicate catalogue relationship edge")
    counts = Counter(edge["kind"] for edge in edges)
    connected = {edge["from"] for edge in edges} | {edge["to"] for edge in edges}

    return {
        "generated_at": generated_at,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "edge_kinds": {kind: counts[kind] for kind in EDGE_KINDS},
        "coverage": {
            "datasets_with_at_least_one_edge": len(connected),
            "isolated_datasets": sorted(set(datasets) - connected),
        },
        "precision": {
            "measured": False,
            "reason": "No reviewed truth set; all emitted edges are literal catalogue metadata matches.",
            "fuzzy_edges": 0,
        },
        "nodes": nodes,
        "edges": edges,
    }


def _read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read valid JSON object {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return value


def generate_catalog_graph(
    manifest_path: Path, health_path: Path, output_path: Path
) -> dict[str, Any]:
    graph = build_graph(_read_object(manifest_path), _read_object(health_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(graph, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return graph


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "datapulse.json")
    parser.add_argument("--health", type=Path, default=ROOT / "health/latest.json")
    parser.add_argument("--output", type=Path, default=ROOT / "catalog-graph.json")
    args = parser.parse_args()
    try:
        graph = generate_catalog_graph(args.manifest, args.health, args.output)
    except (TypeError, ValueError) as exc:
        parser.error(str(exc))
    print(
        f"catalog graph: {graph['node_count']} nodes, {graph['edge_count']} edges -> {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
