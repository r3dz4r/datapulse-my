"""Custodian registry and manifest referential-integrity tests."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_manifest_custodians_are_complete_and_resolved() -> None:
    manifest = json.loads((ROOT / "datapulse.json").read_text(encoding="utf-8"))
    registry = json.loads((ROOT / "custodians.json").read_text(encoding="utf-8"))
    ids = {row["custodian"] for row in manifest["datasets"]}

    assert all(isinstance(row["custodian"], str) and row["custodian"] for row in manifest["datasets"])
    assert ids == set(registry["custodians"])


def test_registry_marker_and_known_aliases_are_stable() -> None:
    manifest = json.loads((ROOT / "datapulse.json").read_text(encoding="utf-8"))
    registry = json.loads((ROOT / "custodians.json").read_text(encoding="utf-8"))
    by_steward = {row["steward"]: row["custodian"] for row in manifest["datasets"]}

    assert registry["schema"] == "datapulse/v1/custodians"
    assert by_steward["BNM"] == by_steward["Bank Negara Malaysia"] == "bnm"
    assert by_steward["DOSM Malaysia"] == by_steward["dosm"] == "dosm"
    assert by_steward["MET Malaysia"] == by_steward["Malaysian Meteorological Department"] == "met"
    assert by_steward["Keretapi Tanah Melayu Berhad"] == by_steward["Keretapi Tanah Melayu Berhad (KTMB)"] == "ktmb"
