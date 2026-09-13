"""Validate field-level provenance for historical-observation/v2 envelopes.

``validate_envelope`` is total for JSON objects: malformed envelopes produce
findings rather than validator exceptions.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "historical-observation.schema.json"
COUNTER_FIELDS = ("rows", "delivered", "empty", "stringified", "truncated")
COUNTER_MEMBERS = {"declared", "observed", "shape_fingerprint", "normalized_projection"}
UNKNOWN_VOCABULARY = {
    "source_version", "source_content_date", "source_identity", "retrieved_at",
    "shape_fingerprint", "change_from_previous", "previous_observation_id",
    "previous_observation_digest",
}


def _schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _entry_error(rule: str, member: str, detail: str) -> str:
    return f"{rule} {member}: {detail}"


def validate_envelope(envelope: dict) -> list[str]:
    """Return stable field-provenance rule violations for one envelope.

    An envelope carries no value for a member when that top-level value is
    ``null`` or the literal string ``"unknown"``. An empty array is a
    determined value: zero witnesses is a finding, not an absence.
    """
    schema = _schema()
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = [
        f"FP-0 {'/'.join(map(str, error.absolute_path)) or '$'}: {error.message}"
        for error in sorted(validator.iter_errors(envelope), key=lambda item: (list(item.absolute_path), item.message))
    ]
    provenance_value = envelope.get("field_provenance")
    if not isinstance(provenance_value, dict):
        errors.append(_entry_error("FP-1", "field_provenance", "must be an object"))
        return errors

    members = set(schema["properties"]) - {"field_provenance"}
    provenance: dict[str, Any] = provenance_value
    findings: list[str] = errors
    if set(provenance) != members:
        findings.append(_entry_error("FP-1", "field_provenance", "keys do not equal envelope member set"))

    for member in sorted(members):
        entry = provenance.get(member)
        if not isinstance(entry, dict):
            if entry is not None:
                findings.append(_entry_error("FP-1", member, "provenance entry must be an object"))
            continue
        if member not in envelope:
            continue
        absent = envelope[member] is None or envelope[member] == "unknown"
        state = entry.get("state")
        reason = entry.get("not_measured_reason")
        if absent and state == "measured":
            findings.append(_entry_error("FP-2", member, "value is null or unknown but state is measured"))
        if not absent and state is not None and state != "measured":
            findings.append(_entry_error("FP-3", member, "value is determined but state is not measured"))
        if reason == "does_not_apply" and state != "not_applicable":
            findings.append(_entry_error("FP-4", member, "does_not_apply requires state not_applicable"))
        if reason not in (None, "does_not_apply") and state != "unmeasured":
            findings.append(_entry_error("FP-4", member, "a measurement reason other than does_not_apply requires state unmeasured"))

    raw_unknown_reasons = envelope.get("unknown_reasons")
    unknown_reasons = (
        set(raw_unknown_reasons)
        if isinstance(raw_unknown_reasons, list) and all(isinstance(member, str) for member in raw_unknown_reasons)
        else set()
    )
    for member in sorted(unknown_reasons):
        entry = provenance.get(member)
        if not isinstance(entry, dict):
            continue
        if entry.get("state") != "unmeasured" or entry.get("basis") != "unknown":
            findings.append(_entry_error("FP-5", member, "unknown_reasons requires state unmeasured and basis unknown"))
    for member in sorted(UNKNOWN_VOCABULARY):
        entry = provenance.get(member)
        if not isinstance(entry, dict):
            continue
        if entry.get("basis") == "unknown" and member not in unknown_reasons:
            findings.append(_entry_error("FP-5", member, "basis unknown requires an unknown_reasons entry"))

    rows_values: set[int] = set()
    for member in sorted(members):
        entry = provenance.get(member)
        if not isinstance(entry, dict):
            continue
        counters = entry.get("counters")
        if not isinstance(counters, dict) or any(field not in counters for field in COUNTER_FIELDS):
            continue
        values = [counters[field] for field in COUNTER_FIELDS]
        all_null = all(value is None for value in values)
        all_set = all(value is not None for value in values)
        if not (all_null or all_set):
            findings.append(_entry_error("FP-6", member, "counters must be null together or non-null together"))
            continue
        if all_null:
            continue
        if not all(isinstance(value, int) and not isinstance(value, bool) for value in values):
            continue
        if member not in COUNTER_MEMBERS:
            findings.append(_entry_error("FP-6", member, "non-null counters are not permitted for this member"))
        rows, delivered, empty, stringified, truncated = values
        rows_values.add(rows)
        if delivered > rows or empty > rows or stringified > delivered or truncated > delivered:
            findings.append(_entry_error("FP-6", member, "counter bounds are inconsistent"))
        if rows == 0 and any(value != 0 for value in (delivered, empty, stringified, truncated)):
            findings.append(_entry_error("FP-6", member, "zero rows requires all other counters to be zero"))
        if rows > 0 and delivered == 0 and not (
            entry.get("state") == "unmeasured"
            and entry.get("not_measured_reason") == "source_did_not_deliver"
        ):
            findings.append(_entry_error("FP-6", member, "zero delivered records requires unmeasured/source_did_not_deliver"))
    if len(rows_values) > 1:
        findings.append(_entry_error("FP-6", "counters", "rows must be identical across entries carrying counters"))

    for member in ("publisher_credential", "verifier_credential"):
        entry = provenance.get(member)
        if not isinstance(entry, dict):
            continue
        if not (
            entry.get("state") == "not_applicable" and entry.get("basis") == "not_applicable"
            and entry.get("derived") is False and entry.get("not_measured_reason") == "does_not_apply"
        ):
            findings.append(_entry_error("FP-7", member, "reserved null credential requires not_applicable provenance"))

    source_entry = provenance.get("source_digest")
    capture_absent = envelope.get("capture_status") != "captured" or envelope.get("replay_state") in {"metadata_only", "not_replayable"}
    if capture_absent and isinstance(source_entry, dict) and not (
        source_entry.get("state") == "unmeasured"
        and source_entry.get("not_measured_reason") in {"source_did_not_deliver", "capture_not_attempted", "capture_failed"}
    ):
        findings.append(_entry_error("FP-8", "source_digest", "absence required by capture or replay state needs an explained unmeasured state"))
    previous_entry = provenance.get("previous_observation_digest")
    if envelope.get("previous_observation_id") is None and isinstance(previous_entry, dict):
        if envelope.get("change_from_previous") == "first_observation":
            valid = previous_entry.get("state") == "not_applicable" and previous_entry.get("not_measured_reason") == "does_not_apply"
        else:
            valid = (
                previous_entry.get("state") == "unmeasured"
                and previous_entry.get("basis") == "unknown"
                and previous_entry.get("not_measured_reason") == "unresolved"
            )
        if not valid:
            findings.append(_entry_error("FP-8", "previous_observation_digest", "absence needs first-observation applicability or unknown/unresolved provenance"))
    return findings


def main(argv: list[str]) -> int:
    """Run the validator CLI: 0 pass, 1 validation failure, 2 usage/read error."""
    if not argv:
        print("usage: validate_historical_observation.py PATH [PATH ...]", file=sys.stderr)
        return 2
    failed = False
    for path in argv:
        try:
            raw = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
            envelope = json.loads(raw)
        except (OSError, json.JSONDecodeError) as error:
            print(f"ERROR {path}: {error}", file=sys.stderr)
            return 2
        rules = validate_envelope(envelope)
        if rules:
            failed = True
            print(f"FAIL {path}")
            for rule in rules:
                print(f"  {rule}")
        else:
            print(f"PASS {path}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
