from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "scripts/derive_per_dataset.sh"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "scripts").mkdir()
    return tmp_path


def manifest(repo: Path, *ids: str) -> None:
    (repo / "datapulse.json").write_text(json.dumps({"datasets": [{"id": item} for item in ids]}))


def run_helper(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["bash", str(HELPER)], cwd=repo, text=True, capture_output=True)


def test_manifest_selects_matching_generators(repo: Path) -> None:
    manifest(repo, "new_dataset", "other")
    (repo / "scripts/gen_new_dataset.py").write_text("from pathlib import Path\nPath('order').write_text('dataset\\n')\n")
    (repo / "scripts/gen_unlisted.py").write_text("raise SystemExit(9)\n")
    result = run_helper(repo)
    assert result.returncode == 0, result.stderr
    assert (repo / "order").read_text() == "dataset\n"


def test_failure_names_dataset_and_generator(repo: Path) -> None:
    manifest(repo, "broken")
    (repo / "scripts/gen_broken.py").write_text("raise SystemExit(7)\n")
    result = run_helper(repo)
    assert result.returncode != 0
    assert "broken" in result.stderr
    assert "scripts/gen_broken.py" in result.stderr


def test_no_matching_generator_is_quiet(repo: Path) -> None:
    manifest(repo, "absent")
    result = run_helper(repo)
    assert result.returncode == 0
    assert result.stdout == result.stderr == ""


def test_call_sites_share_discovery_before_aggregates() -> None:
    generate = (ROOT / "scripts/generate.sh").read_text()
    ci = (ROOT / ".github/workflows/ci.yml").read_text()
    step = ci.split("- name: Regenerate derived artefacts before validation", 1)[1].split("\n      - name:", 1)[0]
    for source, aggregate in [(generate, 'for index in "${!generators[@]}"; do\n  generator='), (step, "python3 scripts/gen_health_trust_summary.py")]:
        assert "per-dataset-derivation" in source
        assert source.index("bash scripts/derive_per_dataset.sh") < source.index(aggregate)


def test_release_build_stops_before_aggregates_on_dataset_failure(repo: Path) -> None:
    manifest(repo, "broken")
    shutil.copy(ROOT / "scripts/generate.sh", repo / "scripts/generate.sh")
    shutil.copy(HELPER, repo / "scripts/derive_per_dataset.sh")
    (repo / "scripts/gen_broken.py").write_text("raise SystemExit(7)\n")
    (repo / "scripts/gen_health_trust_summary.py").write_text("from pathlib import Path\nPath('aggregate-ran').touch()\n")
    result = subprocess.run(["bash", "scripts/generate.sh", "release-build"], cwd=repo, text=True, capture_output=True)
    assert result.returncode != 0
    assert "scripts/gen_broken.py" in result.stderr
    assert not (repo / "aggregate-ran").exists()


@pytest.mark.parametrize("caller", ["release", "ci"])
def test_dataset_runs_before_first_aggregate(repo: Path, caller: str) -> None:
    manifest(repo, "example")
    shutil.copy(ROOT / "scripts/generate.sh", repo / "scripts/generate.sh")
    shutil.copy(HELPER, repo / "scripts/derive_per_dataset.sh")
    (repo / "scripts/gen_example.py").write_text(
        "from pathlib import Path\nPath('order').write_text('dataset\\n')\n"
    )
    (repo / "scripts/gen_health_trust_summary.py").write_text(
        "from pathlib import Path\n"
        "p = Path('order')\np.write_text(p.read_text() + 'aggregate\\n')\n"
    )
    if caller == "release":
        command = ["bash", "scripts/generate.sh", "release-build"]
    else:
        ci = (ROOT / ".github/workflows/ci.yml").read_text()
        step = ci.split("- name: Regenerate derived artefacts before validation", 1)[1].split("\n      - name:", 1)[0]
        lines = step.split("run: |", 1)[1].splitlines()
        first_commands = "\n".join(line.strip() for line in lines[:5])
        command = ["bash", "-c", first_commands]
    result = subprocess.run(command, cwd=repo, text=True, capture_output=True)
    if caller == "ci":
        assert result.returncode == 0, result.stderr
    assert (repo / "order").read_text() == "dataset\naggregate\n"
