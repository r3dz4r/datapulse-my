#!/usr/bin/env python3
"""Resolve immutable sets and validate append-only discovery without date aliases."""
from __future__ import annotations

import base64
import json
import sys
import re
from datetime import date
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.verify_attestation_binding import (
    ContractError, _load, _parse_time, _verify_legacy_plane, _verify_signature,
    verify_rekor_evidence,
)

SET_REF = re.compile(r"attestations/(\d{4}-\d{2}-\d{2})(?:/revisions/([0-9a-f]{64}))?/([A-Za-z0-9_-]+)\.json")
FILES = ("chain_head.json", "index.json", "binding.json", "scores.json")


def set_directory(reference: str, filename: str = "chain_head.json") -> str:
    """Accept only legacy or hash-addressed immutable set paths."""
    match = SET_REF.fullmatch(reference) if isinstance(reference, str) else None
    if match is None or reference.rsplit("/", 1)[1] != filename:
        raise ContractError("unsafe immutable attestation reference")
    date.fromisoformat(match[1])
    return reference.rsplit("/", 1)[0]


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
    import hashlib
    from scripts.verify_attestation_binding import canonical
    claim = payload.get("health", {})
    if claim.get("dataset_count") != len(ids) or claim.get("dataset_ids_sha256") != hashlib.sha256(canonical(ids)).hexdigest():
        raise ContractError("immutable binding membership mismatch")
    if scores.get("schema") != "datapulse/v1/trust-scores" or sorted(r["dataset_id"] for r in scores.get("datasets", [])) != ids:
        raise ContractError("immutable scores membership mismatch")
    rekor = binding.get("rekor")
    if rekor is not None:
        verify_rekor_evidence(root, rekor, claim.get("artifact_sha256"))
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


def validate_discovery(root: Path, document: dict, *, verify_datasets: bool = True) -> None:
    """Check exact descriptors, day runs, and the accepted forward lineage."""
    heads, envelopes, days = (document.get(k, {}) for k in ("heads", "envelopes", "days"))
    seen = set()
    for day, run in days.items():
        date.fromisoformat(day)
        if not isinstance(run, list) or not run:
            raise ContractError("invalid day list")
        for sequence, digest in enumerate(run, 1):
            if digest in seen or digest not in envelopes or digest not in heads:
                raise ContractError("repeated or unresolved discovery head")
            seen.add(digest)
            head = verify_set(root, heads[digest], verify_datasets=verify_datasets)
            if head["chain_head"] != digest or head["payload"]["date"] != day or envelopes[digest] != descriptor(head, heads[digest], sequence):
                raise ContractError("discovery descriptor disagrees with signed set")
            if sequence > 1 and head["payload"]["previous_chain_head"] != run[sequence - 2]:
                raise ContractError("same-day fork or missing parent")
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
    cursor, visited = current, set()
    while cursor != boundary:
        if cursor in visited or cursor not in envelopes:
            raise ContractError("forward lineage has a cycle or unresolved parent")
        visited.add(cursor)
        child = envelopes[cursor]
        parent = child["parent_head"]
        if parent == "0" * 64 and boundary is None:
            break
        if parent not in envelopes or envelopes[parent]["date"] > child["date"]:
            raise ContractError("forward lineage parent missing or date moved backwards")
        if days[envelopes[parent]["date"]][-1] != parent and envelopes[parent]["date"] != child["date"]:
            raise ContractError("next day extends a superseded head")
        cursor = parent
    forward = {h for h, entry in envelopes.items() if boundary is None or entry["date"] >= envelopes[boundary]["date"]}
    if forward != visited | ({boundary} if boundary else set()):
        raise ContractError("fork or disconnected accepted forward head")


def selected_directory(root: Path, *, projections: bool = True, verify_datasets: bool = True) -> str:
    """Resolve current identity and reject mixtures of latest and immutable bytes."""
    document = discovery(root, verify_datasets=verify_datasets)
    digest = document["current_head"]
    directory = set_directory(document["heads"][digest])
    if projections:
        for filename in FILES:
            projection = root / "attestations/latest" / filename
            if not projection.is_file() or projection.read_bytes() != (root / directory / filename).read_bytes():
                raise ContractError("latest projection is stale or mixed")
        mirror = root / ".attestations/chain_head.json"
        if _load(root / "attestations/chain-index.json", "chain index")["schema"] == "datapulse/v2/chain-index" and mirror.read_bytes() != (root / directory / "chain_head.json").read_bytes():
            raise ContractError("legacy mirror disagrees with current head")
    return directory
