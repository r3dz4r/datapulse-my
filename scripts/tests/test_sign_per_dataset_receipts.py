"""Tests for non-blocking batch receipt signing."""

from __future__ import annotations

from pathlib import Path

from scripts.sign_per_dataset_receipts import sign_receipts


def test_missing_signer_is_non_blocking_and_removes_stale_bundles(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    (data / "fuelprice.receipt.statement.json").write_text("{}\n", encoding="utf-8")
    stale = data / "fuelprice.receipt.sigstore.json"
    stale.write_text("stale", encoding="utf-8")
    result = tmp_path / "result"

    assert sign_receipts(data_dir=data, cosign="missing-cosign", result_out=result) is False
    assert result.read_text(encoding="utf-8") == "unsigned\n"
    assert not stale.exists()
