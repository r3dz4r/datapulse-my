"""Store-root guard and run-log line tests for the pilot capture driver.

Two contracts live in ``scripts/observation_pilot.py``.

Store-root guard: the production observation store root is refused by
default, and only the explicit ``--allow-production-store`` opt-in — a
flag a reader can see in the process arguments — lifts that refusal.
These tests fail if the refusal disappears, if the opt-in stops working,
or if the opt-in changes scratch-store behaviour in either direction.

Run-log line vocabulary: a live capture once printed
``captured=no status=filed capture_status=metadata_only`` for an
unprofiled dataset, and the leading yes/no read as a failure verdict
over a filing that succeeded — three vocabularies for one event, with
the derived one masquerading as the verdict.  The line tests pin the
repair: ``status`` stays the only success/failure verdict,
``capture_status`` stays the envelope's authoritative record, and the
derived field states what the payload actually is, in words that cannot
read as a verdict.  They fail if a metadata-only observation stops being
distinguishable from a byte-level one, if a filed envelope can print as
a failure, or if the payload vocabulary claims bytes that were not
retained.

The production root is never written here: CLI cases monkeypatch
``run_pilot`` so the driver stops exactly at the guard (or immediately
after it), and root-resolution cases call ``_resolve_store_root`` directly,
which performs no I/O against the store.
"""

from __future__ import annotations

import re
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


# ---------------------------------------------------------------------------
# Run-log line vocabulary
# ---------------------------------------------------------------------------


def _outcome(
    status: str, capture_status: str | None, *, due: bool = True, reason: str = "gate reason"
) -> pilot.DatasetOutcome:
    """One outcome built directly: the line contract needs no store."""
    return pilot.DatasetOutcome(
        dataset_id="fuelprice",
        due=due,
        status=status,
        observation_id="obs-fuelprice-20260916" if status == "filed" else None,
        capture_status=capture_status,
        projection_state="retained(profile=fuelprice_csv_v1,records=7)"
        if status == "filed"
        else "-",
        reason=reason,
        record_count=7 if status == "filed" and capture_status == "captured" else None,
    )


BYTE_LEVEL: Final[pilot.DatasetOutcome] = _outcome("filed", "captured")

METADATA_ONLY: Final[pilot.DatasetOutcome] = _outcome("filed", "metadata_only")

SKIPPED_BY_CADENCE: Final[pilot.DatasetOutcome] = _outcome(
    "skipped",
    None,
    due=False,
    reason=(
        "cadence-not-due: 10 minutes since obs-fuelprice-20260916 is inside "
        "the 7 days (weekly) refresh interval"
    ),
)

FAILED: Final[pilot.DatasetOutcome] = _outcome(
    "failed", None, reason="transport failed: TransportError: injected transport failure"
)


def _payload_token(line: str) -> str:
    """The ``payload=`` token from a run-log line."""
    match = re.search(r"(?:^| )payload=([^ ]+)", line)
    assert match is not None, f"no payload token in {line!r}"
    return match.group(1)


def test_filed_byte_level_line_claims_source_bytes() -> None:
    """A byte-level filing says so: status filed, envelope status captured,
    payload described as the retained source bytes."""
    line = BYTE_LEVEL.line
    assert "status=filed" in line
    assert "capture_status=captured" in line
    assert _payload_token(line) == "source-bytes"
    assert BYTE_LEVEL.payload_bytes_retained is True


def test_filed_metadata_only_line_keeps_no_bytes_visible_without_a_verdict() -> None:
    """A filed metadata-only envelope must say both truths at once — an
    envelope was filed, and no payload bytes were retained — with the
    payload stated as what it is, never as a yes/no that reads as
    failure."""
    line = METADATA_ONLY.line
    assert "status=filed" in line
    assert "capture_status=metadata_only" in line
    assert _payload_token(line) == "metadata-only(no-payload-bytes)"
    assert METADATA_ONLY.payload_bytes_retained is False
    assert _payload_token(line) != _payload_token(BYTE_LEVEL.line)


def test_line_carries_no_yes_no_capture_verdict() -> None:
    """The derived capture field must not render as yes/no: ``captured=no``
    next to ``status=filed`` is the shape that read as failure over a
    successful filing, in every outcome including the genuinely failed
    one."""
    for outcome in (BYTE_LEVEL, METADATA_ONLY, SKIPPED_BY_CADENCE, FAILED):
        assert "captured=" not in outcome.line


@pytest.mark.parametrize(
    "capture_status", ["partial", "failed", "metadata_only", "not_captured"]
)
def test_every_filed_status_without_bytes_claims_no_bytes(capture_status: str) -> None:
    """Capture retains bytes only for ``captured``; every other filed
    status is an envelope without payload bytes and the line must never
    claim them."""
    outcome = _outcome("filed", capture_status)
    assert outcome.payload_bytes_retained is False
    token = _payload_token(outcome.line)
    assert token != "source-bytes"
    assert "no-payload-bytes" in token


def test_skipped_by_cadence_line_files_nothing() -> None:
    """A gate skip files no envelope: no observation id, no capture
    status, and a payload token that says nothing was filed."""
    line = SKIPPED_BY_CADENCE.line
    assert "due=no" in line
    assert "status=skipped" in line
    assert "observation_id=-" in line
    assert "capture_status=-" in line
    assert _payload_token(line) == "none(nothing-filed)"
    assert SKIPPED_BY_CADENCE.payload_bytes_retained is False


def test_failed_line_reserves_failure_for_status() -> None:
    """Failure is ``status=failed``'s to announce; the payload token just
    says nothing was filed."""
    line = FAILED.line
    assert "status=failed" in line
    assert "capture_status=-" in line
    assert _payload_token(line) == "none(nothing-filed)"
    assert FAILED.payload_bytes_retained is False


def test_cli_summary_reports_payload_retention_not_a_captured_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The run summary counts payload retention per filing instead of a
    ``captured`` count that reads as success: one byte-level filing, one
    metadata-only filing, one gate skip, one failure."""
    outcomes = [METADATA_ONLY, BYTE_LEVEL, SKIPPED_BY_CADENCE, FAILED]

    def fake_run_pilot(
        dataset_ids: Any, *, root: Any, transport: Any, now: Any = None
    ) -> list[pilot.DatasetOutcome]:
        return outcomes

    monkeypatch.setattr(pilot, "run_pilot", fake_run_pilot)
    code = pilot.main(["--store", str(tmp_path / "scratch"), "--datasets", "fuelprice"])
    assert code == 0
    summary = capsys.readouterr().out
    assert "4 dataset(s): 2 filed (1 with payload bytes, 1 metadata-only)" in summary
    assert "1 skipped by gate, 1 failed" in summary
    assert "captured," not in summary
