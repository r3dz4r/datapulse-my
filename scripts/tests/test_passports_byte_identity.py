"""Byte-identity proof for build-time Dataset Passport generation.

data/passports/ is no longer tracked: the Pages build regenerates it. The served
bytes are only trustworthy if the generator reproduces what the committed tree used
to carry. The fixture pins the canonical inputs of commit ef25ca9baa (#2933), where
the generator reproduced all 441 committed passports exactly, sliced to four
datasets of different shapes:

- births: smallest passport, one catalogue edge, no record evidence
- dosm_gdp_annual_real_supply_granular: largest passport, 119 catalogue edges
- fuelprice: record-evidence reference and a declared privacy classification
- gtfs_static_ktmb: no JSON envelope, so source_envelope is unavailable

expected/ holds the committed bytes from that commit, unmodified.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from scripts.gen_dataset_passports import generate


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "passport_byte_identity"
SCHEMAS = ("datapulse.schema.json", "health.schema.json", "passport.schema.json")
EXPECTED = sorted(path.name for path in (FIXTURE / "expected").glob("*.json"))


def _generated(tmp_path: Path) -> Path:
    root = tmp_path / "root"
    shutil.copytree(FIXTURE / "inputs", root)
    for schema in SCHEMAS:
        shutil.copyfile(ROOT / schema, root / schema)
    output = tmp_path / "passports"
    assert generate(root, output) == len(EXPECTED)
    return output


def test_fixture_covers_at_least_three_passports() -> None:
    assert len(EXPECTED) >= 3


@pytest.mark.parametrize("name", EXPECTED)
def test_generator_reproduces_committed_passport_bytes(tmp_path: Path, name: str) -> None:
    generated = (_generated(tmp_path) / name).read_bytes()
    expected = (FIXTURE / "expected" / name).read_bytes()
    assert generated == expected, f"{name}: build output differs from the committed passport bytes"


def test_byte_identity_detects_a_changed_input(tmp_path: Path) -> None:
    root = tmp_path / "root"
    shutil.copytree(FIXTURE / "inputs", root)
    for schema in SCHEMAS:
        shutil.copyfile(ROOT / schema, root / schema)
    (root / "data" / "json" / "births.json").unlink()
    generate(root, tmp_path / "passports")
    assert (tmp_path / "passports" / "births.json").read_bytes() != (FIXTURE / "expected" / "births.json").read_bytes()
