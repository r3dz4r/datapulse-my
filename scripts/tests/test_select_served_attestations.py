"""Focused tests for the Pages attestation selection boundary."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "select_served_attestations.py"


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


@pytest.fixture
def root(tmp_path: Path) -> Path:
    plane = tmp_path / "attestations"
    current = "attestations/2026-10-10"
    old = "attestations/2026-09-01"
    write_json(plane / "chain-index.json", {
        "heads": {"digest": f"{current}/chain_head.json"},
        "envelopes": {"digest": {}},
    })
    write_json(plane / "latest/index.json", {
        "date": "2026-10-10",
        "chain_head_ref": f"{current}/chain_head.json",
        "binding_ref": f"{current}/binding.json",
        "attestations": {"dataset": f"{current}/dataset.json"},
    })
    for name in ("chain_head.json", "index.json", "scores.json", "dataset.json"):
        write_json(tmp_path / current / name, {})
    write_json(tmp_path / current / "binding.json", {
        "rekor": {"entry": "attestations/rekor/entry.json"},
        "payload": {"correction": {"health_snapshot_ref": f"{old}/correction.json"}},
    })
    write_json(plane / "rekor/entry.json", {})
    for name in ("cited.json", "correction.json", "unreferenced.json"):
        write_json(tmp_path / old / name, {})
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/index.html").write_text(f'"{old}/cited.json"')
    write_json(tmp_path / ".attestations/chain_head.json", {})
    return tmp_path


def run_selector(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args, "--root", str(root)],
        text=True, capture_output=True, check=False,
    )


@pytest.mark.parametrize("preassembled", [False, True])
def test_apply_keeps_references_and_drops_unreferenced_old_file(
    root: Path, preassembled: bool,
) -> None:
    site = root / "_site"
    site.mkdir()
    shutil.copy2(root / "docs/index.html", site / "index.html")
    if preassembled:
        shutil.copytree(root / "attestations", site / "attestations")
        shutil.copytree(root / ".attestations", site / ".attestations")

    result = run_selector(root, "--apply", "--site", str(site))

    assert result.returncode == 0, result.stderr
    counts = json.loads(result.stdout)
    assert counts["attestations_retained"] < counts["attestations_before"]
    for reference in (
        "attestations/2026-09-01/cited.json",
        "attestations/2026-09-01/correction.json",
        "attestations/rekor/entry.json",
        "attestations/2026-10-10/dataset.json",
    ):
        assert (site / reference).is_file()
    assert not (site / "attestations/2026-09-01/unreferenced.json").exists()
    assert (site / ".attestations/chain_head.json").is_file()


@pytest.mark.parametrize("reference", [
    "attestations/2026-10-10/../bad.json",
    "attestations/2026-10-10/bad.txt",
    "outside/bad.json",
])
def test_unsafe_binding_reference_raises(root: Path, reference: str) -> None:
    write_json(root / "attestations/2026-10-10/binding.json", {
        "rekor": {"entry": reference},
    })

    result = run_selector(root, "--plan")

    assert result.returncode != 0
    assert "unsafe attestation reference" in result.stderr


def test_plan_exits_nonzero_over_file_limit(root: Path) -> None:
    result = run_selector(root, "--plan", "--max-files", "1")

    assert result.returncode != 0
    counts = json.loads(result.stdout)
    assert counts["site_total"] > counts["max_files"]
    assert "Pages artifact has" in result.stderr
