"""Tests for non-blocking, partial-failure-tolerant batch receipt signing.

The cosign call boundary (``_run_cosign``) is replaced in every test; no test
shells out to a real cosign or contacts Sigstore.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts import sign_per_dataset_receipts as signer
from scripts.sign_per_dataset_receipts import SigningResult, demote_unverified, sign_receipts


IDS = ("arrivals", "deaths", "fuelprice")


def _data(tmp_path: Path, ids: tuple[str, ...] = IDS) -> Path:
    data = tmp_path / "data"
    data.mkdir()
    for identifier in ids:
        (data / f"{identifier}.receipt.statement.json").write_text("{}\n", encoding="utf-8")
        (data / f"{identifier}.receipt.evidence.json").write_text("{}\n", encoding="utf-8")
    return data


def _fake_cosign_path(tmp_path: Path) -> str:
    """An executable that satisfies shutil.which but is never executed."""
    path = tmp_path / "bin" / "cosign"
    path.parent.mkdir()
    path.write_text("#!/bin/sh\nexit 97\n", encoding="utf-8")
    path.chmod(0o755)
    return str(path)


@pytest.fixture
def signing_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[str, list[list[str]], set[str]]:
    """Install a fake cosign boundary; returns (cosign path, call log, ids that fail)."""
    monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_URL", "https://token.example.test")
    monkeypatch.setattr(signer, "RETRY_BACKOFF_SECONDS", 0.0)
    calls: list[list[str]] = []
    failing: set[str] = set()

    def fake_run_cosign(argv: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        bundle = Path(argv[argv.index("--bundle") + 1])
        identifier = bundle.name.removesuffix(".receipt.sigstore.json")
        if identifier in failing:
            return subprocess.CompletedProcess(argv, 1, "", "error: rate limited by tlog")
        bundle.write_text(json.dumps({"signed": identifier}), encoding="utf-8")
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(signer, "_run_cosign", fake_run_cosign)
    return _fake_cosign_path(tmp_path), calls, failing


def _manifest(data: Path) -> dict:
    return json.loads((data / "receipts-manifest.json").read_text(encoding="utf-8"))


def test_one_failing_dataset_leaves_successful_bundles_intact(tmp_path: Path, signing_env) -> None:
    cosign, calls, failing = signing_env
    data = _data(tmp_path)
    failing.add("deaths")
    result = tmp_path / "result"

    outcome = sign_receipts(data_dir=data, cosign=cosign, result_out=result)

    assert outcome is SigningResult.PARTIAL
    assert result.read_text(encoding="utf-8") == "partial\n"
    assert json.loads((data / "arrivals.receipt.sigstore.json").read_text()) == {"signed": "arrivals"}
    assert json.loads((data / "fuelprice.receipt.sigstore.json").read_text()) == {"signed": "fuelprice"}
    assert not (data / "deaths.receipt.sigstore.json").exists()
    assert not (data / ".per-dataset-receipt-staging").exists()
    manifest = _manifest(data)
    assert manifest["schema"] == "datapulse/v1/receipt-coverage"
    assert manifest["total"] == 3
    assert manifest["signed_count"] == 2 == len(manifest["signed"])
    assert manifest["signed"] == ["arrivals", "fuelprice"]
    assert manifest["unsigned"] == [{"id": "deaths", "reason": "signing_failed"}]
    assert manifest["generated_at"].endswith("Z")
    # The failing dataset was retried exactly to the bound, the others signed once.
    attempts = [Path(argv[argv.index("--bundle") + 1]).name for argv in calls]
    assert attempts.count("deaths.receipt.sigstore.json") == signer.MAX_ATTEMPTS == 2
    assert attempts.count("arrivals.receipt.sigstore.json") == 1


def test_transient_failure_recovers_within_the_retry_bound(tmp_path: Path, signing_env, monkeypatch) -> None:
    cosign, _, _ = signing_env
    data = _data(tmp_path)
    inner = signer._run_cosign
    failed_once: set[str] = set()

    def flaky(argv: list[str]) -> subprocess.CompletedProcess[str]:
        if "deaths.receipt.sigstore.json" in argv[argv.index("--bundle") + 1] and "deaths" not in failed_once:
            failed_once.add("deaths")
            return subprocess.CompletedProcess(argv, 1, "", "transient")
        return inner(argv)

    monkeypatch.setattr(signer, "_run_cosign", flaky)
    result = tmp_path / "result"

    assert sign_receipts(data_dir=data, cosign=cosign, result_out=result) is SigningResult.SIGNED
    assert result.read_text(encoding="utf-8") == "signed\n"
    manifest = _manifest(data)
    assert manifest["signed_count"] == manifest["total"] == 3
    assert manifest["unsigned"] == []


def test_manifest_records_every_dataset_when_nothing_signs(tmp_path: Path, signing_env) -> None:
    cosign, _, failing = signing_env
    data = _data(tmp_path)
    failing.update(IDS)
    result = tmp_path / "result"

    assert sign_receipts(data_dir=data, cosign=cosign, result_out=result) is SigningResult.UNSIGNED
    assert result.read_text(encoding="utf-8") == "unsigned\n"
    manifest = _manifest(data)
    assert manifest["total"] == 3
    assert manifest["signed_count"] == 0
    assert manifest["signed"] == []
    assert [item["id"] for item in manifest["unsigned"]] == sorted(IDS)
    assert {item["reason"] for item in manifest["unsigned"]} == {"signing_failed"}


def test_result_file_distinguishes_all_three_states(tmp_path: Path, signing_env) -> None:
    cosign, _, failing = signing_env
    seen: dict[str, str] = {}
    for label, fail in (("all", set()), ("some", {"deaths"}), ("none", set(IDS))):
        failing.clear()
        failing.update(fail)
        root = tmp_path / label
        root.mkdir()
        data = _data(root)
        result = root / "result"
        outcome = sign_receipts(data_dir=data, cosign=cosign, result_out=result)
        assert result.read_text(encoding="utf-8") == f"{outcome.value}\n"
        seen[label] = outcome.value
    assert seen == {"all": "signed", "some": "partial", "none": "unsigned"}


def test_missing_signer_is_non_blocking_and_keeps_bundles_it_did_not_create(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(signer, "_run_cosign", lambda argv: pytest.fail("cosign must not be invoked"))
    data = _data(tmp_path, ("fuelprice",))
    prior = data / "fuelprice.receipt.sigstore.json"
    prior.write_text("prior", encoding="utf-8")
    result = tmp_path / "result"

    assert sign_receipts(data_dir=data, cosign="missing-cosign", result_out=result) is SigningResult.UNSIGNED
    assert result.read_text(encoding="utf-8") == "unsigned\n"
    # This run did not create the bundle, so it must not delete it; the
    # manifest still records the dataset as unsigned, so it is not published.
    assert prior.read_text(encoding="utf-8") == "prior"
    assert _manifest(data)["unsigned"] == [{"id": "fuelprice", "reason": "signer_unavailable"}]


def test_missing_oidc_records_a_closed_vocabulary_reason(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("ACTIONS_ID_TOKEN_REQUEST_URL", raising=False)
    monkeypatch.setattr(signer, "_run_cosign", lambda argv: pytest.fail("cosign must not be invoked"))
    data = _data(tmp_path, ("fuelprice",))

    assert sign_receipts(data_dir=data, cosign=_fake_cosign_path(tmp_path)) is SigningResult.UNSIGNED
    assert _manifest(data)["unsigned"] == [{"id": "fuelprice", "reason": "oidc_unavailable"}]


def test_manifest_is_written_when_there_are_no_statements(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    result = tmp_path / "result"

    assert sign_receipts(data_dir=data, cosign="missing-cosign", result_out=result) is SigningResult.UNSIGNED
    manifest = _manifest(data)
    assert (manifest["total"], manifest["signed_count"], manifest["signed"], manifest["unsigned"]) == (0, 0, [], [])
    assert result.read_text(encoding="utf-8") == "unsigned\n"


def test_missing_evidence_is_recorded_without_exception_text(tmp_path: Path, signing_env) -> None:
    cosign, _, _ = signing_env
    data = _data(tmp_path)
    (data / "arrivals.receipt.evidence.json").unlink()

    assert sign_receipts(data_dir=data, cosign=cosign) is SigningResult.PARTIAL
    raw = (data / "receipts-manifest.json").read_text(encoding="utf-8")
    assert json.loads(raw)["unsigned"] == [{"id": "arrivals", "reason": "evidence_missing"}]
    assert "rate limited" not in raw and "Error" not in raw and str(data) not in raw


def test_unsigned_reasons_stay_in_the_closed_vocabulary(tmp_path: Path, signing_env) -> None:
    cosign, _, failing = signing_env
    data = _data(tmp_path)
    failing.add("fuelprice")
    sign_receipts(data_dir=data, cosign=cosign)
    assert {item["reason"] for item in _manifest(data)["unsigned"]} <= signer.UNSIGNED_REASONS
    with pytest.raises(ValueError):
        signer.SigningError("cosign exploded: secret text")


def test_demote_withholds_unverified_bundle_and_updates_counts(tmp_path: Path, signing_env) -> None:
    cosign, _, _ = signing_env
    data = _data(tmp_path)
    assert sign_receipts(data_dir=data, cosign=cosign) is SigningResult.SIGNED
    result = tmp_path / "result"

    assert demote_unverified(data_dir=data, identifiers=["deaths"], result_out=result) is SigningResult.PARTIAL
    assert result.read_text(encoding="utf-8") == "partial\n"
    assert not (data / "deaths.receipt.sigstore.json").exists()
    assert (data / "arrivals.receipt.sigstore.json").exists()
    manifest = _manifest(data)
    assert manifest["signed"] == ["arrivals", "fuelprice"]
    assert manifest["signed_count"] == 2 and manifest["total"] == 3
    assert manifest["unsigned"] == [{"id": "deaths", "reason": "verification_failed"}]


def test_demote_refuses_a_dataset_not_listed_as_signed(tmp_path: Path, signing_env) -> None:
    cosign, _, failing = signing_env
    data = _data(tmp_path)
    failing.add("deaths")
    sign_receipts(data_dir=data, cosign=cosign)
    with pytest.raises(ValueError):
        demote_unverified(data_dir=data, identifiers=["deaths"])
