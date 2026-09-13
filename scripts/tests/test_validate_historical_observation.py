"""Focused tests for the historical-observation field-provenance validator."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from validate_historical_observation import validate_envelope  # noqa: E402

SCRIPT = ROOT / "scripts" / "validate_historical_observation.py"


def _captured_envelope() -> dict[str, Any]:
    identity_limitation = "Identity is declared or independently supported; it is not a certification of authority, control, or authenticity."
    shape_limitation = "Structural fingerprint over keys, types, and headers only; it is not a digest of the source content."
    verification_limitation = "Verification status is cryptographic and procedural only; it is neither a freshness classification nor a statement of semantic truth."
    envelope: dict[str, Any] = {
        "schema": "historical-observation/v2", "observation_id": "obs-fuelprice-20260913t000642z", "dataset_id": "fuelprice",
        "source_identity": {"identity_value": "Ministry", "basis": "declared_by_source", "limitation": identity_limitation},
        "source_url": "https://data.gov.my/data-catalogue/fuelprice", "observed_request_url": "https://storage.data.gov.my/fuelprice.csv",
        "observed_at": "2026-09-13T00:06:42Z", "retrieved_at": "2026-09-13T00:05:12Z", "source_content_date": "2026-09-10",
        "source_version": {"value": "2026-w37", "basis": "observed_in_content"}, "capture_policy": "full_source_bytes", "capture_status": "captured",
        "source_digest": "sha256:" + "ab" * 32, "observation_digest": "observation:sha256:" + "cd" * 32,
        "shape_fingerprint": {"algorithm": "shape-v1", "value": "9d" * 32, "basis": "csv-headers", "limitation": shape_limitation},
        "normalized_projection": {"state": "retained", "format": "csv", "record_count": 620}, "normalization_profile_version": "datapulse-normalization-profile/v1",
        "previous_observation_id": "obs-fuelprice-20260906t000639z", "previous_observation_digest": "observation:sha256:" + "ef" * 32,
        "change_from_previous": "changed", "verification": {"verification_status": "verified", "verified_at": "2026-09-13T00:07:03Z", "method": "digest", "limitation": verification_limitation},
        "attestation_ref": ".attestations/latest/2026-09-13.json", "witness_refs": [],
        "claim_boundary": {"may_conclude": ["A source was observed"], "may_not_conclude": ["That it is true"]}, "unknown_reasons": [],
        "cycle_root": {"root": "cycle-root:sha256:" + "11" * 32, "algorithm": "merkle-sha256", "observation_count": 418},
        "contract_digest": "contract:sha256:" + "22" * 32, "superseded_by": None, "invalidated_by": None,
        "declared": {"entries": []}, "observed": {"entries": []}, "publisher_credential": None, "verifier_credential": None, "replay_state": "replayable",
    }
    null_counters = {"rows": None, "delivered": None, "empty": None, "stringified": None, "truncated": None}
    source_supplied = {
        "source_url", "source_content_date", "source_version", "source_identity", "declared", "observed",
    }
    declared_by_source = {"source_identity", "declared"}
    configured_by_policy = {"capture_policy"}
    members = list(envelope.items())
    envelope["field_provenance"] = {}
    for member, value in members:
        if value is None:
            basis, derived, state, reason = "not_measured", False, "unmeasured", "unresolved"
        elif member in source_supplied:
            basis = "declared_by_source" if member in declared_by_source else "copied_from_source"
            derived, state, reason = False, "measured", None
        elif member in configured_by_policy:
            basis, derived, state, reason = "configured_by_policy", True, "measured", None
        else:
            basis, derived, state, reason = "platform_computed", True, "measured", None
        envelope["field_provenance"][member] = {
            "basis": basis, "derived": derived, "state": state,
            "not_measured_reason": reason, "transform": None, "counters": null_counters.copy(),
        }
    for member in ("publisher_credential", "verifier_credential"):
        envelope["field_provenance"][member] = {"basis": "not_applicable", "derived": False, "state": "not_applicable", "not_measured_reason": "does_not_apply", "transform": None, "counters": null_counters.copy()}
    return envelope


def _assert_only_rule(envelope: dict[str, Any], expected: str) -> None:
    rules = validate_envelope(envelope)
    assert any(rule.startswith(expected) for rule in rules), rules
    assert not any(
        finding.startswith(f"FP-{number}")
        for number in range(1, 9)
        if f"FP-{number}" != expected
        for finding in rules
    ), rules


def test_valid_control_and_cli_pass(tmp_path: Path) -> None:
    envelope = _captured_envelope()
    valid = tmp_path / "valid.json"
    valid.write_text(json.dumps(envelope), encoding="utf-8")
    Path("/tmp/hist-obs-valid.json").write_text(json.dumps(envelope), encoding="utf-8")
    assert validate_envelope(envelope) == []
    result = subprocess.run([sys.executable, str(SCRIPT), str(valid)], text=True, capture_output=True, check=False)
    assert result.returncode == 0
    assert result.stdout == f"PASS {valid}\n"


def test_fixture_exercises_both_derived_biconditional_branches() -> None:
    entries = _captured_envelope()["field_provenance"].values()
    assert any(entry["derived"] is True and entry["basis"] in {"platform_computed", "configured_by_policy"} for entry in entries)
    assert any(entry["derived"] is False and entry["basis"] not in {"platform_computed", "configured_by_policy"} for entry in entries)


@pytest.mark.parametrize("rule", range(1, 9))
def test_each_provenance_rule_has_one_red_case(rule: int) -> None:
    envelope = _captured_envelope()
    provenance = envelope["field_provenance"]
    if rule == 1:
        provenance["not_a_member"] = copy.deepcopy(provenance["schema"])
    elif rule == 2:
        provenance["superseded_by"] = {**provenance["superseded_by"], "state": "measured", "not_measured_reason": None}
    elif rule == 3:
        provenance["source_digest"] = {**provenance["source_digest"], "state": "unmeasured", "not_measured_reason": "unresolved"}
    elif rule == 4:
        provenance["superseded_by"] = {**provenance["superseded_by"], "not_measured_reason": "does_not_apply"}
    elif rule == 5:
        provenance["source_content_date"] = {**provenance["source_content_date"], "basis": "unknown"}
    elif rule == 6:
        provenance["schema"] = {**provenance["schema"], "counters": {"rows": 1, "delivered": 1, "empty": 0, "stringified": 0, "truncated": 0}}
    elif rule == 7:
        provenance["publisher_credential"] = {**provenance["publisher_credential"], "basis": "not_measured", "state": "unmeasured", "not_measured_reason": "unresolved"}
    else:
        envelope["replay_state"] = "not_replayable"
    _assert_only_rule(envelope, f"FP-{rule}")


def test_cli_failure_unreadable_and_stdin(tmp_path: Path) -> None:
    invalid = _captured_envelope()
    invalid["field_provenance"]["superseded_by"] = {
        **invalid["field_provenance"]["superseded_by"], "state": "measured", "not_measured_reason": None
    }
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(invalid), encoding="utf-8")
    Path("/tmp/hist-obs-unmeasured-measured.json").write_text(json.dumps(invalid), encoding="utf-8")
    failed = subprocess.run([sys.executable, str(SCRIPT), str(path)], text=True, capture_output=True, check=False)
    assert failed.returncode == 1 and "FAIL" in failed.stdout and "FP-2" in failed.stdout
    missing = subprocess.run([sys.executable, str(SCRIPT), str(tmp_path / "missing.json")], text=True, capture_output=True, check=False)
    assert missing.returncode == 2
    passed = subprocess.run([sys.executable, str(SCRIPT), "-"], input=json.dumps(_captured_envelope()), text=True, capture_output=True, check=False)
    assert passed.returncode == 0 and passed.stdout == "PASS -\n"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda envelope: envelope["field_provenance"].pop("observed"),
        lambda envelope: envelope.pop("witness_refs"),
        lambda envelope: (
            envelope["field_provenance"].pop("source_version"),
            envelope["unknown_reasons"].append("source_version"),
        ),
        lambda envelope: envelope.__setitem__("field_provenance", []),
        lambda envelope: envelope["field_provenance"].__setitem__("observed", "not an object"),
    ],
)
def test_malformed_envelopes_return_findings_and_cli_has_no_traceback(
    tmp_path: Path, mutate: Any,
) -> None:
    envelope = _captured_envelope()
    mutate(envelope)
    findings = validate_envelope(envelope)
    assert findings
    path = tmp_path / "malformed.json"
    path.write_text(json.dumps(envelope), encoding="utf-8")
    result = subprocess.run([sys.executable, str(SCRIPT), str(path)], text=True, capture_output=True, check=False)
    assert result.returncode == 1
    assert "FAIL" in result.stdout
    assert "FP-" in result.stdout
    assert "Traceback" not in result.stdout
    assert "Traceback" not in result.stderr
