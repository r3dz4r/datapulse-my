#!/usr/bin/env python3
"""Pure, deterministic evidence-graph/v1 builder and verifier."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

Graph = dict[str, object]
Node = dict[str, object]
Edge = dict[str, object]

ID_RE = re.compile(r"^[a-z][a-z0-9_-]{1,127}$")
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
STATUSES = frozenset(("fresh", "aging", "stale", "discontinued", "degraded", "browser_dependent", "unreachable", "unknown", "unknown_freshness", "reference"))
UNSAFE_SUPPORTED_STATUSES = frozenset(("stale", "discontinued", "degraded", "browser_dependent", "unreachable", "unknown"))
NODE_FIELDS = {
    "dataset": frozenset(("id", "type", "dataset_id", "name", "source_url")),
    "observation": frozenset(("id", "type", "dataset_id", "observed_at", "status", "source_url", "fingerprint", "observation_digest")),
    "receipt": frozenset(("id", "type", "observation_id", "receipt_digest", "receipt_kind", "verification")),
    "claim": frozenset(("id", "type", "observation_id", "claim_type", "text", "support", "evidence_digest")),
    "reconciliation": frozenset(("id", "type", "dataset_ids", "verdict", "basis")),
}
EDGE_TYPES = frozenset(("observes", "derived_from", "attested_by", "supports", "supersedes", "conflicts_with"))
FORBIDDEN_KEY_PARTS = ("identity", "buyer", "session", "cookie", "token", "password", "secret", "api_key", "ip_address")


def _timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _sort_items(items: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    return sorted((copy.deepcopy(item) for item in items), key=lambda item: str(item.get("id", "")))


def canonical_graph_bytes(graph: Graph) -> bytes:
    """Return canonical graph bytes excluding its self-referential graph ID."""
    content = {key: value for key, value in graph.items() if key != "graph_id"}
    if isinstance(content.get("nodes"), list):
        content["nodes"] = _sort_items(content["nodes"])
    if isinstance(content.get("edges"), list):
        content["edges"] = _sort_items(content["edges"])
    return json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def build_graph(nodes: Iterable[Node], edges: Iterable[Edge]) -> Graph:
    """Normalize graph content, derive a deterministic timestamp and graph ID, and verify it."""
    sorted_nodes = _sort_items(nodes)
    sorted_edges = _sort_items(edges)
    observation_times = [node.get("observed_at") for node in sorted_nodes if node.get("type") == "observation"]
    timestamps = [value for value in observation_times if _timestamp(value) is not None]
    generated_at = max(timestamps) if timestamps else "1970-01-01T00:00:00Z"
    graph: Graph = {"schema": "evidence-graph/v1", "generated_at": generated_at, "nodes": sorted_nodes, "edges": sorted_edges}
    graph["graph_id"] = "sha256:" + hashlib.sha256(canonical_graph_bytes(graph)).hexdigest()
    errors = verify_graph(graph)
    if errors:
        raise ValueError("invalid evidence graph: " + "; ".join(errors))
    return graph


def verify_graph(graph: Graph) -> list[str]:
    """Return deterministic validation errors; an empty list means the graph is valid."""
    errors: list[str] = []
    if not isinstance(graph, dict):
        return ["graph must be an object"]
    for key in graph:
        if any(part in key.lower() for part in FORBIDDEN_KEY_PARTS):
            errors.append(f"forbidden key: {key}")
    if graph.get("schema") != "evidence-graph/v1": errors.append("schema must be evidence-graph/v1")
    if not DIGEST_RE.fullmatch(str(graph.get("graph_id", ""))): errors.append("graph_id must be a sha256 digest")
    if _timestamp(graph.get("generated_at")) is None: errors.append("generated_at must be an ISO-8601 timestamp with timezone")
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    if not isinstance(nodes, list): return sorted(errors + ["nodes must be an array"])
    if not isinstance(edges, list): return sorted(errors + ["edges must be an array"])
    node_by_id: dict[str, Node] = {}
    dataset_nodes: dict[str, Node] = {}
    for index, node in enumerate(nodes):
        prefix = f"node[{index}]"
        if not isinstance(node, dict): errors.append(f"{prefix} must be an object"); continue
        kind = node.get("type")
        if kind not in NODE_FIELDS: errors.append(f"{prefix} has invalid type"); continue
        if set(node) != NODE_FIELDS[kind]: errors.append(f"{prefix} fields must exactly match {kind}")
        node_id = node.get("id")
        if not isinstance(node_id, str) or not ID_RE.fullmatch(node_id): errors.append(f"{prefix} has invalid id"); continue
        if node_id in node_by_id: errors.append(f"duplicate node id: {node_id}")
        node_by_id[node_id] = node
        if kind == "dataset":
            dataset_id = node.get("dataset_id")
            if not isinstance(dataset_id, str) or not ID_RE.fullmatch(dataset_id): errors.append(f"dataset {node_id} has invalid dataset_id")
            elif dataset_id in dataset_nodes: errors.append(f"duplicate dataset_id: {dataset_id}")
            else: dataset_nodes[dataset_id] = node
        if kind == "observation":
            if node.get("status") not in STATUSES: errors.append(f"observation {node_id} has invalid status")
            if _timestamp(node.get("observed_at")) is None: errors.append(f"observation {node_id} has invalid observed_at")
            if not DIGEST_RE.fullmatch(str(node.get("observation_digest", ""))): errors.append(f"observation {node_id} has invalid observation_digest")
    for node_id, node in sorted(node_by_id.items()):
        kind = node.get("type")
        if kind == "observation":
            dataset_id = node.get("dataset_id")
            if dataset_id not in dataset_nodes: errors.append(f"observation {node_id} has unresolved dataset_id: {dataset_id}")
        elif kind in ("receipt", "claim"):
            observation_id = node.get("observation_id")
            if observation_id not in node_by_id or node_by_id.get(observation_id, {}).get("type") != "observation": errors.append(f"{kind} {node_id} has unresolved observation_id: {observation_id}")
            digest_key = "receipt_digest" if kind == "receipt" else "evidence_digest"
            if not DIGEST_RE.fullmatch(str(node.get(digest_key, ""))): errors.append(f"{kind} {node_id} has invalid {digest_key}")
        elif kind == "reconciliation":
            dataset_ids = node.get("dataset_ids")
            if not isinstance(dataset_ids, list) or not dataset_ids: errors.append(f"reconciliation {node_id} requires dataset_ids")
            else:
                for dataset_id in dataset_ids:
                    if dataset_id not in dataset_nodes: errors.append(f"reconciliation {node_id} has unresolved dataset_id: {dataset_id}")
    edge_keys: set[tuple[str, str, str]] = set()
    edge_ids: set[str] = set()
    receipt_supports: set[str] = set()
    observed_by: dict[str, list[str]] = {}
    for index, edge in enumerate(edges):
        prefix = f"edge[{index}]"
        if not isinstance(edge, dict): errors.append(f"{prefix} must be an object"); continue
        if set(edge) != {"id", "type", "from", "to"}: errors.append(f"{prefix} fields must exactly match edge"); continue
        edge_id, edge_type, source, target = edge.get("id"), edge.get("type"), edge.get("from"), edge.get("to")
        if not isinstance(edge_id, str) or not ID_RE.fullmatch(edge_id): errors.append(f"{prefix} has invalid id")
        elif edge_id in edge_ids: errors.append(f"duplicate edge id: {edge_id}")
        edge_ids.add(str(edge_id))
        if edge_type not in EDGE_TYPES: errors.append(f"{prefix} has invalid type"); continue
        if source not in node_by_id or target not in node_by_id: errors.append(f"edge {edge_id} has dangling endpoint"); continue
        if source == target: errors.append(f"edge {edge_id} is a self-edge"); continue
        key = (str(edge_type), str(source), str(target))
        if key in edge_keys: errors.append(f"duplicate edge: {edge_type} {source}->{target}")
        edge_keys.add(key)
        source_kind, target_kind = node_by_id[source].get("type"), node_by_id[target].get("type")
        allowed = {"observes": (("dataset", "observation"),), "derived_from": (("observation", "receipt"), ("claim", "observation")), "attested_by": (("observation", "receipt"),), "supports": (("observation", "claim"), ("receipt", "claim")), "supersedes": (("observation", "observation"),), "conflicts_with": (("observation", "observation"), ("observation", "reconciliation"), ("reconciliation", "observation"), ("reconciliation", "reconciliation"))}
        if (source_kind, target_kind) not in allowed[edge_type]: errors.append(f"edge {edge_id} has invalid {edge_type} endpoints")
        if edge_type == "supports" and source_kind == "receipt" and target_kind == "claim": receipt_supports.add(str(target))
        if edge_type == "observes" and source_kind == "dataset" and target_kind == "observation": observed_by.setdefault(str(target), []).append(str(source))
        if edge_type == "supersedes" and source_kind == target_kind == "observation":
            if _timestamp(node_by_id[source].get("observed_at")) is None or _timestamp(node_by_id[target].get("observed_at")) is None or _timestamp(node_by_id[source].get("observed_at")) <= _timestamp(node_by_id[target].get("observed_at")): errors.append(f"edge {edge_id} must supersede an older observation")
    for node_id, node in sorted(node_by_id.items()):
        if node.get("type") == "observation":
            sources = observed_by.get(node_id, [])
            if len(sources) != 1:
                errors.append(f"observation {node_id} must have exactly one observes edge")
            elif node_by_id[sources[0]].get("dataset_id") != node.get("dataset_id"):
                errors.append(f"observation {node_id} observes edge dataset_id does not match")
        if node.get("type") != "claim" or node.get("support") != "supported": continue
        observation = node_by_id.get(str(node.get("observation_id")), {})
        if node.get("evidence_digest") != observation.get("observation_digest"): errors.append(f"supported claim {node_id} evidence_digest must match its observation")
        if observation.get("status") in UNSAFE_SUPPORTED_STATUSES: errors.append(f"supported claim {node_id} has unsafe observation status")
        if node_id not in receipt_supports: errors.append(f"supported claim {node_id} lacks receipt support")
    expected = "sha256:" + hashlib.sha256(canonical_graph_bytes(graph)).hexdigest()
    if graph.get("graph_id") != expected: errors.append("graph_id does not match canonical graph content")
    return sorted(errors)


def load_fixture(path: str | Path) -> Graph:
    """Load a JSON fixture for tests; this helper performs no runtime graph I/O."""
    with Path(path).open(encoding="utf-8") as handle:
        value: Any = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("fixture graph must be an object")
    return value
