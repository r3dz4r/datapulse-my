"""Run every repository shell test in the fast pytest gate."""

from __future__ import annotations

from pathlib import Path
import subprocess
import time

import pytest


TESTS_DIR = Path(__file__).parent
SHELL_TESTS = sorted(TESTS_DIR.glob("test_*.sh"))
SKIP_REASONS = {
    "scripts/tests/test_gen_rss_equivalence.sh": (
        "deliberate one-off equivalence proof against the pre-optimisation "
        "revision; slow because that renderer takes minutes, so it is not part "
        "of the fast gate"
    ),
    "scripts/tests/test_openwiki_snapshot.sh": (
        "blocked on OpenWiki provider credits; fails for a reason outside this "
        "repository"
    ),
}


def shell_test_parameters() -> list[object]:
    """Return one pytest case for each shell test present on disk."""
    parameters: list[object] = []
    for shell_test in SHELL_TESTS:
        relative_path = shell_test.relative_to(TESTS_DIR.parent.parent).as_posix()
        if relative_path in SKIP_REASONS:
            parameters.append(
                pytest.param(
                    shell_test,
                    marks=pytest.mark.skip(reason=SKIP_REASONS[relative_path]),
                    id=shell_test.name,
                )
            )
        else:
            parameters.append(pytest.param(shell_test, id=shell_test.name))
    return parameters


@pytest.mark.parametrize("shell_test", shell_test_parameters())
def test_shell_suite(shell_test: Path) -> None:
    """A non-zero shell-test exit remains a pytest failure."""
    started = time.monotonic()
    try:
        result = subprocess.run(
            ["bash", str(shell_test)],
            cwd=TESTS_DIR.parent.parent,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        duration = time.monotonic() - started
        pytest.fail(
            f"{shell_test.name} timed out after {duration:.3f}s\n"
            f"stdout:\n{error.stdout or ''}\n"
            f"stderr:\n{error.stderr or ''}"
        )

    duration = time.monotonic() - started
    assert result.returncode == 0, (
        f"{shell_test.name} exited {result.returncode} after {duration:.3f}s\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
