from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "scripts").mkdir()
    return tmp_path


def manifest(repo: Path, *ids: str) -> None:
    (repo / "datapulse.json").write_text(json.dumps({"datasets": [{"id": item} for item in ids]}))


def run_discovery(repo: Path, caller: str) -> subprocess.CompletedProcess[str]:
    if caller == "release":
        source = (ROOT / "scripts/generate.sh").read_text()
    else:
        ci = (ROOT / ".github/workflows/ci.yml").read_text()
        step = ci.split("- name: Regenerate derived artefacts before validation", 1)[1].split("\n      - name:", 1)[0]
        source = textwrap.dedent(step.split("run: |\n", 1)[1].split("\n      #", 1)[0])
    block = source.split("python3 - <<'PY'", 1)[1].split("\nPY", 1)[0]
    return subprocess.run(["python3", "-c", block], cwd=repo, text=True, capture_output=True)


@pytest.mark.parametrize("caller", ["release", "ci"])
def test_manifest_selects_matching_generators(repo: Path, caller: str) -> None:
    manifest(repo, "new_dataset", "other")
    (repo / "scripts/gen_new_dataset.py").write_text("from pathlib import Path\nPath('order').write_text('dataset\\n')\n")
    (repo / "scripts/gen_unlisted.py").write_text("raise SystemExit(9)\n")
    result = run_discovery(repo, caller)
    assert result.returncode == 0, result.stderr
    assert (repo / "order").read_text() == "dataset\n"


@pytest.mark.parametrize("caller", ["release", "ci"])
def test_failure_names_dataset_and_generator(repo: Path, caller: str) -> None:
    manifest(repo, "broken")
    (repo / "scripts/gen_broken.py").write_text("raise SystemExit(7)\n")
    result = run_discovery(repo, caller)
    assert result.returncode != 0
    assert "broken" in result.stderr
    assert "scripts/gen_broken.py" in result.stderr
    assert "exit 7" in result.stderr


@pytest.mark.parametrize("caller", ["release", "ci"])
def test_no_matching_generator_is_quiet(repo: Path, caller: str) -> None:
    manifest(repo, "absent")
    result = run_discovery(repo, caller)
    assert result.returncode == 0
    assert result.stdout == result.stderr == ""


def test_call_sites_share_discovery_before_aggregates() -> None:
    generate = (ROOT / "scripts/generate.sh").read_text()
    ci = (ROOT / ".github/workflows/ci.yml").read_text()
    step = ci.split("- name: Regenerate derived artefacts before validation", 1)[1].split("\n      - name:", 1)[0]
    for source, aggregate in [(generate, 'for index in "${!generators[@]}"; do\n  generator='), (step, "python3 scripts/gen_health_trust_summary.py")]:
        assert "per-dataset-derivation" in source
        assert source.index("python3 - <<'PY'", source.index("per-dataset-derivation")) < source.index(aggregate)


def test_ci_readme_generation_and_validators_follow_derivation() -> None:
    ci = (ROOT / ".github/workflows/ci.yml").read_text()
    lines = ci.splitlines()
    marker = next(i for i, line in enumerate(lines) if "per-dataset-derivation" in line)
    # The --check precheck exits early when README is unchanged, before comparing derived prose.
    readme_runs = [i for i, line in enumerate(lines) if "python3 scripts/gen_readme.py" in line and "--check" not in line]
    assert readme_runs
    assert all(i > marker for i in readme_runs)
    step = ci.split("- name: Regenerate derived artefacts before validation", 1)[1].split("\n      - name:", 1)[0]
    assert "if: env.FULL_VERIFICATION == 'true'" in step
    assert "python3 scripts/gen_readme.py\n" in step
    for validator in ("verify_doc_claims.py", "verify_distribution_sync.py"):
        positions = [i for i, line in enumerate(lines) if validator in line]
        assert positions and all(i > marker for i in positions)


def test_release_build_stops_before_aggregates_on_dataset_failure(repo: Path) -> None:
    manifest(repo, "broken")
    shutil.copy(ROOT / "scripts/generate.sh", repo / "scripts/generate.sh")
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
        commands = textwrap.dedent(step.split("run: |\n", 1)[1].split("\n      #", 1)[0])
        first_commands = commands.split("python3 scripts/gen_health_trust_summary.py", 1)[0] + "python3 scripts/gen_health_trust_summary.py"
        command = ["bash", "-c", first_commands]
    result = subprocess.run(command, cwd=repo, text=True, capture_output=True)
    if caller == "ci":
        assert result.returncode == 0, result.stderr
    assert (repo / "order").read_text() == "dataset\naggregate\n"


def test_release_public_preflight_follows_surface_generators() -> None:
    result = subprocess.run(
        ["bash", "scripts/generate.sh", "release-build", "--list"],
        cwd=ROOT, text=True, capture_output=True, check=True,
    )
    commands = [line for line in result.stdout.splitlines() if line[:1].isdigit()]
    preflight = next(i for i, line in enumerate(commands) if "verify_distribution_sync.py" in line)
    for generator in (
        "gen_readme.py", "gen_mcp_reference.py", "gen_ai_catalog.py",
        "gen_llms_summary.py", "gen_public_discovery.py", "embed_dashboard_data.py",
        "gen_site_nav.py",
    ):
        positions = [i for i, line in enumerate(commands) if f"scripts/{generator}" in line]
        assert positions, generator
        assert positions[0] < preflight, generator
