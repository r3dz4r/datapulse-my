"""Store-root guard tests for the pilot capture driver.

The contract under test lives in ``scripts/observation_pilot.py``: the
production observation store root is refused by default, and only the
explicit ``--allow-production-store`` opt-in — a flag a reader can see in
the process arguments — lifts that refusal.  These tests fail if the
refusal disappears, if the opt-in stops working, or if the opt-in changes
scratch-store behaviour in either direction.

The production root is never written here: CLI cases monkeypatch
``run_pilot`` so the driver stops exactly at the guard (or immediately
after it), and root-resolution cases call ``_resolve_store_root`` directly,
which performs no I/O against the store.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Final

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import observation_pilot as pilot  # noqa: E402
from observation_store import (  # noqa: E402
    DEFAULT_ROOT,
    ROOT_ENVIRONMENT_VARIABLE,
)

#: The default refusal's message, verbatim — the tripwire's wording is part
#: of the contract.  If this message changes, the change must be deliberate.
REFUSAL_SUFFIX: Final[str] = (
    "is the production observation store root; this pilot writes only "
    "scratch stores — pass a scratch root such as .pilot-scratch"
)


def _fake_run_pilot_recorder(seen: dict[str, Any]) -> Any:
    """A run_pilot stand-in that records its arguments and files nothing."""

    def fake_run_pilot(
        dataset_ids: Any, *, root: Any, transport: Any, now: Any = None
    ) -> list[pilot.DatasetOutcome]:
        seen["dataset_ids"] = list(dataset_ids)
        seen["root"] = root
        return []

    return fake_run_pilot


def test_production_root_is_refused_by_default_with_the_existing_message() -> None:
    """Without the opt-in the production root raises, message verbatim."""
    with pytest.raises(pilot.PilotError) as raised:
        pilot._resolve_store_root(DEFAULT_ROOT)
    assert str(raised.value) == f"store root {DEFAULT_ROOT.resolve()} {REFUSAL_SUFFIX}"


def test_env_configured_production_root_is_refused_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The refusal follows the store module's env-derived production root,
    proving the driver hardcodes no production path of its own."""
    production = tmp_path / "env-production-store"
    monkeypatch.setenv(ROOT_ENVIRONMENT_VARIABLE, str(production))
    with pytest.raises(pilot.PilotError) as raised:
        pilot._resolve_store_root(production)
    assert str(raised.value) == f"store root {production.resolve()} {REFUSAL_SUFFIX}"


def test_opt_in_permits_the_production_root() -> None:
    """With the opt-in the production root resolves instead of raising."""
    permitted = pilot._resolve_store_root(
        DEFAULT_ROOT, allow_production_store=True
    )
    assert permitted == DEFAULT_ROOT.resolve()


def test_opt_in_permits_the_env_configured_production_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The opt-in lifts the env-derived refusal too — both guarded roots,
    and only those, change behaviour under the flag."""
    production = tmp_path / "env-production-store"
    monkeypatch.setenv(ROOT_ENVIRONMENT_VARIABLE, str(production))
    permitted = pilot._resolve_store_root(
        production, allow_production_store=True
    )
    assert permitted == production.resolve()


def test_scratch_root_is_accepted_with_and_without_the_opt_in(
    tmp_path: Path,
) -> None:
    """Deliberate decision: the opt-in is a permission lift, not an
    assertion that the root is production — a non-production root is
    accepted identically with and without the flag."""
    scratch = tmp_path / "pilot-scratch"
    assert pilot._resolve_store_root(scratch) == scratch.resolve()
    assert (
        pilot._resolve_store_root(scratch, allow_production_store=True)
        == scratch.resolve()
    )


def test_cli_refuses_production_root_before_any_write(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Default CLI run against the production root: exit 2, the existing
    refusal on stderr, and run_pilot never reached — so nothing is written."""

    def unreachable(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(
            "run_pilot must not run when the production root is refused"
        )

    monkeypatch.setattr(pilot, "run_pilot", unreachable)
    code = pilot.main(["--store", str(DEFAULT_ROOT), "--datasets", "fuelprice"])
    assert code == 2
    error = capsys.readouterr().err
    assert f"store root {DEFAULT_ROOT.resolve()} {REFUSAL_SUFFIX}" in error


def test_cli_opt_in_reaches_run_pilot_with_the_production_root(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    """Opt-in CLI run against the production root: exit 0 and run_pilot
    receives the production root itself."""
    seen: dict[str, Any] = {}
    monkeypatch.setattr(pilot, "run_pilot", _fake_run_pilot_recorder(seen))
    code = pilot.main(
        [
            "--store",
            str(DEFAULT_ROOT),
            "--allow-production-store",
            "--datasets",
            "fuelprice",
        ]
    )
    assert code == 0
    assert seen["root"] == DEFAULT_ROOT.resolve()
    assert seen["dataset_ids"] == ["fuelprice"]


def test_cli_scratch_run_is_unchanged_by_the_opt_in(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The scratch-store CLI path behaves identically under the flag: the
    flag neither blocks a scratch run nor alters the resolved root."""
    scratch = tmp_path / "pilot-scratch"
    seen: dict[str, Any] = {}
    monkeypatch.setattr(pilot, "run_pilot", _fake_run_pilot_recorder(seen))
    code = pilot.main(
        [
            "--store",
            str(scratch),
            "--allow-production-store",
            "--datasets",
            "fuelprice",
        ]
    )
    assert code == 0
    assert seen["root"] == scratch.resolve()
