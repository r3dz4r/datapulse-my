#!/usr/bin/env python3
"""Resolve immutable sets and validate append-only discovery without date aliases."""
from __future__ import annotations

import base64
import hashlib
import json
import sys
import re
from datetime import date
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.verify_attestation_binding import (
    ContractError, _digest_bytes, _load, _parse_time, _verify_legacy_plane,
    _verify_signature, canonical, verify_rekor_evidence,
)

SET_REF = re.compile(r"attestations/(\d{4}-\d{2}-\d{2})(?:/revisions/([0-9a-f]{64}))?/([A-Za-z0-9_-]+)\.json")
FILES = ("chain_head.json", "index.json", "binding.json", "scores.json")
# Rewritten every health cycle: the latest copy is fresher than the chain head's
# frozen set, so byte-equality with that set is unsatisfiable.
PIPELINE_OWNED_PROJECTIONS = ("scores.json",)


def set_directory(reference: str, filename: str = "chain_head.json") -> str:
    """Accept only legacy or hash-addressed immutable set paths."""
    match = SET_REF.fullmatch(reference) if isinstance(reference, str) else None
    if match is None or reference.rsplit("/", 1)[1] != filename:
        raise ContractError("unsafe immutable attestation reference")
    date.fromisoformat(match[1])
    return reference.rsplit("/", 1)[0]


def correction_record(day: str, original: str, previous: str, old_digest: str, digest: str) -> dict[str, Any]:
    """Define the signed correction identity and deterministic provenance.

    The revision id is content-addressed on the predecessor head and the new
    health digest, so the immutable health snapshot it names can be written
    before the set itself exists.  Naming the revision directory after the
    chain head (as this branch's discovery does) would make the snapshot
    reference self-referential.
    """
    revision = hashlib.sha256(canonical({"previous_chain_head": previous, "health_sha256": digest})).hexdigest()
    return {
        "schema": "datapulse/v1/attestation-correction",
        "revision_id": revision,
        "reason": "health artifact bytes changed",
        "original_chain_head": original,
        "supersedes_chain_head": previous,
        "previous_health_sha256": old_digest,
        "health_sha256": digest,
        "health_snapshot_ref": f"attestations/{day}/revisions/{revision}/health.json",
    }


def verify_set(root: Path, reference: str, *, verify_datasets: bool = True) -> dict[str, Any]:
    """Verify historical integrity independently of today's canonical health."""
    directory = set_directory(reference)
    head = _load(root / reference, "immutable chain head")
    index = _load(root / directory / "index.json", "immutable index")
    binding = _load(root / directory / "binding.json", "immutable binding")
    scores = _load(root / directory / "scores.json", "immutable scores")
    payload = binding.get("payload", {})
    registry = _load(root / "docs/.well-known/datapulse-probe-keys.json", "key registry")
    matches = [r for r in registry.get("keys", []) if r.get("key_id") == payload.get("ed25519", {}).get("key_id")]
    if registry.get("schema") != "datapulse/v2/probe-key-registry" or len(matches) != 1:
        raise ContractError("historical attestation key missing or ambiguous")
    row = matches[0]
    published = _parse_time(payload.get("published_at"), "publication time")
    if (row.get("purpose") != "attestation-chain-signing" or row.get("status") == "compromised"
            or row.get("compromised_at") or not (_parse_time(row.get("not_before"), "key start") <= published <= _parse_time(row.get("not_after"), "key end"))):
        raise ContractError("historical signer is unauthorized")
    public = Ed25519PublicKey.from_public_bytes(base64.b64decode(row["public_key_base64"], validate=True))
    _verify_signature(public, payload, binding.get("signature_base64"), "immutable binding")
    _verify_legacy_plane(root, index, head, public, row, verify_datasets=verify_datasets)
    if (binding.get("schema") != "datapulse/v1/attestation-binding-envelope"
            or payload.get("schema") != "datapulse/v1/attestation-binding"
            or payload.get("date") != head["payload"]["date"]
            or payload.get("ed25519", {}).get("chain_head_ref") != reference
            or payload.get("ed25519", {}).get("chain_head") != head["chain_head"]
            or index.get("binding_ref") != directory + "/binding.json"):
        raise ContractError("immutable binding/index/head disagree")
    match = SET_REF.fullmatch(reference)
    if match[1] != head["payload"]["date"] or (match[2] and match[2] != head["chain_head"]):
        raise ContractError("immutable head path identity mismatch")
    ids = sorted(index["attestations"])
    claim = payload.get("health", {})
    if claim.get("dataset_count") != len(ids) or claim.get("dataset_ids_sha256") != hashlib.sha256(canonical(ids)).hexdigest():
        raise ContractError("immutable binding membership mismatch")
    if scores.get("schema") != "datapulse/v1/trust-scores" or sorted(r["dataset_id"] for r in scores.get("datasets", [])) != ids:
        raise ContractError("immutable scores membership mismatch")
    rekor = binding.get("rekor")
    if rekor is not None:
        verify_rekor_evidence(root, rekor, claim.get("artifact_sha256"))
    # A recorded health snapshot pins the exact input a correction superseded;
    # when present it must match the signed claim. Main's same-day correction
    # evidence lives here, so the branch's lineage verifier must check it too.
    snapshot = root / directory / "health.json"
    if snapshot.exists() and _digest_bytes(snapshot.read_bytes()) != claim.get("artifact_sha256"):
        raise ContractError("dated health snapshot digest is invalid")
    record = payload.get("correction")
    if record is not None:
        if not isinstance(record, dict):
            raise ContractError("signed correction provenance is invalid")
        revision = record.get("revision_id")
        if (record.get("schema") != "datapulse/v1/attestation-correction"
                or not isinstance(revision, str) or re.fullmatch(r"[0-9a-f]{64}", revision) is None
                or record.get("health_snapshot_ref") != f"attestations/{payload.get('date')}/revisions/{revision}/health.json"
                or record.get("health_sha256") != claim.get("artifact_sha256")
                or record.get("supersedes_chain_head") != head["payload"].get("previous_chain_head")
                or head["payload"].get("correction") != record):
            raise ContractError("signed correction provenance is invalid")
        # The immutable correction snapshot is only present in a fully fetched
        # plane; the served head-only check validates the signed record instead.
        correction_snapshot = root / record["health_snapshot_ref"]
        if verify_datasets and not correction_snapshot.is_file():
            raise ContractError("signed correction health snapshot is missing")
        if correction_snapshot.is_file() and _digest_bytes(correction_snapshot.read_bytes()) != record.get("health_sha256"):
            raise ContractError("signed correction health snapshot digest is invalid")
    if binding.get("claims") != {"artifact_signed": rekor is not None, "rekor_witnessed": rekor is not None, "source_truth_verified": False}:
        raise ContractError("immutable binding evidence claims disagree")
    return head


def descriptor(head: dict, reference: str, sequence: int) -> dict:
    """Derive unsigned discovery fields from verified signed evidence."""
    directory = set_directory(reference)
    return {"date": head["payload"]["date"], "sequence": sequence,
            "parent_head": head["payload"]["previous_chain_head"],
            "index_ref": directory + "/index.json", "binding_ref": directory + "/binding.json",
            "scores_ref": directory + "/scores.json"}


def discovery(root: Path, *, verify_datasets: bool = True) -> dict:
    """Validate v2, or derive v2 from verified v1 entries without rewriting evidence."""
    path = root / "attestations/chain-index.json"
    if not path.exists():
        return {"schema": "datapulse/v2/chain-index", "heads": {}, "anchors": {}, "envelopes": {}, "days": {}, "current_head": None}
    document = _load(path, "chain index")
    if document.get("schema") not in {"datapulse/v1/chain-index", "datapulse/v2/chain-index"}:
        raise ContractError("unknown chain index schema")
    heads = document.get("heads")
    if not isinstance(heads, dict) or len(set(heads.values())) != len(heads):
        raise ContractError("duplicate or invalid chain head mapping")
    if document["schema"] == "datapulse/v1/chain-index":
        result = {**document, "schema": "datapulse/v2/chain-index", "envelopes": {}, "days": {}}
        for digest, reference in heads.items():
            try:
                head = verify_set(root, reference, verify_datasets=verify_datasets)
                if head["chain_head"] != digest:
                    continue  # Preserve unresolved historical map entries, never assert them.
            except (ValueError, OSError, KeyError, TypeError):
                continue
            day = head["payload"]["date"]
            if day in result["days"]:
                raise ContractError("duplicate-date attestation ambiguity detected")
            result["envelopes"][digest] = descriptor(head, reference, 1)
            result["days"][day] = [digest]
        current = _load(root / "attestations/latest/chain_head.json", "migration head")["chain_head"]
        if current not in result["envelopes"]:
            raise ContractError("migration head is unresolved")
        result["current_head"] = current
        # Pins the historical-gap boundary; descendants may never silently reset it.
        result["migration_head"] = current
        result["unresolved_heads"] = sorted(set(heads) - set(result["envelopes"]))
        document = result
    validate_discovery(root, document, verify_datasets=verify_datasets)
    return document


def assert_head_extends_base(document: dict, base_head: str | None) -> set[str]:
    """Walk verified signed predecessors to the accepted base, or genesis.

    Descriptors must first be checked against their signed envelopes. A mirror
    belongs to the candidate's current head; the base is an ancestor identity,
    never the bytes that an appended mirror is expected to retain.
    """
    envelopes, days = document["envelopes"], document["days"]
    cursor, visited = document["current_head"], set()
    while cursor != base_head:
        if cursor in visited or cursor not in envelopes:
            raise ContractError("forward lineage has a cycle or unresolved parent")
        visited.add(cursor)
        child = envelopes[cursor]
        parent = child["parent_head"]
        if parent == "0" * 64 and base_head is None:
            break
        if parent not in envelopes or envelopes[parent]["date"] > child["date"]:
            raise ContractError("forward lineage parent missing or date moved backwards")
        if days[envelopes[parent]["date"]][-1] != parent and envelopes[parent]["date"] != child["date"]:
            raise ContractError("next day extends a superseded head")
        cursor = parent
    return visited


def validate_discovery(root: Path, document: dict, *, verify_datasets: bool = True) -> None:
    """Check exact descriptors, day runs, and the accepted forward lineage."""
    heads, envelopes, days = (document.get(k, {}) for k in ("heads", "envelopes", "days"))
    seen = set()
    for day, run in days.items():
        date.fromisoformat(day)
        if not isinstance(run, list) or not run:
            raise ContractError("invalid day list")
        original = run[0]
        previous_health: str | None = None
        for sequence, digest in enumerate(run, 1):
            if digest in seen or digest not in envelopes or digest not in heads:
                raise ContractError("repeated or unresolved discovery head")
            seen.add(digest)
            head = verify_set(root, heads[digest], verify_datasets=verify_datasets)
            if head["chain_head"] != digest or head["payload"]["date"] != day or envelopes[digest] != descriptor(head, heads[digest], sequence):
                raise ContractError("discovery descriptor disagrees with signed set")
            if sequence > 1 and head["payload"]["previous_chain_head"] != run[sequence - 2]:
                raise ContractError("same-day fork or missing parent")
            directory = set_directory(heads[digest])
            payload = _load(root / directory / "binding.json", "immutable binding")["payload"]
            record = payload.get("correction")
            if sequence == 1:
                if record is not None:
                    raise ContractError("original attestation cannot be a correction")
            else:
                if not isinstance(record, dict) or previous_health is None:
                    raise ContractError("same-day correction is missing its signed provenance")
                expected = correction_record(day, original, run[sequence - 2], previous_health, payload["health"]["artifact_sha256"])
                if record != expected or head["payload"].get("correction") != record:
                    raise ContractError("signed correction provenance disagrees with the append lineage")
            previous_health = payload["health"]["artifact_sha256"]
    if set(heads) - seen != set(document.get("unresolved_heads", [])):
        raise ContractError("unresolved head mappings changed without reconciliation")
    if seen != set(envelopes):
        raise ContractError("day lists and descriptors disagree")
    current = document.get("current_head")
    if not seen and current is None:
        return
    if current not in seen or current != days[max(days)][-1]:
        raise ContractError("current selector is not the terminal accepted head")
    boundary = document.get("migration_head")
    visited = assert_head_extends_base(document, boundary)
    forward = {h for h, entry in envelopes.items() if boundary is None or entry["date"] >= envelopes[boundary]["date"]}
    if forward != visited | ({boundary} if boundary else set()):
        raise ContractError("fork or disconnected accepted forward head")


def legacy_mirror_expected_schema(root: Path) -> str:
    """Read the committed chain-index schema that controls legacy mirror checks."""
    return _load(root / "attestations/chain-index.json", "chain index")["schema"]


def verify_legacy_mirror(root: Path, document: dict[str, Any], directory: str) -> None:
    """Reject a stale legacy head mirror for the resolved current head."""
    mirror = root / ".attestations/chain_head.json"
    if (mirror.is_file()
            and legacy_mirror_expected_schema(root) == "datapulse/v2/chain-index"
            and mirror.read_bytes() != (root / directory / "chain_head.json").read_bytes()):
        raise ContractError("legacy mirror disagrees with current head")


def selected_directory(root: Path, *, projections: bool = True, verify_datasets: bool = True) -> str:
    """Resolve current identity and reject mixtures of latest and immutable bytes."""
    document = discovery(root, verify_datasets=verify_datasets)
    digest = document["current_head"]
    directory = set_directory(document["heads"][digest])
    if projections:
        for filename in FILES:
            projection = root / "attestations/latest" / filename
            if not projection.is_file():
                raise ContractError("latest projection is stale or mixed")
            frozen = root / directory / filename
            if filename in PIPELINE_OWNED_PROJECTIONS:
                latest_scores = _load(projection, "latest scores projection")
                frozen_scores = _load(frozen, "immutable scores")
                if _parse_time(latest_scores.get("generated_at"), "latest scores generated_at") < _parse_time(
                    frozen_scores.get("generated_at"), "immutable scores generated_at"
                ):
                    raise ContractError("latest projection is stale or mixed")
            elif projection.read_bytes() != frozen.read_bytes():
                raise ContractError("latest projection is stale or mixed")
        # The legacy mirror is a mutable projection; a historical verification
        # plane assembled from immutable bytes is not required to carry it.
        # Compare only within this candidate tree. Accepted-base ancestry is
        # established through signed predecessors, not mirror byte identity.
        verify_legacy_mirror(root, document, directory)
    return directory
