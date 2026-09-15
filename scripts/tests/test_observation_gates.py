"""Gate tests for the observation store: lock the safety rules into committed tests.

Behaviour under test lives in scripts/observation_gates.py (merged and verified).
No deletion is ever performed here — only checks and dry runs.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import observation_gates as gates  # noqa: E402
from observation_gates import (  # noqa: E402  identity-shared with the module under test
    POLICY_SCHEMA_CONST,
    PayloadTooLargeError,
    blob_path,
    normalized_path,
)
from observation_store import put_blob, put_envelope, put_normalized  # noqa: E402

# Synthetic limits: small enough to reason about, independent of the repo config.
SYNTHETIC_LIMITS: Final[dict[str, int]] = {
    "max_raw_bytes": 8192,
    "max_normalized_bytes": 4096,
    "retention_months": 12,
    "total_budget_bytes": 1_000_000,
}

# Injected clock: a fixed UTC instant so every classification is reproducible.
NOW: Final[datetime] = datetime(2026, 9, 15, tzinfo=timezone.utc)


def _policy_document() -> dict[str, Any]:
    """A synthetic policy config: one dataset with a retention window, one with
    its own raw cap, everything else falling back to the synthetic globals."""
    return {
        "schema": POLICY_SCHEMA_CONST,
        "limits": dict(SYNTHETIC_LIMITS),
        "datasets": {
            "gated-dataset": {"retention_months": 6},
            "tiny-raw-dataset": {"max_raw_bytes": 1024},
        },
    }


def _install_policies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, document: dict[str, Any]
) -> Path:
    """Point the gates module at a temporary config through its own seam — the
    module-level policies_config_path()/global_limits() lookups — and return a
    fresh store root (kept outside the config file's directory so budget totals
    and inventory hashes measure store content only)."""
    config = tmp_path / "observation-policies.json"
    config.write_text(json.dumps(document), encoding="utf-8")
    monkeypatch.setattr(gates, "policies_config_path", lambda: config)
    monkeypatch.setattr(gates, "global_limits", lambda: document["limits"])
    return tmp_path / "store"


def _envelope(dataset_id: str, observation_id: str, observed_at: str) -> dict[str, Any]:
    return {
        "schema": "historical-observation/v2",
        "dataset_id": dataset_id,
        "observation_id": observation_id,
        "observed_at": observed_at,
    }


def _referencing_envelope(
    dataset_id: str,
    observation_id: str,
    observed_at: str,
    source_digest: str,
    observation_digest: str,
) -> dict[str, Any]:
    envelope = _envelope(dataset_id, observation_id, observed_at)
    envelope["source_digest"] = source_digest
    envelope["observation_digest"] = observation_digest
    return envelope


def _inventory_hash(root: Path) -> str:
    """Full inventory of a store tree: every relative path plus every file's
    bytes, hashed in sorted order — any creation, mutation, or removal differs."""
    digest = hashlib.sha256()
    for path in sorted(candidate for candidate in root.rglob("*")):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        if path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()


def test_raw_size_check_at_limit_and_one_over(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """raw_size_check returns the effective limit at exactly the limit and raises
    PayloadTooLargeError one byte over; a dataset whose policy declares its own
    max_raw_bytes uses that value, not the global one."""
    root = _install_policies(tmp_path, monkeypatch, _policy_document())
    # Exactly at the global cap passes and reports the effective limit.
    assert gates.raw_size_check("gated-dataset", SYNTHETIC_LIMITS["max_raw_bytes"], root=root) == 8192
    with pytest.raises(PayloadTooLargeError, match="max_raw_bytes=8192"):
        gates.raw_size_check("gated-dataset", SYNTHETIC_LIMITS["max_raw_bytes"] + 1, root=root)
    # The dataset's own cap (1024) is far below the global one (8192): accepting
    # 1024 and refusing 1025 proves the override, not the global, was enforced.
    assert gates.raw_size_check("tiny-raw-dataset", 1024, root=root) == 1024
    with pytest.raises(PayloadTooLargeError, match="max_raw_bytes=1024"):
        gates.raw_size_check("tiny-raw-dataset", 1025, root=root)


def test_normalized_size_check_at_limit_and_one_over(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """normalized_size_check behaves the same way against the global
    max_normalized_bytes."""
    root = _install_policies(tmp_path, monkeypatch, _policy_document())
    assert gates.normalized_size_check("gated-dataset", 4096, root=root) == 4096
    with pytest.raises(PayloadTooLargeError, match="max_normalized_bytes=4096"):
        gates.normalized_size_check("gated-dataset", 4097, root=root)
    # The schema defines no per-dataset normalized override: tiny-raw-dataset's
    # max_raw_bytes must not leak into the normalized gate.
    assert gates.normalized_size_check("tiny-raw-dataset", 4096, root=root) == 4096


def test_retention_report_classifies_expired_and_within_retention(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """retention_report with an injected now classifies an observation older
    than the dataset's retention_months as expired and a recent one as
    within_retention, and reports days_overdue."""
    root = _install_policies(tmp_path, monkeypatch, _policy_document())
    # gated-dataset retains 6 months: 2026-06-01 is inside, 2025-03-15 expired
    # on 2025-09-15 — exactly 365 days before the injected now.
    put_envelope(
        "gated-dataset", "obs-gated-recent-20260601",
        _envelope("gated-dataset", "obs-gated-recent-20260601", "2026-06-01T00:00:00Z"),
        root=root,
    )
    put_envelope(
        "gated-dataset", "obs-gated-old-20250315",
        _envelope("gated-dataset", "obs-gated-old-20250315", "2025-03-15T00:00:00Z"),
        root=root,
    )
    report = gates.retention_report(root=root, now=NOW)
    assert set(report) == {"counts", "expired", "now"}
    assert report["now"] == "2026-09-15T00:00:00Z"
    assert report["counts"] == {
        "total": 2,
        "within_retention": 1,
        "expired": 1,
        "policy_absent": 0,
        "unreadable": 0,
    }
    assert report["expired"] == [
        {
            "observation_id": "obs-gated-old-20250315",
            "dataset_id": "gated-dataset",
            "observed_at": "2025-03-15T00:00:00Z",
            "days_overdue": 365,
        }
    ]


def test_budget_report_reports_total_budget_headroom_and_overage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """budget_report reports the true on-disk total, the configured budget,
    the headroom, and an overage when the total exceeds a small budget
    injected through the module's own config seam."""
    root = _install_policies(tmp_path, monkeypatch, _policy_document())
    put_blob(b"b" * 100, root=root)
    put_normalized({"budget": 1}, root=root)
    put_envelope(
        "gated-dataset", "obs-gated-20260101",
        _envelope("gated-dataset", "obs-gated-20260101", "2026-01-01T00:00:00Z"),
        root=root,
    )
    on_disk = sum(path.stat().st_size for path in root.rglob("*") if path.is_file())

    tiny = _policy_document()
    tiny["limits"]["total_budget_bytes"] = 50  # far below what is already stored
    _install_policies(tmp_path, monkeypatch, tiny)
    report = gates.budget_report(root=root)
    assert set(report) == {"bytes", "exceeded", "headroom_bytes", "overage_bytes", "total_budget_bytes"}
    assert report["bytes"]["total"] == on_disk
    assert report["bytes"]["total"] == (
        report["bytes"]["blobs"]
        + report["bytes"]["normalized"]
        + report["bytes"]["envelopes"]
        + report["bytes"]["indexes"]
    )
    assert report["total_budget_bytes"] == 50
    assert report["exceeded"] is True
    assert report["overage_bytes"] == on_disk - 50
    assert report["headroom_bytes"] == 50 - on_disk  # negative, not clamped

    generous = _policy_document()
    generous["limits"]["total_budget_bytes"] = on_disk * 10
    _install_policies(tmp_path, monkeypatch, generous)
    roomy = gates.budget_report(root=root)
    assert roomy["exceeded"] is False
    assert roomy["overage_bytes"] == 0
    assert roomy["headroom_bytes"] == on_disk * 10 - on_disk


def test_duplicate_report_names_the_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """duplicate_report returns a structure that names which case applies,
    rather than a bare empty list that reads like 'no data'."""
    root = _install_policies(tmp_path, monkeypatch, _policy_document())
    put_blob(b"unique raw bytes", root=root)
    original = put_envelope(
        "gated-dataset", "obs-gated-20260101",
        _envelope("gated-dataset", "obs-gated-20260101", "2026-01-01T00:00:00Z"),
        root=root,
    )
    clean = gates.duplicate_report(root=root)
    assert clean["case"] == "no_duplicates_found"
    assert clean["duplicates"] == []
    assert clean["explanation"]  # the no-data case is stated, not implied
    assert clean["content_addressed"]["blob_paths"] == 1

    # Byte-identical envelope bytes under a second dataset path: envelopes are
    # identity-addressed, so only a byte-level comparison can catch this.
    twin = root / "envelopes" / "other-dataset" / "2026" / "01" / "obs-gated-20260101.json"
    twin.parent.mkdir(parents=True)
    twin.write_bytes(original.read_bytes())
    dirty = gates.duplicate_report(root=root)
    assert dirty["case"] == "duplicates_found"
    grouped = {path for group in dirty["duplicates"] for path in group["paths"]}
    assert {
        original.relative_to(root).as_posix(),
        twin.relative_to(root).as_posix(),
    } <= grouped


def test_compression_anomalies_flags_out_of_band_ratio_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """compression_anomalies flags a pair whose ratio is outside the
    documented band and leaves one inside the band unflagged."""
    root = _install_policies(tmp_path, monkeypatch, _policy_document())
    # In-band pair: raw 210 bytes, normalized 210 canonical bytes -> ratio 1.0.
    raw_in_band = put_blob(b"q" * 210, root=root)
    normalized_in_band = put_normalized({"pad": "x" * 200}, root=root)
    put_envelope(
        "gated-dataset", "obs-gated-inband-20260101",
        _referencing_envelope(
            "gated-dataset", "obs-gated-inband-20260101", "2026-01-01T00:00:00Z",
            raw_in_band, normalized_in_band,
        ),
        root=root,
    )
    # Out-of-band pair: normalized 210 bytes against raw 50 -> ratio 4.2 > 3.0.
    raw_out_of_band = put_blob(b"r" * 50, root=root)
    normalized_out_of_band = put_normalized({"pad": "y" * 200}, root=root)
    put_envelope(
        "gated-dataset", "obs-gated-outband-20260102",
        _referencing_envelope(
            "gated-dataset", "obs-gated-outband-20260102", "2026-01-02T00:00:00Z",
            raw_out_of_band, normalized_out_of_band,
        ),
        root=root,
    )
    report = gates.compression_anomalies(root=root)
    assert set(report) == {"anomalies", "band", "pairs_compared"}
    assert report["pairs_compared"] == 2
    assert report["band"]["min_ratio"] == gates.MIN_NORMALIZED_TO_RAW_RATIO
    assert report["band"]["max_ratio"] == gates.MAX_NORMALIZED_TO_RAW_RATIO
    assert [entry["observation_id"] for entry in report["anomalies"]] == ["obs-gated-outband-20260102"]
    anomaly = report["anomalies"][0]
    assert anomaly["violation"] == "above_max"
    raw_size = blob_path(raw_out_of_band, root=root).stat().st_size
    normalized_size = normalized_path(normalized_out_of_band, root=root).stat().st_size
    assert anomaly["ratio"] == round(normalized_size / raw_size, 6)


def test_referenced_blob_is_never_proposed_for_removal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Safety case: a blob an expired envelope still references is kept with
    reason referenced_by_envelope; an unreferenced old blob is would_remove;
    and a full inventory hash of the store tree is identical before and after
    the dry run."""
    root = _install_policies(tmp_path, monkeypatch, _policy_document())
    referenced_digest = put_blob(b"blob an expired envelope still cites", root=root)
    projection_digest = put_normalized({"still": "referenced"}, root=root)
    orphan_digest = put_blob(b"old blob nothing references", root=root)
    # observed 2026-01-01 + 6 months retention = expired on 2026-07-01, well
    # before the injected now — the strongest form of the rule: even an EXPIRED
    # envelope's references protect the bytes it cites.
    envelope_path = put_envelope(
        "gated-dataset", "obs-gated-expired-20260101",
        _referencing_envelope(
            "gated-dataset", "obs-gated-expired-20260101", "2026-01-01T00:00:00Z",
            referenced_digest, projection_digest,
        ),
        root=root,
    )

    inventory_before = _inventory_hash(root)
    report = gates.cleanup_dry_run(root=root, now=NOW)
    assert _inventory_hash(root) == inventory_before  # a dry run changes nothing

    assert set(report) == {"counts", "decisions", "not_in_scope", "now"}
    decisions = {decision["path"]: decision for decision in report["decisions"]}
    assert len(decisions) == 4

    referenced_path = blob_path(referenced_digest, root=root).relative_to(root).as_posix()
    assert decisions[referenced_path] == {
        "path": referenced_path,
        "kind": "blob",
        "decision": "keep",
        "reason": "referenced_by_envelope",
        "referring_observations": 1,
    }
    projection_path = normalized_path(projection_digest, root=root).relative_to(root).as_posix()
    assert decisions[projection_path] == {
        "path": projection_path,
        "kind": "normalized",
        "decision": "keep",
        "reason": "referenced_by_envelope",
        "referring_observations": 1,
    }
    orphan_path = blob_path(orphan_digest, root=root).relative_to(root).as_posix()
    assert decisions[orphan_path] == {
        "path": orphan_path,
        "kind": "blob",
        "decision": "would_remove",
        "reason": "unreferenced",
        "referring_observations": 0,
    }
    # The expired envelope itself is classified would_remove ("expired"): the
    # two removals together are a two-phase outcome, never a single pass —
    # envelopes go first, and only a later run may reap the bytes their
    # references kept alive. That phasing is what keeps cited evidence intact.
    envelope_rel = envelope_path.relative_to(root).as_posix()
    assert decisions[envelope_rel] == {
        "path": envelope_rel,
        "kind": "envelope",
        "decision": "would_remove",
        "reason": "expired",
    }
    assert report["counts"]["total_objects"] == 4
    assert report["counts"]["would_remove"] == 2
    assert report["counts"]["keep"] == 2
    assert report["counts"]["keep_by_reason"] == {
        "within_retention": 0,
        "referenced_by_envelope": 2,
        "policy_absent": 0,
        "unreadable": 0,
    }


def test_report_to_json_is_deterministic_and_round_trips(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """report_to_json is byte-identical across two calls with the same inputs
    and round-trips through json.loads."""
    root = _install_policies(tmp_path, monkeypatch, _policy_document())
    put_envelope(
        "gated-dataset", "obs-gated-recent-20260601",
        _envelope("gated-dataset", "obs-gated-recent-20260601", "2026-06-01T00:00:00Z"),
        root=root,
    )
    first = gates.report_to_json(gates.retention_report(root=root, now=NOW))
    second = gates.report_to_json(gates.retention_report(root=root, now=NOW))
    assert first == second  # two independent scans serialise to identical bytes
    report = gates.retention_report(root=root, now=NOW)
    assert json.loads(first) == report
    assert gates.report_to_json(report) == first


def test_verify_store_clean_store_reports_zero_failures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A well-formed store verifies clean: every classification count is an
    explicit zero, no dangling references, and the counts cover every object
    actually on disk rather than an emptiness that reads like 'no data'."""
    root = _install_policies(tmp_path, monkeypatch, _policy_document())
    raw_digest = put_blob(b"clean raw payload", root=root)
    projection_digest = put_normalized({"clean": True}, root=root)
    put_envelope(
        "gated-dataset", "obs-gated-clean-20260101",
        _referencing_envelope(
            "gated-dataset", "obs-gated-clean-20260101", "2026-01-01T00:00:00Z",
            raw_digest, projection_digest,
        ),
        root=root,
    )
    files_on_disk = sum(
        1
        for category in ("blobs", "normalized")
        for path in (root / category).rglob("*")
        if path.is_file()
    )

    report = gates.verify_store(root=root)

    assert files_on_disk == 2  # guards the count assertions against vacuity
    assert set(report) == {"counts", "dangling_references", "failures", "ok"}
    assert report["ok"] is True
    assert report["counts"] == {
        "total_objects": files_on_disk,
        "ok": files_on_disk,
        "corrupt": 0,
        "unreadable": 0,
        "misnamed": 0,
        "envelopes": 1,
        "envelopes_unreadable": 0,
        "dangling_references": 0,
    }
    assert report["failures"] == {"corrupt": [], "unreadable": [], "misnamed": []}
    assert report["dangling_references"] == []


def test_verify_store_flags_tampered_blob_as_corrupt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A blob whose bytes are rewritten after writing is reported corrupt,
    with its path, and the recomputed digest differs from the digest in its
    name."""
    root = _install_policies(tmp_path, monkeypatch, _policy_document())
    raw_digest = put_blob(b"original bytes", root=root)
    tampered = blob_path(raw_digest, root=root)
    tampered.write_bytes(b"tampered bytes")  # same path, different bytes

    report = gates.verify_store(root=root)

    assert report["ok"] is False
    assert report["counts"]["corrupt"] == 1
    failure = report["failures"]["corrupt"][0]
    assert failure["path"] == tampered.relative_to(root).as_posix()
    assert failure["digest"] == raw_digest  # what the filename still claims
    recomputed = "sha256:" + hashlib.sha256(b"tampered bytes").hexdigest()
    assert failure["actual_digest"] == recomputed
    assert failure["actual_digest"] != failure["digest"]


def test_verify_store_reports_misnamed_file_without_crashing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A file under blobs/ whose name is not a valid digest is classified
    misnamed rather than crashing the sweep."""
    root = _install_policies(tmp_path, monkeypatch, _policy_document())
    put_blob(b"properly addressed", root=root)
    stray = root / "blobs" / "sha256" / "ab" / "not-a-digest.raw"
    stray.parent.mkdir(parents=True)
    stray.write_bytes(b"stray bytes")

    report = gates.verify_store(root=root)

    assert report["ok"] is False
    assert report["counts"]["misnamed"] == 1
    assert report["counts"]["ok"] == 1  # the legit blob is still classified
    assert report["failures"]["misnamed"] == [
        {
            "classification": "misnamed",
            "kind": "blob",
            "path": stray.relative_to(root).as_posix(),
            "reason": "path is not digest-derived (expected <first-two-hex>/<64 hex>.raw)",
        }
    ]


def test_verify_store_reports_dangling_source_digest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An envelope whose source_digest has no blob behind it is reported as a
    dangling reference carrying the dataset id and observation id of the
    envelope that cites it."""
    root = _install_policies(tmp_path, monkeypatch, _policy_document())
    projection_digest = put_normalized({"dangling": "source"}, root=root)
    phantom = "sha256:" + "0" * 64  # well-formed digest, no blob behind it
    put_envelope(
        "gated-dataset", "obs-gated-dangling-20260101",
        _referencing_envelope(
            "gated-dataset", "obs-gated-dangling-20260101", "2026-01-01T00:00:00Z",
            phantom, projection_digest,
        ),
        root=root,
    )

    report = gates.verify_store(root=root)

    assert report["ok"] is False
    assert report["counts"]["dangling_references"] == 1
    assert report["dangling_references"] == [
        {
            "dataset_id": "gated-dataset",
            "observation_id": "obs-gated-dangling-20260101",
            "field": "source_digest",
            "digest": phantom,
            "expected_path": blob_path(phantom, root=root).relative_to(root).as_posix(),
        }
    ]


def test_read_verified_returns_intact_bytes_and_raises_on_corruption(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """read_blob_verified returns the bytes for an intact blob and raises the
    integrity exception — naming the digest — for a tampered one;
    read_normalized_verified behaves the same for projections."""
    root = _install_policies(tmp_path, monkeypatch, _policy_document())
    # Derived from ObservationStoreError so existing handlers still catch it.
    assert issubclass(gates.IntegrityError, gates.ObservationStoreError)

    raw_digest = put_blob(b"intact raw payload", root=root)
    assert gates.read_blob_verified(raw_digest, root=root) == b"intact raw payload"
    projection_digest = put_normalized({"intact": True}, root=root)
    assert gates.read_normalized_verified(projection_digest, root=root) == b'{"intact":true}'

    blob_path(raw_digest, root=root).write_bytes(b"rewritten bytes")
    with pytest.raises(gates.IntegrityError, match=raw_digest) as corrupt_blob:
        gates.read_blob_verified(raw_digest, root=root)
    message = str(corrupt_blob.value)
    assert "sha256:" + hashlib.sha256(b"rewritten bytes").hexdigest() in message
    assert raw_digest in message  # expected and actual are both named

    normalized_path(projection_digest, root=root).write_bytes(b"{}")
    with pytest.raises(gates.IntegrityError, match=projection_digest):
        gates.read_normalized_verified(projection_digest, root=root)


def test_verify_store_changes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A full inventory hash of the store tree is identical before and after
    the sweep."""
    root = _install_policies(tmp_path, monkeypatch, _policy_document())
    raw_digest = put_blob(b"bytes the sweep must not touch", root=root)
    projection_digest = put_normalized({"untouched": True}, root=root)
    put_envelope(
        "gated-dataset", "obs-gated-untouched-20260101",
        _referencing_envelope(
            "gated-dataset", "obs-gated-untouched-20260101", "2026-01-01T00:00:00Z",
            raw_digest, projection_digest,
        ),
        root=root,
    )
    # Damage BEFORE the sweep: the strongest form of the contract — the
    # verifier reports corruption it finds without "helpfully" healing it.
    blob_path(raw_digest, root=root).write_bytes(b"already corrupt before the sweep")

    inventory_before = _inventory_hash(root)
    report = gates.verify_store(root=root)
    assert _inventory_hash(root) == inventory_before
    assert report["counts"]["corrupt"] == 1  # found, reported, left as-is


def test_verify_store_ignores_objects_outside_store_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The sweep does not follow or report objects outside the store root."""
    root = _install_policies(tmp_path, monkeypatch, _policy_document())
    put_blob(b"the only governed object", root=root)
    # Decoy: correctly digest-named layout with mismatched bytes, but outside
    # the store root — sweeping it would both over-count and falsely fail.
    outside_hex = "ab" * 32
    outside = tmp_path / "outside-store" / "blobs" / "sha256" / "ab" / f"{outside_hex}.raw"
    outside.parent.mkdir(parents=True)
    outside.write_bytes(b"bytes that would fail verification if swept")

    report = gates.verify_store(root=root)

    assert report["counts"]["total_objects"] == 1
    assert report["ok"] is True  # the decoy cannot fail a store it is not in
    assert "outside-store" not in json.dumps(report)
