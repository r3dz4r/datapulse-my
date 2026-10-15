#!/usr/bin/env python3
"""Exercise the changed-path classifier with a real health merge."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
CLASSIFIER = ROOT / "scripts/classify_change.py"
FIXTURE = Path(__file__).parent / "fixtures/pr1601-health-merge-paths.txt"


def classify(paths: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLASSIFIER)],
        input="\n".join(paths) + "\n",
        text=True,
        capture_output=True,
        check=False,
    )


def health_merge_paths() -> list[str]:
    paths = FIXTURE.read_text(encoding="utf-8").splitlines()
    assert len(paths) == 100
    return paths


def test_real_health_merge_uses_fast_path_deterministically() -> None:
    paths = health_merge_paths()
    first = classify(paths)
    second = classify(paths)
    assert first.returncode == 0, first.stderr
    assert (first.returncode, first.stdout, first.stderr) == (
        second.returncode,
        second.stdout,
        second.stderr,
    )


@pytest.mark.parametrize("source_path", ("scripts/gen_drift.py", ".github/workflows/ci.yml"))
def test_health_merge_with_source_path_uses_full_verification(source_path: str) -> None:
    assert classify([*health_merge_paths(), source_path]).returncode != 0


def test_code_only_change_uses_full_verification() -> None:
    assert classify(["scripts/gen_drift.py", ".github/workflows/ci.yml"]).returncode != 0


def test_mixed_ownership_generated_paths_need_snapshot_pair() -> None:
    assert classify(["health/latest.json", "README.md", "data/pharmaceutical_products.md"]).returncode != 0
    assert classify(
        [
            "health/latest.json",
            "catalog-snapshot.json",
            "changelog.json",
            "README.md",
            "data/pharmaceutical_products.md",
        ]
    ).returncode == 0
