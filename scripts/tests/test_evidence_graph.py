from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.evidence_graph import build_graph, canonical_graph_bytes, load_fixture, verify_graph


FIXTURES = Path(__file__).parent / "fixtures" / "evidence_graph"


def _valid_graph() -> dict[str, object]:
    fixture = load_fixture(FIXTURES / "valid.json")
    return build_graph(fixture["nodes"], fixture["edges"])


def test_valid_fixture_has_schema_and_verifier_validation() -> None:
    graph = load_fixture(FIXTURES / "valid.json")
    assert verify_graph(graph) == []
    try:
        from jsonschema import Draft202012Validator, FormatChecker
    except ImportError:
        pytest.skip("jsonschema is optional; stdlib verifier remains covered")
    schema = json.loads((Path(__file__).parents[2] / "evidence-graph.schema.json").read_text(encoding="utf-8"))
    assert list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(graph)) == []


def test_graph_id_is_byte_stable_across_input_ordering() -> None:
    fixture = load_fixture(FIXTURES / "valid.json")
    first = build_graph(fixture["nodes"], fixture["edges"])
    second = build_graph(list(reversed(fixture["nodes"])), list(reversed(fixture["edges"])))
    assert first["graph_id"] == second["graph_id"]
    assert canonical_graph_bytes(first) == canonical_graph_bytes(second)


def test_dangling_edge_is_rejected() -> None:
    graph = load_fixture(FIXTURES / "invalid-dangling-edge.json")
    assert "edge edge_dangling has dangling endpoint" in verify_graph(graph)


def test_supported_claim_with_mismatched_digest_is_rejected() -> None:
    graph = load_fixture(FIXTURES / "invalid-supported-claim.json")
    assert "supported claim claim_bnm_opr evidence_digest must match its observation" in verify_graph(graph)


def test_supported_claim_on_unsafe_observation_is_rejected() -> None:
    graph = _valid_graph()
    observation = next(node for node in graph["nodes"] if node["type"] == "observation")
    observation["status"] = "stale"
    assert "supported claim claim_fuelprice has unsafe observation status" in verify_graph(graph)


def test_supported_claim_requires_receipt_support() -> None:
    graph = _valid_graph()
    graph["edges"] = [edge for edge in graph["edges"] if edge["id"] != "edge_supports"]
    assert "supported claim claim_fuelprice lacks receipt support" in verify_graph(graph)


def test_supersedes_requires_newer_source_observation() -> None:
    graph = _valid_graph()
    graph = copy.deepcopy(graph)
    graph["nodes"].append({"id": "observation_old", "type": "observation", "dataset_id": "fuelprice", "observed_at": "2026-09-08T00:00:00Z", "status": "fresh", "source_url": "https://data.gov.my/data-catalogue/fuelprice", "fingerprint": "old", "observation_digest": "sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"})
    graph["edges"].append({"id": "edge_wrong_order", "type": "supersedes", "from": "observation_fuelprice", "to": "observation_old"})
    assert "edge edge_wrong_order must supersede an older observation" in verify_graph(graph)


def test_reconciliation_rejects_unknown_dataset() -> None:
    graph = _valid_graph()
    reconciliation = next(node for node in graph["nodes"] if node["type"] == "reconciliation")
    reconciliation["dataset_ids"] = ["bnm_opr"]
    assert "reconciliation reconciliation_fuelprice has unresolved dataset_id: bnm_opr" in verify_graph(graph)


def test_serialized_graph_excludes_secrets_and_identity_fields() -> None:
    graph = _valid_graph()
    serialized = canonical_graph_bytes(graph).decode("utf-8")
    for forbidden in ("identity", "buyer", "session", "ip_address", "secret", "token"):
        assert forbidden not in serialized
    graph["session_id"] = "not-allowed"
    assert "forbidden key: session_id" in verify_graph(graph)


def test_build_rejects_invalid_graph() -> None:
    fixture = load_fixture(FIXTURES / "invalid-supported-claim.json")
    with pytest.raises(ValueError, match="evidence_digest must match"):
        build_graph(fixture["nodes"], fixture["edges"])
