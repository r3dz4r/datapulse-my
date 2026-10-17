"""Keep parity test fixtures from writing through to committed data."""

from __future__ import annotations

import hashlib
import importlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
COMMITTED_INPUTS = (
    ROOT / "datapulse.json",
    ROOT / "health/latest.json",
    ROOT / "mcp.json",
    ROOT / "docs/index.html",
)


def _hashes() -> dict[Path, str]:
    return {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in COMMITTED_INPUTS}


def test_parity_failure_fixtures_leave_committed_inputs_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = _hashes()
    write_text = Path.write_text

    def guarded_write(path: Path, *args: object, **kwargs: object) -> int:
        assert path.resolve() not in COMMITTED_INPUTS, f"test wrote committed input: {path}"
        return write_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", guarded_write)
    try:
        parity_tests = importlib.import_module("scripts.tests.test_verify_local_public_parity")
        parity_tests.test_wrong_dataset_count_fails(tmp_path / "dataset")
        parity_tests.test_wrong_tool_count_fails(tmp_path / "tools")
        parity_tests.test_taxonomy_violation_fails(tmp_path / "taxonomy")
    finally:
        assert _hashes() == before
