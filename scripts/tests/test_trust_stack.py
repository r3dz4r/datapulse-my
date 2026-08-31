"""Local, deterministic trust-stack contract vectors; no network or keys."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from scripts.trust_stack import (
    CONTRACT_VERSION,
    AdmissionRequest,
    TrustShiftPolicy,
    TrustStackError,
    build_governed_context,
    canonical_bytes,
    derive_readiness_profile,
    digest_payload,
    establish_baseline,
    reconstruct_context,
    validate_provenance,
    verify_clearance,
    watch_response,
)

NOW = "2026-09-01T00:00:00Z"
MANIFEST = {
    "id": "sample",
    "name": "Sample",
    "url": "https://example.test/data",
    "source": "Example Agency",
    "licence": "CC-BY-4.0",
    "refresh_frequency": "daily",
}
HEALTH = {
    "dataset_id": "sample",
    "request_url": "https://example.test/data",
    "status": "fresh",
    "first_row_hash": "shape-v1:" + "a" * 64,
}
FIXTURES = Path(__file__).parent / "fixtures/trust_stack"
ROOT = Path(__file__).resolve().parents[2]


def test_all_five_local_companion_fixtures_validate_against_their_schemas() -> None:
    for fixture in sorted((FIXTURES / "valid").glob("*.json")):
        schema = json.loads((FIXTURES / "schemas" / fixture.name).read_text())
        instance = json.loads(fixture.read_text())
        assert (
            list(
                Draft202012Validator(
                    schema, format_checker=FormatChecker()
                ).iter_errors(instance)
            )
            == []
        )


def test_existing_public_mcp_contract_is_unchanged() -> None:
    advertisement = json.loads((ROOT / "mcp.json").read_text())
    assert advertisement["endpoint"]["auth_required"] is False
    # The generated catalogue currently exposes 18 tools; this local slice must
    # preserve that observed public contract rather than regenerate it.
    assert len(advertisement["tools"]) == 18
    assert all(
        set(tool["annotations"])
        == {"readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint"}
        for tool in advertisement["tools"]
    )


def _clearance() -> dict[str, object]:
    allowed = {
        "tool_name": "tool_a",
        "input_schema_digest": "sha256:" + "a" * 64,
        "annotation_digest": "sha256:" + "b" * 64,
        "effect_class": "read_only",
    }
    payload = {
        "clearance_id": "urn:datapulse:trust-stack:tool-clearance:" + "c" * 64,
        "issuer_id": "fixture-issuer",
        "trust_root_id": "fixture-root",
        "server_identity": {
            "endpoint": "https://example.test/mcp",
            "name": "DataPulse MY",
            "version": "1",
            "advertisement_digest": "sha256:" + "d" * 64,
        },
        "issued_at": "2026-08-01T00:00:00Z",
        "not_before": "2026-08-01T00:00:00Z",
        "expires_at": "2026-10-01T00:00:00Z",
        "sequence": 2,
        "allowed_tools": [allowed],
        "policy_id": "fixture/v1",
        "clearance_subject_digest": "sha256:" + "e" * 64,
        "supersedes": None,
    }
    return {
        "contract_version": CONTRACT_VERSION,
        "object_type": "tool_clearance",
        "object_id": payload["clearance_id"],
        "subject_id": "DataPulse MY",
        "created_at": NOW,
        "producer": {"id": "fixture", "version": "1"},
        "payload": payload,
        "payload_digest": digest_payload(payload),
    }


def _request(tool_name: str = "tool_a") -> AdmissionRequest:
    return AdmissionRequest(
        "https://example.test/mcp",
        "DataPulse MY",
        "1",
        "sha256:" + "d" * 64,
        tool_name,
        "sha256:" + "a" * 64,
        "sha256:" + "b" * 64,
        "read_only",
    )


def test_readiness_is_deterministic_and_unknown_is_weighted_out() -> None:
    profile = derive_readiness_profile(MANIFEST, HEALTH, evidence=[], assessed_at=NOW)
    assert profile["payload"]["overall"] == "ready"
    missing = derive_readiness_profile(
        {"id": "sample"}, HEALTH, evidence=[], assessed_at=NOW
    )
    dimensions = missing["payload"]["dimensions"]
    assert dimensions["licensing"]["state"] == "unknown"
    assert dimensions["licensing"]["coverage"] == {"evaluated": 0, "applicable": 1}
    assert missing["payload"]["overall"] == "indeterminate"
    assert canonical_bytes(profile) == canonical_bytes(
        derive_readiness_profile(MANIFEST, HEALTH, evidence=[], assessed_at=NOW)
    )


def test_context_reconstructs_point_in_time_and_rejects_stale_or_broken_chain() -> None:
    node = {
        "source_node_id": "source-a",
        "publisher": "Example",
        "content_digest": "sha256:" + "1" * 64,
        "observed_at": "2026-08-01T00:00:00Z",
        "valid_at": "2026-08-01T00:00:00Z",
        "schema_version": "v1",
        "provenance_ref": {"object_id": "p", "payload_digest": "sha256:" + "2" * 64},
        "selection_decision": "selected",
        "eligibility": {
            "approved": True,
            "current": True,
            "attributable": True,
            "integrity_verified": True,
        },
    }
    context = build_governed_context(
        "sample",
        [node],
        valid_at="2026-08-15T00:00:00Z",
        assembled_at=NOW,
        previous_context_digest=None,
    )
    reconstructed = reconstruct_context(
        [context],
        valid_at="2026-08-15T00:00:00Z",
        now=NOW,
        max_age_days=31,
        required=True,
    )
    assert reconstructed["selected_source_node_ids"] == ["source-a"]
    stale = reconstruct_context(
        [context],
        valid_at="2026-09-01T00:00:00Z",
        now=NOW,
        max_age_days=1,
        required=False,
    )
    assert (
        stale["reason_codes"] == ["stale_context"]
        and stale["selected_source_node_ids"] == []
    )
    broken = copy.deepcopy(context)
    broken["payload"]["previous_context_digest"] = "sha256:" + "f" * 64
    broken["payload"]["checkpoint"]["previous_digest"] = "sha256:" + "f" * 64
    broken["payload_digest"] = digest_payload(broken["payload"])
    with pytest.raises(TrustStackError, match="checkpoint_predecessor_missing"):
        reconstruct_context(
            [broken],
            valid_at="2026-08-15T00:00:00Z",
            now=NOW,
            max_age_days=31,
            required=True,
        )


def test_provenance_rejects_parentless_unattributed_cycles_and_human_upgrade() -> None:
    valid = {
        "entities": [{"id": "e", "digest": "sha256:" + "1" * 64}],
        "activities": [{"id": "a", "agent_id": "software"}],
        "agents": [{"id": "software", "kind": "software"}],
        "claims": [{"id": "c", "activity_id": "a", "parent_ids": ["e"]}],
        "artifacts": [{"id": "r", "digest": "sha256:" + "2" * 64}],
        "edges": [{"from": "e", "to": "c", "relation": "supports"}],
        "verification_assertions": [
            {"claim_id": "c", "rung": "automated_check", "activity_id": "a"}
        ],
        "conflicts": [],
    }
    assert validate_provenance(valid) == []
    bad_parent = copy.deepcopy(valid)
    bad_parent["claims"][0]["parent_ids"] = []
    assert validate_provenance(bad_parent) == ["parentless_claim"]
    bad_agent = copy.deepcopy(valid)
    bad_agent["activities"][0].pop("agent_id")
    assert validate_provenance(bad_agent) == ["unattributed_activity"]
    bad_human = copy.deepcopy(valid)
    bad_human["verification_assertions"][0]["rung"] = "human_verified"
    assert validate_provenance(bad_human) == ["human_rung_requires_human_activity"]


def test_clearance_denies_missing_root_expiry_replay_wildcard_and_contract_changes() -> (
    None
):
    clearance = _clearance()
    assert (
        verify_clearance(
            clearance, _request(), now=NOW, roots={}, signature_verifier=lambda *_: True
        ).reason_code
        == "trust_root_unavailable"
    )
    roots = {"fixture-root": {"fixture_only": True}}
    assert verify_clearance(
        clearance, _request(), now=NOW, roots=roots, signature_verifier=lambda *_: True
    ).allowed
    mismatch = copy.deepcopy(clearance)
    mismatch["contract_version"] = "trust-stack/v2.0.0"
    assert (
        verify_clearance(
            mismatch,
            _request(),
            now=NOW,
            roots=roots,
            signature_verifier=lambda *_: True,
        ).reason_code
        == "clearance_invalid"
    )
    assert (
        verify_clearance(
            clearance,
            _request("tool_b"),
            now=NOW,
            roots=roots,
            signature_verifier=lambda *_: True,
        ).reason_code
        == "tool_not_allowlisted"
    )
    changed = _request()
    assert (
        verify_clearance(
            clearance,
            AdmissionRequest(
                changed.endpoint,
                changed.server_name,
                changed.server_version,
                changed.advertisement_digest,
                changed.tool_name,
                "sha256:" + "9" * 64,
                changed.annotation_digest,
                changed.effect_class,
            ),
            now=NOW,
            roots=roots,
            signature_verifier=lambda *_: True,
        ).reason_code
        == "tool_contract_mismatch"
    )
    expired = copy.deepcopy(clearance)
    expired["payload"]["expires_at"] = "2026-08-31T00:00:00Z"
    expired["payload_digest"] = digest_payload(expired["payload"])
    assert (
        verify_clearance(
            expired,
            _request(),
            now=NOW,
            roots=roots,
            signature_verifier=lambda *_: True,
        ).reason_code
        == "clearance_expired"
    )
    assert (
        verify_clearance(
            clearance,
            _request(),
            now=NOW,
            roots=roots,
            signature_verifier=lambda *_: True,
            accepted_sequence=3,
        ).reason_code
        == "clearance_superseded"
    )
    wildcard = copy.deepcopy(clearance)
    wildcard["payload"]["allowed_tools"][0]["tool_name"] = "*"
    wildcard["payload_digest"] = digest_payload(wildcard["payload"])
    assert (
        verify_clearance(
            wildcard,
            _request(),
            now=NOW,
            roots=roots,
            signature_verifier=lambda *_: True,
        ).reason_code
        == "clearance_invalid"
    )


def test_trustshift_detects_staged_defection_but_ignores_key_order_and_tolerated_timing() -> (
    None
):
    policy = TrustShiftPolicy(
        "fixture/v1",
        expected_samples=2,
        semantic_paths={"result.status": "ok"},
        scope_path="result.records",
        timing_classes={"fast", "normal"},
    )
    baseline = establish_baseline(
        "server",
        "tool_a",
        "sha256:" + "a" * 64,
        "clearance",
        policy,
        [
            {"result": {"status": "ok", "records": [{"id": "one"}]}},
            {"result": {"records": [{"id": "one"}], "status": "ok"}},
        ],
        ["fast", "normal"],
    )
    benign = watch_response(
        baseline,
        {"result": {"records": [{"id": "one"}], "status": "ok"}},
        timing_class="fast",
    )
    assert benign["decision"] == "allow"
    structural = watch_response(
        baseline,
        {"result": {"status": "ok", "records": [{"id": "one"}], "extra": True}},
        timing_class="fast",
    )
    assert (
        structural["decision"] == "quarantine"
        and "structural_mutation" in structural["signal_kinds"]
    )
    semantic = watch_response(
        baseline,
        {"result": {"status": "reversed", "records": [{"id": "one"}]}},
        timing_class="fast",
    )
    assert "semantic_invariant_violation" in semantic["signal_kinds"]
    scope = watch_response(
        baseline,
        {"result": {"status": "ok", "records": [{"id": "one"}, {"id": "two"}]}},
        timing_class="fast",
    )
    assert "scope_expansion" in scope["signal_kinds"]
