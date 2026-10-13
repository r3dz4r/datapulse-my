"""Focused tests for the Pages attestation selection boundary."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "select_served_attestations.py"
METADATA = ("index.json", "binding.json", "scores.json", "health.json", "health.json.gz")


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
    assert counts["attestations_retained"] <= counts["attestations_before"]
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


def test_six_day_window_is_inclusive_and_seven_day_window_is_exclusive(root: Path) -> None:
    chain_path = root / "attestations/chain-index.json"
    chain = json.loads(chain_path.read_text())
    chain["heads"].update({
        "six-days": "attestations/2026-10-04/chain_head.json",
        "seven-days": "attestations/2026-10-03/chain_head.json",
    })
    chain["envelopes"].update({"six-days": {}, "seven-days": {}})
    chain_path.write_text(json.dumps(chain))
    for day in ("2026-10-04", "2026-10-03"):
        for name in ("chain_head", "index", "binding", "scores", "uncited"):
            write_json(root / f"attestations/{day}/{name}.json", {})

    site = root / "_site"
    site.mkdir()
    shutil.copytree(root / "attestations", site / "attestations")
    result = run_selector(root, "--apply", "--site", str(site))

    assert result.returncode == 0, result.stderr
    assert (site / "attestations/2026-10-04/uncited.json").is_file()
    assert not (site / "attestations/2026-10-03/uncited.json").exists()


def test_many_daily_revisions_keep_metadata_and_resolve_served_references(tmp_path: Path) -> None:
    # 120 accepted revisions, 439 dataset files each: the old policy exceeds 18,000.
    heads = {}
    envelopes = {}
    directories = []
    newest = {}
    for number in range(120):
        day = (date(2026, 10, 7) + timedelta(days=number % 7)).isoformat()
        digest = f"{120 - number:064x}"  # Hash order opposes acceptance order.
        directory = f"attestations/{day}/revisions/{digest}"
        directories.append(directory)
        newest[day] = directory
        heads[digest] = f"{directory}/chain_head.json"
        envelopes[digest] = {"sequence": number // 7 + 1,
                             "index_ref": f"{directory}/index.json",
                             "binding_ref": f"{directory}/binding.json",
                             "scores_ref": f"{directory}/scores.json"}
        refs = {f"dataset{i}": f"{directory}/dataset{i}.json" for i in range(439)}
        for reference in refs.values():
            write_json(tmp_path / reference, {})
        for name in ("chain_head.json", *METADATA):
            write_json(tmp_path / directory / name, {})
        write_json(tmp_path / directory / "index.json", {"attestations": refs})
        write_json(tmp_path / directory / "binding.json", {
            "rekor": {"reference_ref": "attestations/rekor/reference.json"},
            "payload": {"correction": {"health_snapshot_ref": f"{directories[0]}/health.json"}},
        })
    write_json(tmp_path / "attestations/rekor/reference.json", {})
    # Deliberately scramble map order; sequence, rather than iteration order, decides newest.
    write_json(tmp_path / "attestations/chain-index.json", {
        "heads": dict(reversed(list(heads.items()))), "envelopes": envelopes,
    })
    current = newest["2026-10-13"]
    write_json(tmp_path / "attestations/latest/index.json", {
        "date": "2026-10-13", "chain_head_ref": f"{current}/chain_head.json",
        "binding_ref": f"{current}/binding.json",
        "attestations": {"dataset0": f"{current}/dataset0.json"},
    })
    site = tmp_path / "_site"
    site.mkdir()
    result = run_selector(tmp_path, "--apply", "--site", str(site))
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["site_total"] < 18000
    inventory = json.loads((site / "attestations/served-retention.json").read_text())
    assert f"{directories[0]}/dataset0.json" in inventory["not_served"]
    assert f"{current}/dataset0.json" not in inventory["not_served"]
    for directory in directories:
        for name in ("chain_head.json", *METADATA):
            assert (site / directory / name).is_file()
        assert (site / directory / "dataset438.json").is_file() == (directory in newest.values())
    # All chain-index, latest-index and binding references resolve after selection.
    def references(value: object) -> list[str]:
        if isinstance(value, dict):
            return [ref for item in value.values() for ref in references(item)]
        if isinstance(value, list):
            return [ref for item in value for ref in references(item)]
        return [value] if isinstance(value, str) and value.startswith("attestations/") else []

    for path in [site / "attestations/chain-index.json", site / "attestations/latest/index.json",
                 *site.glob("attestations/**/binding.json")]:
        for reference in references(json.loads(path.read_text())):
            assert (site / reference).is_file(), reference
    before = {p.relative_to(site): p.read_bytes() for p in site.rglob("*") if p.is_file()}
    second = run_selector(tmp_path, "--apply", "--site", str(site))
    assert second.returncode == 0, second.stderr
    assert before == {p.relative_to(site): p.read_bytes() for p in site.rglob("*") if p.is_file()}


@pytest.mark.parametrize("depth", ["0", "-1"])
def test_full_revision_depth_must_be_positive(root: Path, depth: str) -> None:
    result = run_selector(root, "--plan", "--full-revisions-per-day", depth)
    assert result.returncode != 0
    assert "--full-revisions-per-day must be positive" in result.stderr


def test_missing_full_revision_evidence_fails_closed(root: Path) -> None:
    write_json(root / "attestations/2026-10-10/index.json", {
        "attestations": {"broken": "attestations/2026-10-10/broken.json"},
    })
    result = run_selector(root, "--plan")
    assert result.returncode != 0
    assert "published attestation reference is missing" in result.stderr


@pytest.mark.parametrize("depth", [1, 2])
def test_full_revision_depth_uses_sequence_and_keeps_pinned_old_evidence(
    root: Path, depth: int,
) -> None:
    chain_path = root / "attestations/chain-index.json"
    chain = json.loads(chain_path.read_text())
    directories = []
    for sequence in (1, 3, 2):
        digest = f"{4 - sequence:064x}"
        directory = f"attestations/2026-10-09/revisions/{digest}"
        directories.append((sequence, directory))
        chain["heads"][digest] = f"{directory}/chain_head.json"
        chain["envelopes"][digest] = {"sequence": sequence}
        for name in ("chain_head.json", *METADATA, "evidence.json", "pinned.json"):
            write_json(root / directory / name, {})
        write_json(root / directory / "index.json", {
            "attestations": {"dataset": f"{directory}/evidence.json",
                             "pinned": f"{directory}/pinned.json"},
        })
    write_json(chain_path, chain)
    (root / "docs/pinned.md").write_text(f"{directories[0][1]}/pinned.json")
    site = root / "_site"
    site.mkdir()
    shutil.copy2(root / "docs/pinned.md", site / "pinned.md")
    result = run_selector(root, "--apply", "--site", str(site),
                          "--full-revisions-per-day", str(depth))
    assert result.returncode == 0, result.stderr
    for sequence, directory in directories:
        assert (site / directory / "evidence.json").exists() == (sequence > 3 - depth)
        for name in METADATA:
            assert (site / directory / name).is_file()
    pinned = f"{directories[0][1]}/pinned.json"
    assert (site / pinned).is_file()
    assert pinned not in json.loads((site / "attestations/served-retention.json").read_text())["not_served"]


def test_cited_binding_references_are_retained_even_outside_accepted_sets(root: Path) -> None:
    write_json(root / "attestations/2026-09-01/binding.json", {
        "rekor": {"reference_ref": "attestations/rekor/cited.json"},
    })
    write_json(root / "attestations/rekor/cited.json", {})
    (root / "docs/index.html").write_text("attestations/2026-09-01/binding.json")
    result = run_selector(root, "--plan")
    assert result.returncode == 0, result.stderr
    (root / "attestations/rekor/cited.json").unlink()
    result = run_selector(root, "--plan")
    assert result.returncode != 0
    assert "published attestation reference is missing" in result.stderr
