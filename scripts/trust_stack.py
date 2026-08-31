"""Local trust-stack/v1 companion contracts.

These helpers intentionally have no network, key-store, or public-server path.
They prepare deterministic fixtures for a separately configured private consumer.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

CONTRACT_VERSION = "trust-stack/v1.0.0"
_DIMENSIONS = (
    "fair",
    "licensing",
    "provenance",
    "governance",
    "reproducibility",
    "catalogue_readiness",
)
_OBJECT_TYPES = {
    "readiness_profile",
    "governed_context",
    "ai_provenance",
    "tool_clearance",
    "trustshift_observation",
}
_MAX_CLEARANCE_BYTES = 64 * 1024


class TrustStackError(ValueError):
    """Raised when a local companion contract cannot be safely interpreted."""


def canonical_bytes(value: object) -> bytes:
    """Serialize fixture-compatible JSON deterministically without transport wrappers."""
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def digest_payload(payload: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(payload)).hexdigest()


def _parse_time(value: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise TrustStackError("invalid_timestamp")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TrustStackError("invalid_timestamp") from exc


def _object(
    object_type: str, subject_id: str, payload: dict[str, Any], created_at: str
) -> dict[str, Any]:
    if object_type not in _OBJECT_TYPES:
        raise TrustStackError("unsupported_object_type")
    digest = digest_payload(payload)
    immutable = {
        "object_type": object_type,
        "subject_id": subject_id,
        "payload_digest": digest,
    }
    object_id = (
        "urn:datapulse:trust-stack:"
        + object_type
        + ":"
        + hashlib.sha256(canonical_bytes(immutable)).hexdigest()
    )
    return {
        "contract_version": CONTRACT_VERSION,
        "object_type": object_type,
        "object_id": object_id,
        "subject_id": subject_id,
        "created_at": created_at,
        "producer": {"id": "datapulse-local", "version": "1"},
        "payload": payload,
        "payload_digest": digest,
    }


def _check(
    state: str, reason: str, evidence_refs: list[dict[str, str]]
) -> dict[str, Any]:
    return {"state": state, "reason_codes": [reason], "evidence_refs": evidence_refs}


def _dimension(
    name: str, present: bool, evidence_refs: list[dict[str, str]]
) -> dict[str, Any]:
    state = "pass" if present else "unknown"
    check = _check(
        state, "signal_present" if present else "signal_missing", evidence_refs
    )
    return {
        "state": state,
        "checks": [{"check_id": name + ".v1", **check}],
        "coverage": {"evaluated": int(present), "applicable": 1},
        "reason_codes": check["reason_codes"],
        "policy_basis": "datapulse-local-readiness/v1",
    }


def derive_readiness_profile(
    manifest: Mapping[str, Any],
    health: Mapping[str, Any],
    evidence: Sequence[Mapping[str, Any]],
    *,
    assessed_at: str,
) -> dict[str, Any]:
    """Derive only metadata sufficiency; unknown signals are never scored neutral."""
    _parse_time(assessed_at)
    subject = manifest.get("id") or health.get("dataset_id")
    if not isinstance(subject, str) or not subject:
        raise TrustStackError("missing_subject_id")
    refs = [
        {
            "object_id": str(item.get("object_id", "local-evidence")),
            "payload_digest": str(item.get("payload_digest", digest_payload(item))),
        }
        for item in evidence
    ]
    signals = {
        "fair": bool(manifest.get("url") and manifest.get("name")),
        "licensing": bool(manifest.get("licence") or manifest.get("license")),
        "provenance": bool(manifest.get("source") and health.get("request_url")),
        "governance": bool(manifest.get("source")),
        "reproducibility": bool(
            health.get("request_url") and health.get("first_row_hash")
        ),
        "catalogue_readiness": bool(
            manifest.get("id")
            and manifest.get("name")
            and manifest.get("url")
            and manifest.get("refresh_frequency")
        ),
    }
    dimensions = {name: _dimension(name, signals[name], refs) for name in _DIMENSIONS}
    states = [dimension["state"] for dimension in dimensions.values()]
    overall = (
        "not_ready"
        if "fail" in states
        else "ready"
        if all(state == "pass" for state in states)
        else "indeterminate"
    )
    payload = {
        "profile_id": "readiness:" + subject,
        "subject": subject,
        "assessed_at": assessed_at,
        "policy_id": "datapulse-local-readiness/v1",
        "dimensions": dimensions,
        "overall": overall,
        "evidence_refs": refs,
        "limitations": ["unknown signals are excluded from coverage and prevent ready"]
        if "unknown" in states
        else [],
    }
    return _object("readiness_profile", subject, payload, assessed_at)


def build_governed_context(
    subject_id: str,
    source_nodes: Sequence[Mapping[str, Any]],
    *,
    valid_at: str,
    assembled_at: str,
    previous_context_digest: str | None,
) -> dict[str, Any]:
    """Build a bounded, content-addressed context from already observed nodes."""
    _parse_time(valid_at)
    _parse_time(assembled_at)
    nodes = [
        dict(item)
        for item in sorted(
            source_nodes, key=lambda item: str(item.get("source_node_id", ""))
        )
    ]
    if any(not item.get("source_node_id") for item in nodes):
        raise TrustStackError("missing_source_node_id")
    node_digest = digest_payload(nodes)
    payload = {
        "context_version_id": "context:"
        + subject_id
        + ":"
        + node_digest.split(":", 1)[1],
        "context_digest": node_digest,
        "purpose": "local-fixture",
        "selection_policy_id": "datapulse-context/v1",
        "valid_at": valid_at,
        "assembled_at": assembled_at,
        "source_nodes": nodes,
        "previous_context_digest": previous_context_digest,
        "checkpoint": {
            "position": 0 if previous_context_digest is None else 1,
            "previous_digest": previous_context_digest,
            "current_digest": node_digest,
            "policy": "datapulse-context/v1",
        },
        "eligibility": {},
        "consumption_trace": [],
        "limitations": [],
        "conflicts": [],
    }
    return _object("governed_context", subject_id, payload, assembled_at)


def reconstruct_context(
    contexts: Sequence[Mapping[str, Any]],
    *,
    valid_at: str,
    now: str,
    max_age_days: int,
    required: bool,
) -> dict[str, Any]:
    """Recompute eligibility at a point in time; later corrections are not backfilled."""
    point = _parse_time(valid_at)
    clock = _parse_time(now)
    if max_age_days < 0:
        raise TrustStackError("invalid_max_age")
    ordered = sorted(
        contexts, key=lambda item: str(item.get("payload", {}).get("assembled_at", ""))
    )
    prior: str | None = None
    selected: list[str] = []
    reasons: list[str] = []
    for context in ordered:
        payload = context.get("payload", {})
        if (
            context.get("contract_version") != CONTRACT_VERSION
            or context.get("object_type") != "governed_context"
            or digest_payload(payload) != context.get("payload_digest")
        ):
            raise TrustStackError("context_integrity_invalid")
        checkpoint = payload.get("checkpoint", {})
        previous = payload.get("previous_context_digest")
        if payload.get("context_digest") != digest_payload(
            payload.get("source_nodes", [])
        ) or checkpoint.get("current_digest") != payload.get("context_digest"):
            raise TrustStackError("context_integrity_invalid")
        if checkpoint.get("previous_digest") != previous or (
            previous is not None and previous != prior
        ):
            raise TrustStackError("checkpoint_predecessor_missing")
        prior = payload.get("context_digest")
        if _parse_time(str(payload.get("valid_at"))) > point:
            continue
        for node in payload.get("source_nodes", []):
            observed = _parse_time(str(node.get("observed_at")))
            eligibility = node.get("eligibility", {})
            age_days = (clock - observed).total_seconds() / 86400
            eligible = (
                all(
                    eligibility.get(key) is True
                    for key in (
                        "approved",
                        "current",
                        "attributable",
                        "integrity_verified",
                    )
                )
                and observed <= point
                and age_days <= max_age_days
            )
            if eligible:
                selected.append(str(node["source_node_id"]))
            elif age_days > max_age_days:
                reasons.append("stale_context")
    if required and not selected:
        raise TrustStackError(reasons[0] if reasons else "required_context_unavailable")
    return {
        "selected_source_node_ids": sorted(selected),
        "reason_codes": sorted(set(reasons)),
        "context_digest": prior,
    }


def validate_provenance(payload: Mapping[str, Any]) -> list[str]:
    """Validate F(AI)²R ancestry and prohibit automatic human-rung elevation."""
    entities = {str(item.get("id")) for item in payload.get("entities", [])}
    claims = {str(item.get("id")) for item in payload.get("claims", [])}
    activities = {str(item.get("id")): item for item in payload.get("activities", [])}
    agents = {str(item.get("id")): item for item in payload.get("agents", [])}
    errors: list[str] = []
    for claim in payload.get("claims", []):
        parents = claim.get("parent_ids", [])
        if not parents or not all(
            str(parent) in entities | claims for parent in parents
        ):
            errors.append("parentless_claim")
        activity = activities.get(str(claim.get("activity_id")))
        if activity is None or str(activity.get("agent_id")) not in agents:
            errors.append("unattributed_activity")
    for assertion in payload.get("verification_assertions", []):
        rung = assertion.get("rung")
        activity = activities.get(str(assertion.get("activity_id")))
        agent = agents.get(str(activity.get("agent_id"))) if activity else None
        if rung in {"human_reviewed", "human_verified"} and (
            not agent
            or agent.get("kind") != "human"
            or activity.get("kind") != "review"
        ):
            errors.append("human_rung_requires_human_activity")
    edges = [
        (str(edge.get("from")), str(edge.get("to")))
        for edge in payload.get("edges", [])
    ]
    node_ids = (
        entities
        | claims
        | set(activities)
        | set(agents)
        | {str(item.get("id")) for item in payload.get("artifacts", [])}
    )
    if any(left not in node_ids or right not in node_ids for left, right in edges):
        errors.append("provenance_edge_endpoint_missing")
    graph: dict[str, list[str]] = {}
    for left, right in edges:
        graph.setdefault(left, []).append(right)
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        cycle = any(visit(child) for child in graph.get(node, []))
        visiting.remove(node)
        visited.add(node)
        return cycle

    if any(visit(node) for node in graph):
        errors.append("provenance_cycle")
    return sorted(set(errors))


@dataclass(frozen=True)
class AdmissionRequest:
    endpoint: str
    server_name: str
    server_version: str
    advertisement_digest: str
    tool_name: str
    input_schema_digest: str
    annotation_digest: str
    effect_class: str


@dataclass(frozen=True)
class AdmissionDecision:
    allowed: bool
    reason_code: str


def verify_clearance(
    envelope: Mapping[str, Any],
    request: AdmissionRequest,
    *,
    now: str,
    roots: Mapping[str, Any],
    signature_verifier: Callable[[Mapping[str, Any], Any], bool] | None,
    accepted_sequence: int | None = None,
) -> AdmissionDecision:
    """Offline, fail-closed verifier. A caller supplies the approved verifier/root config."""
    if len(canonical_bytes(envelope)) > _MAX_CLEARANCE_BYTES:
        return AdmissionDecision(False, "clearance_oversized")
    payload = envelope.get("payload")
    if (
        envelope.get("contract_version") != CONTRACT_VERSION
        or envelope.get("object_type") != "tool_clearance"
        or not isinstance(payload, Mapping)
        or digest_payload(payload) != envelope.get("payload_digest")
    ):
        return AdmissionDecision(False, "clearance_invalid")
    root_id = payload.get("trust_root_id")
    if not isinstance(root_id, str) or root_id not in roots:
        return AdmissionDecision(False, "trust_root_unavailable")
    if signature_verifier is None or not signature_verifier(envelope, roots[root_id]):
        return AdmissionDecision(False, "clearance_signature_invalid")
    try:
        current = _parse_time(now)
        not_before = _parse_time(str(payload["not_before"]))
        expires = _parse_time(str(payload["expires_at"]))
    except (KeyError, TrustStackError):
        return AdmissionDecision(False, "trusted_time_unavailable")
    if current < not_before:
        return AdmissionDecision(False, "clearance_not_yet_valid")
    if current > expires:
        return AdmissionDecision(False, "clearance_expired")
    if accepted_sequence is not None and (
        not isinstance(payload.get("sequence"), int)
        or payload["sequence"] < accepted_sequence
    ):
        return AdmissionDecision(False, "clearance_superseded")
    identity = payload.get("server_identity", {})
    if not isinstance(identity, Mapping) or (
        identity.get("endpoint"),
        identity.get("name"),
        identity.get("version"),
        identity.get("advertisement_digest"),
    ) != (
        request.endpoint,
        request.server_name,
        request.server_version,
        request.advertisement_digest,
    ):
        return AdmissionDecision(False, "server_identity_mismatch")
    tools = payload.get("allowed_tools")
    if not isinstance(tools, list) or not tools:
        return AdmissionDecision(False, "clearance_invalid")
    if any(
        not isinstance(item, Mapping)
        or any(
            item.get(field) == "*"
            for field in (
                "tool_name",
                "input_schema_digest",
                "annotation_digest",
                "effect_class",
            )
        )
        for item in tools
    ):
        return AdmissionDecision(False, "clearance_invalid")
    matches = [item for item in tools if item.get("tool_name") == request.tool_name]
    if not matches:
        return AdmissionDecision(False, "tool_not_allowlisted")
    if not any(
        (
            item.get("input_schema_digest"),
            item.get("annotation_digest"),
            item.get("effect_class"),
        )
        == (
            request.input_schema_digest,
            request.annotation_digest,
            request.effect_class,
        )
        for item in matches
    ):
        return AdmissionDecision(False, "tool_contract_mismatch")
    return AdmissionDecision(True, "allowed")


@dataclass(frozen=True)
class TrustShiftPolicy:
    policy_id: str
    expected_samples: int
    semantic_paths: Mapping[str, Any]
    scope_path: str
    timing_classes: set[str]


def _at_path(value: Mapping[str, Any], path: str) -> Any:
    item: Any = value
    for part in path.split("."):
        if not isinstance(item, Mapping) or part not in item:
            return None
        item = item[part]
    return item


def _shape(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _shape(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_shape(value[0])] if value else []
    return type(value).__name__


def establish_baseline(
    server_identity: str,
    tool_identity: str,
    schema_digest: str,
    clearance_id: str,
    policy: TrustShiftPolicy,
    responses: Sequence[Mapping[str, Any]],
    timing_classes: Sequence[str],
) -> dict[str, Any]:
    """Create a scoped baseline only from the policy's bounded benign corpus."""
    if len(responses) != policy.expected_samples or len(timing_classes) != len(
        responses
    ):
        raise TrustStackError("invalid_trust_window")
    shapes = {
        _digest
        for _digest in (digest_payload(_shape(response)) for response in responses)
    }
    if len(shapes) != 1:
        raise TrustStackError("baseline_structural_inconsistent")
    invariants = {path: _at_path(responses[0], path) for path in policy.semantic_paths}
    if any(
        _at_path(response, path) != expected
        for response in responses
        for path, expected in invariants.items()
    ):
        raise TrustStackError("baseline_semantic_inconsistent")
    scope = sorted(
        {
            str(record.get("id"))
            for response in responses
            for record in (_at_path(response, policy.scope_path) or [])
            if isinstance(record, Mapping) and "id" in record
        }
    )
    payload = {
        "server_identity": server_identity,
        "tool_identity": tool_identity,
        "schema_digest": schema_digest,
        "clearance_id": clearance_id,
        "baseline_policy_id": policy.policy_id,
        "trust_window": {"samples": len(responses)},
        "shape_digest": next(iter(shapes)),
        "semantic_invariants": invariants,
        "scope_path": policy.scope_path,
        "scope_ids": scope,
        "timing_classes": sorted(set(timing_classes)),
        "fixture_cohort_digest": digest_payload(list(responses)),
    }
    return {**payload, "baseline_digest": digest_payload(payload)}


def watch_response(
    baseline: Mapping[str, Any], response: Mapping[str, Any], *, timing_class: str
) -> dict[str, Any]:
    """Detect local structural, semantic, and scope drift without retaining raw response bytes."""
    signals: list[str] = []
    if digest_payload(_shape(response)) != baseline.get("shape_digest"):
        signals.append("structural_mutation")
    for path, expected in baseline.get("semantic_invariants", {}).items():
        if _at_path(response, path) != expected:
            signals.append("semantic_invariant_violation")
    policy_scope = baseline.get("scope_ids", [])
    scope = {
        str(record.get("id"))
        for record in (_at_path(response, str(baseline.get("scope_path"))) or [])
        if isinstance(record, Mapping) and "id" in record
    }
    if not scope <= set(policy_scope):
        signals.append("scope_expansion")
    if timing_class not in set(baseline.get("timing_classes", [])):
        signals.append("benign_drift_candidate")
    decision = "allow" if not signals else "quarantine"
    return {
        "baseline_digest": baseline.get("baseline_digest"),
        "response_observation": {
            "shape_digest": digest_payload(_shape(response)),
            "timing_class": timing_class,
        },
        "signal_kinds": sorted(signals),
        "decision": decision,
        "limitations": [
            "ground-truth-free monitoring detects drift but cannot prove truth or prevent availability failures"
        ],
    }
