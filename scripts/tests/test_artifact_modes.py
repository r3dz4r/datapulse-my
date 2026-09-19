"""Managed-artefact writers must set 0644 files and 0755 directories.

These tests pin the fix for the production residual where ``tempfile.mkstemp``
created 0600 files and ``os.replace`` carried that mode to the final path, so a
reader under a different identity (the operator's read-only state probe) could
not read the managed artefacts and reported the dataset count and health
timestamp as unknown.

The restrictive umask is deliberate: the modes must be set by the writer, not
inherited from the process that happens to run it.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Callable

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from artifact_modes import DIRECTORY_MODE, FILE_MODE  # noqa: E402
import gen_catalog_snapshot  # noqa: E402
import gen_drift  # noqa: E402
import gen_evidence_coverage  # noqa: E402
import gen_health_history  # noqa: E402
import gen_reconciliation  # noqa: E402
import gen_trends  # noqa: E402
import observation_receipt  # noqa: E402
import shadow_health_publication  # noqa: E402
import summarize_pipeline_telemetry  # noqa: E402

Writer = Callable[[Path, Any], None]

# Every repo writer that produced a managed artefact via mkstemp + os.replace,
# and therefore landed at 0600 before the fix.
MANAGED_WRITERS: tuple[tuple[str, Writer, Any], ...] = (
    ("gen_catalog_snapshot", gen_catalog_snapshot.atomic_write, b'{"schema":"fixture"}\n'),
    ("gen_drift", gen_drift.write_atomic, {"schema": "fixture"}),
    ("gen_trends", gen_trends.write_atomic, {"schema": "fixture"}),
    ("gen_reconciliation", gen_reconciliation.write_atomic, {"schema": "fixture"}),
    ("gen_evidence_coverage", gen_evidence_coverage.write_atomic, {"schema": "fixture"}),
    ("observation_receipt", observation_receipt._atomic_write, b'{"schema":"fixture"}\n'),
    ("gen_health_history", gen_health_history.atomic_write, '{"schema":"fixture"}\n'),
    (
        "summarize_pipeline_telemetry",
        summarize_pipeline_telemetry.write_receipt,
        {"schema": "fixture"},
    ),
    (
        "shadow_health_publication",
        shadow_health_publication.atomic_write,
        b'{"schema":"fixture"}\n',
    ),
)


@pytest.fixture
def restrictive_umask() -> Any:
    previous = os.umask(0o077)
    try:
        yield
    finally:
        os.umask(previous)


@pytest.mark.parametrize(
    ("name", "writer", "payload"),
    MANAGED_WRITERS,
    ids=[entry[0] for entry in MANAGED_WRITERS],
)
def test_managed_writer_sets_file_and_directory_modes(
    tmp_path: Path, restrictive_umask: None, name: str, writer: Writer, payload: Any
) -> None:
    target = tmp_path / "created" / "nested" / "artifact.json"

    writer(target, payload)

    assert target.is_file(), name
    assert target.stat().st_mode & 0o777 == FILE_MODE, f"{name} wrote {oct(target.stat().st_mode & 0o777)}"
    assert (tmp_path / "created").stat().st_mode & 0o777 == DIRECTORY_MODE, name
    assert target.parent.stat().st_mode & 0o777 == DIRECTORY_MODE, name
    assert target.parent.parent.stat().st_mode & 0o777 == DIRECTORY_MODE, name


@pytest.mark.parametrize(
    ("name", "writer", "payload"),
    MANAGED_WRITERS,
    ids=[entry[0] for entry in MANAGED_WRITERS],
)
def test_managed_writer_repairs_a_pre_existing_0600_file(
    tmp_path: Path, name: str, writer: Writer, payload: Any
) -> None:
    target = tmp_path / "artifact.json"
    target.write_bytes(b"stale")
    target.chmod(0o600)

    writer(target, payload)

    assert target.stat().st_mode & 0o777 == FILE_MODE, f"{name} left {oct(target.stat().st_mode & 0o777)}"


def test_managed_writer_leaves_existing_directory_mode_untouched(
    tmp_path: Path, restrictive_umask: None
) -> None:
    existing = tmp_path / "existing"
    existing.mkdir()
    existing.chmod(0o700)

    gen_drift.write_atomic(existing / "artifact.json", {"schema": "fixture"})

    assert existing.stat().st_mode & 0o777 == 0o700
    assert (existing / "artifact.json").stat().st_mode & 0o777 == FILE_MODE
