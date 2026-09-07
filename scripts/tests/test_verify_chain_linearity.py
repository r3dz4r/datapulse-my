from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.verify_chain_linearity import (
    ChainLinearityError,
    verify_chain_linearity,
)


def _write_head(path: Path, chain_head: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"chain_head": chain_head}), encoding="utf-8"
    )


def test_latest_head_mirrors_newest_dated_head(tmp_path: Path) -> None:
    root = tmp_path / "fixture"
    older = "1" * 64
    newest = "2" * 64
    _write_head(root / "attestations/2099-01-01/chain_head.json", older)
    _write_head(root / "attestations/2099-01-02/chain_head.json", newest)
    _write_head(root / "attestations/latest/chain_head.json", newest)

    report = verify_chain_linearity(root)

    assert report.latest_date == "2099-01-02"
    assert report.chain_head == newest


def test_rejects_latest_head_that_points_to_an_older_dated_day(tmp_path: Path) -> None:
    root = tmp_path / "fixture"
    older = "1" * 64
    newest = "2" * 64
    _write_head(root / "attestations/2099-01-01/chain_head.json", older)
    _write_head(root / "attestations/2099-01-02/chain_head.json", newest)
    _write_head(root / "attestations/latest/chain_head.json", older)

    with pytest.raises(ChainLinearityError, match="does not match newest dated head"):
        verify_chain_linearity(root)
