"""Contract tests for the historical-observation/v1 envelope schema.

Fixtures live inline in this file on purpose: the envelope contract must be
defensible before any capture, storage or signing code exists, and every
invalid fixture must fail for a named member and keyword, not merely falsy.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "historical-observation.schema.json").read_text(encoding="utf-8"))
HEALTH_SCHEMA = json.loads((ROOT / "health.schema.json").read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())

HEALTH_STATUSES = HEALTH_SCHEMA["properties"]["datasets"]["items"]["properties"]["status"]["enum"]
REPLAY_STATES = SCHEMA["properties"]["replay_state"]["enum"]

EXPECTED_MEMBERS = {
    "schema",
    "observation_id",
    "dataset_id",
    "source_identity",
    "source_url",
    "observed_request_url",
    "observed_at",
    "retrieved_at",
    "source_content_date",
    "source_version",
    "capture_policy",
    "capture_status",
    "source_digest",
    "observation_digest",
    "shape_fingerprint",
    "normalized_projection",
    "normalization_profile_version",
    "previous_observation_id",
    "previous_observation_digest",
    "change_from_previous",
    "verification",
    "attestation_ref",
    "witness_refs",
    "claim_boundary",
    "unknown_reasons",
    "cycle_root",
    "contract_digest",
    "superseded_by",
    "invalidated_by",
    "declared",
    "observed",
    "publisher_credential",
    "verifier_credential",
    "replay_state",
}

# .attestations/chain_head.json publishes bare 64-hex values for chain_head,
# previous_chain_head and dataset_links_sha256 — no "observation:" prefix.
# A chain-head value pasted into same-dataset history must fail on pattern.
CHAIN_HEAD_VALUE = "a3a337d7d4efd5516c74255ebe80849b58d66fe57fec5ee8c50dd17a77c0e023"

IDENTITY_LIMITATION = (
    "Identity is declared or independently supported; "
    "it is not a certification of authority, control, or authenticity."
)
SHAPE_LIMITATION = (
    "Structural fingerprint over keys, types, and headers only; "
    "it is not a digest of the source content."
)
VERIFICATION_LIMITATION = (
    "Verification status is cryptographic and procedural only; "
    "it is neither a freshness classification nor a statement of semantic truth."
)


def _captured_envelope() -> dict[str, Any]:
    return {
        "schema": "historical-observation/v1",
        "observation_id": "obs-fuelprice-20260913t000642z",
        "dataset_id": "fuelprice",
        "source_identity": {
            "identity_value": "Malaysia Ministry of Finance weekly fuel price bulletin",
            "basis": "declared_by_source",
            "limitation": IDENTITY_LIMITATION,
        },
        "source_url": "https://data.gov.my/data-catalogue/fuelprice",
        "observed_request_url": "https://storage.data.gov.my/opendata/fuelprice/fuelprice.csv",
        "observed_at": "2026-09-13T00:06:42Z",
        "retrieved_at": "2026-09-13T00:05:12Z",
        "source_content_date": "2026-09-10",
        "source_version": {"value": "2026-w37", "basis": "observed_in_content"},
        "capture_policy": "full_source_bytes",
        "capture_status": "captured",
        "source_digest": "sha256:" + "ab" * 32,
        "observation_digest": "observation:sha256:" + "cd" * 32,
        "shape_fingerprint": {
            "algorithm": "shape-v1",
            "value": "9d" * 32,
            "basis": "csv-headers",
            "limitation": SHAPE_LIMITATION,
        },
        "normalized_projection": {"state": "retained", "format": "csv", "record_count": 620},
        "normalization_profile_version": "datapulse-normalization-profile/v1",
        "previous_observation_id": "obs-fuelprice-20260906t000639z",
        "previous_observation_digest": "observation:sha256:" + "ef" * 32,
        "change_from_previous": "changed",
        "verification": {
            "verification_status": "verified",
            "verified_at": "2026-09-13T00:07:03Z",
            "method": "observation_digest-recompute+ed25519-chain-attestation",
            "limitation": VERIFICATION_LIMITATION,
        },
        "attestation_ref": ".attestations/latest/2026-09-13.json",
        "witness_refs": [],
        "claim_boundary": {
            "may_conclude": [
                "A source was observed at the recorded request URL and times",
                "The recorded digests bind to exactly the bytes captured at that time",
            ],
            "may_not_conclude": [
                "That the content is fresh, authoritative, complete, or correct",
                "That verification status implies freshness or semantic truth",
            ],
        },
        "unknown_reasons": [],
        "cycle_root": {
            "root": "cycle-root:sha256:" + "11" * 32,
            "algorithm": "merkle-sha256",
            "observation_count": 418,
        },
        "contract_digest": "contract:sha256:" + "22" * 32,
        "superseded_by": None,
        "invalidated_by": None,
        "declared": {
            "entries": [
                {
                    "subject": "refresh_cadence",
                    "value": "weekly",
                    "basis": "data.gov.my catalogue metadata",
                }
            ]
        },
        "observed": {
            "entries": [
                {
                    "subject": "refresh_cadence",
                    "value": 7,
                    "basis": "days between the last two observed source_content_date values",
                }
            ]
        },
        "publisher_credential": None,
        "verifier_credential": None,
        "replay_state": "replayable",
    }


def _metadata_only_envelope() -> dict[str, Any]:
    envelope = _captured_envelope()
    envelope["capture_status"] = "metadata_only"
    envelope["source_digest"] = None
    envelope["replay_state"] = "not_replayable"
    return envelope


def _errors(envelope: dict[str, Any]) -> list[ValidationError]:
    return sorted(
        VALIDATOR.iter_errors(envelope),
        key=lambda error: (list(error.path), str(error.validator)),
    )


def _failing(
    errors: list[ValidationError],
    path: list[str],
    keyword: str,
    fragment: str = "",
) -> list[ValidationError]:
    return [
        error
        for error in errors
        if list(error.path) == path and error.validator == keyword and fragment in error.message
    ]


def test_schema_is_a_valid_draft_2020_12_schema() -> None:
    Draft202012Validator.check_schema(SCHEMA)


def test_contract_member_set_is_pinned() -> None:
    assert set(SCHEMA["required"]) == EXPECTED_MEMBERS
    assert set(SCHEMA["properties"]) == EXPECTED_MEMBERS
    assert SCHEMA["additionalProperties"] is False


def test_valid_envelope_validates_cleanly() -> None:
    assert _errors(_captured_envelope()) == []


def test_missing_required_member_is_rejected_for_that_member() -> None:
    envelope = _captured_envelope()
    del envelope["observation_digest"]

    errors = _errors(envelope)

    assert errors
    assert _failing(errors, [], "required", "observation_digest")


def test_explicit_unknown_source_version_is_representable() -> None:
    envelope = _captured_envelope()
    envelope["source_version"] = "unknown"
    envelope["unknown_reasons"] = ["source_version"]

    assert _errors(envelope) == []


def test_fabricated_bare_source_version_is_rejected() -> None:
    # In the source_version position a bare string may only be the explicit
    # unknown marker; a real version must travel as {value, basis} so a
    # fabricated value has nowhere to hide.
    envelope = _captured_envelope()
    envelope["source_version"] = "2026-w37-final"

    errors = _errors(envelope)

    assert errors
    assert _failing(errors, ["source_version"], "oneOf")


def test_unknown_source_version_requires_a_reason_entry() -> None:
    envelope = _captured_envelope()
    envelope["source_version"] = "unknown"
    envelope["unknown_reasons"] = []

    errors = _errors(envelope)

    assert errors
    assert _failing(errors, ["unknown_reasons"], "contains")


def test_source_digest_for_uncaptured_bytes_is_rejected() -> None:
    envelope = _captured_envelope()
    envelope["capture_status"] = "not_captured"
    envelope["replay_state"] = "not_replayable"

    errors = _errors(envelope)

    assert errors
    assert _failing(errors, ["source_digest"], "type", "null")
    assert not _failing(errors, ["capture_status"], "enum")


def test_chain_head_value_in_previous_observation_digest_is_rejected() -> None:
    envelope = _captured_envelope()
    envelope["previous_observation_digest"] = CHAIN_HEAD_VALUE

    errors = _errors(envelope)

    assert errors
    assert _failing(errors, ["previous_observation_digest"], "pattern")

    prefixed = _captured_envelope()
    prefixed["previous_observation_digest"] = "sha256:" + CHAIN_HEAD_VALUE

    prefixed_errors = _errors(prefixed)

    assert prefixed_errors
    assert _failing(prefixed_errors, ["previous_observation_digest"], "pattern")


def test_replayable_without_captured_source_digest_is_rejected() -> None:
    envelope = _metadata_only_envelope()
    envelope["replay_state"] = "replayable"

    errors = _errors(envelope)

    assert errors
    assert _failing(errors, ["source_digest"], "type", "string")
    assert _failing(errors, ["capture_status"], "const")


def test_unknown_extra_member_is_rejected() -> None:
    envelope = _captured_envelope()
    envelope["session_id"] = "not-allowed"

    errors = _errors(envelope)

    assert errors
    assert _failing(errors, [], "additionalProperties", "session_id")


@pytest.mark.parametrize("state", REPLAY_STATES)
def test_every_replay_state_member_validates_alone(state: str) -> None:
    envelope = _captured_envelope() if state == "replayable" else _metadata_only_envelope()
    envelope["replay_state"] = state

    assert _errors(envelope) == []


def test_replay_state_outside_the_vocabulary_is_rejected() -> None:
    envelope = _metadata_only_envelope()
    envelope["replay_state"] = "mostly-replayable"

    errors = _errors(envelope)

    assert errors
    assert _failing(errors, ["replay_state"], "enum")


def test_previous_digest_requires_previous_id() -> None:
    envelope = _captured_envelope()
    envelope["previous_observation_id"] = None

    errors = _errors(envelope)

    assert errors
    assert _failing(errors, ["previous_observation_id"], "type", "string")


def test_reserved_credentials_must_stay_null_in_this_phase() -> None:
    populated_publisher = _captured_envelope()
    populated_publisher["publisher_credential"] = {"type": "Ed25519VerificationKey2020"}

    publisher_errors = _errors(populated_publisher)

    assert publisher_errors
    assert _failing(publisher_errors, ["publisher_credential"], "type", "null")

    populated_verifier = _captured_envelope()
    populated_verifier["verifier_credential"] = {"credential_schema": "w3c-vc/v2"}

    verifier_errors = _errors(populated_verifier)

    assert verifier_errors
    assert _failing(verifier_errors, ["verifier_credential"], "type", "null")


def test_replay_and_verification_vocabularies_stay_off_the_health_axis() -> None:
    replay = set(REPLAY_STATES)
    verification = set(
        SCHEMA["properties"]["verification"]["properties"]["verification_status"]["enum"]
    )
    health = set(HEALTH_STATUSES)

    assert replay & health == {"unknown"}
    assert verification & health == {"unknown"}
    assert "fresh" not in replay
    assert "replayable" not in health


def test_three_time_axes_have_separate_members() -> None:
    properties = SCHEMA["properties"]

    assert {"observed_at", "retrieved_at", "source_content_date"} <= set(properties)
    assert properties["observed_at"]["type"] == "string"
    assert properties["retrieved_at"]["type"] == ["string", "null"]
    assert properties["source_content_date"]["type"] == ["string", "null"]
