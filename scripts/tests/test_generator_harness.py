import gc
from pathlib import Path

from scripts.tests.generator_harness import run_generator, run_generator_twice


ROOT = Path(__file__).resolve().parents[2]
PYTHON_GENERATOR = ROOT / "scripts/gen_dashboard_filters.py"
BASH_GENERATOR = ROOT / "scripts/gen_data_reports.sh"
PYTHON_INPUTS = ["datapulse.json", "health/latest.json"]
PYTHON_OUTPUTS = ["docs/.dashboard_filters.json"]
BASH_INPUTS = ["health/latest.json", "data/fuelprice.md"]
BASH_OUTPUTS = ["data/fuelprice.md"]


def test_python_generator_produces_expected_outputs(tmp_path: Path) -> None:
    result = run_generator(
        ROOT,
        PYTHON_GENERATOR,
        PYTHON_INPUTS,
        PYTHON_OUTPUTS,
        workdir_root=tmp_path / "python-generator",
    )

    assert result.returncode == 0, result.stderr
    assert all(result.outputs[path] is not None for path in PYTHON_OUTPUTS)


def test_python_generator_is_deterministic() -> None:
    first, second, diff = run_generator_twice(
        ROOT, PYTHON_GENERATOR, PYTHON_INPUTS, PYTHON_OUTPUTS
    )

    assert first.returncode == second.returncode == 0
    assert all(diff.values())


def test_python_generator_handles_malformed_input(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "datapulse.json").write_text("{}\n", encoding="utf-8")

    result = run_generator(
        source,
        PYTHON_GENERATOR,
        ["datapulse.json"],
        PYTHON_OUTPUTS,
        workdir_root=tmp_path / "python-malformed",
    )

    assert result.returncode != 0
    assert "datasets" in result.stderr


def test_python_generator_does_not_touch_tracked_workspace(tmp_path: Path) -> None:
    manifest_before = (ROOT / "datapulse.json").read_bytes()
    output = ROOT / "docs/.dashboard_filters.json"
    output_existed = output.exists()
    output_before = output.read_bytes() if output_existed else None

    result = run_generator(
        ROOT,
        PYTHON_GENERATOR,
        PYTHON_INPUTS,
        PYTHON_OUTPUTS,
        workdir_root=tmp_path / "python-isolated",
    )

    assert result.returncode == 0, result.stderr
    assert (ROOT / "datapulse.json").read_bytes() == manifest_before
    assert output.exists() is output_existed
    assert (output.read_bytes() if output.exists() else None) == output_before


def test_bash_generator_produces_expected_outputs(tmp_path: Path) -> None:
    result = run_generator(
        ROOT,
        BASH_GENERATOR,
        BASH_INPUTS,
        BASH_OUTPUTS,
        workdir_root=tmp_path / "bash-generator",
    )

    assert result.returncode == 0, result.stderr
    assert all(result.outputs[path] is not None for path in BASH_OUTPUTS)


def test_bash_generator_is_deterministic() -> None:
    first, second, diff = run_generator_twice(
        ROOT, BASH_GENERATOR, BASH_INPUTS, BASH_OUTPUTS
    )

    assert first.returncode == second.returncode == 0
    assert all(diff.values())


def test_bash_generator_handles_malformed_input(tmp_path: Path) -> None:
    source = tmp_path / "source"
    health = source / "health/latest.json"
    health.parent.mkdir(parents=True)
    health.write_text("{not valid JSON}\n", encoding="utf-8")

    result = run_generator(
        source,
        BASH_GENERATOR,
        ["health/latest.json"],
        BASH_OUTPUTS,
        workdir_root=tmp_path / "bash-malformed",
    )

    assert result.returncode != 0
    assert "health/latest.json" in result.stderr


def test_bash_generator_does_not_touch_tracked_workspace(tmp_path: Path) -> None:
    health_before = (ROOT / "health/latest.json").read_bytes()
    report_before = (ROOT / "data/fuelprice.md").read_bytes()

    result = run_generator(
        ROOT,
        BASH_GENERATOR,
        BASH_INPUTS,
        BASH_OUTPUTS,
        workdir_root=tmp_path / "bash-isolated",
    )

    assert result.returncode == 0, result.stderr
    assert (ROOT / "health/latest.json").read_bytes() == health_before
    assert (ROOT / "data/fuelprice.md").read_bytes() == report_before


def test_harness_creates_isolated_workdir() -> None:
    result = run_generator(
        ROOT, PYTHON_GENERATOR, PYTHON_INPUTS, PYTHON_OUTPUTS
    )
    workdir = result.workdir

    assert workdir.exists()
    assert workdir != ROOT

    del result
    gc.collect()
    assert not workdir.exists()


def test_harness_run_generator_twice_returns_diff_map() -> None:
    first, second, diff = run_generator_twice(
        ROOT, PYTHON_GENERATOR, PYTHON_INPUTS, PYTHON_OUTPUTS
    )

    assert first.workdir != second.workdir
    assert set(diff) == set(PYTHON_OUTPUTS)
    assert all(isinstance(diff[path], bool) for path in PYTHON_OUTPUTS)
