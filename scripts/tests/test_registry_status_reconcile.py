"""Tests for scripts/reconcile_registry_status.py (registry lifecycle reconciliation)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "reconcile_registry_status.py"
FIXTURE = ROOT / "scripts" / "tests" / "fixtures" / "registry" / "versions_with_stale_active.json"
WORKFLOW = ROOT / ".github" / "workflows" / "publish-mcp.yml"
SERVER_NAME = "io.github.r3dz4r/datapulse-my"
META_KEY = "io.modelcontextprotocol.registry/official"

from scripts.reconcile_registry_status import (  # noqa: E402
    active_versions,
    build_plan,
    entry_is_latest,
    extract_entries,
)


def _entry(version: str, status: str, is_latest: bool = False) -> dict[str, object]:
    return {
        "server": {"name": SERVER_NAME, "version": version, "title": "DataPulse MY"},
        "_meta": {META_KEY: {"status": status, "isLatest": is_latest}},
    }


def _payload(*entries: dict[str, object]) -> dict[str, object]:
    return {"servers": list(entries), "metadata": {}}


def _fixture_entries() -> list[dict[str, object]]:
    return extract_entries(json.loads(FIXTURE.read_text(encoding="utf-8")))


# A stub mcp-publisher: records its argv, optionally mutates the fixture to
# reflect the deprecation, then exits with a configurable code and output.
STUB_SOURCE = '''#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

argv = sys.argv[1:]
record = Path(os.environ["RECONCILE_STUB_RECORD"])
with record.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(argv) + "\\n")
if os.environ.get("RECONCILE_STUB_MUTATE") == "1" and argv:
    fixture = Path(os.environ["RECONCILE_STUB_FIXTURE"])
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    for entry in payload["servers"]:
        if entry["server"]["version"] == argv[-1]:
            entry["_meta"]["io.modelcontextprotocol.registry/official"]["status"] = "deprecated"
    fixture.write_text(json.dumps(payload, indent=2) + "\\n", encoding="utf-8")
output = os.environ.get("RECONCILE_STUB_OUTPUT", "")
if output:
    print(output, file=sys.stderr)
sys.exit(int(os.environ.get("RECONCILE_STUB_EXIT", "0")))
'''


def _stub_publisher(tmp_path: Path) -> Path:
    stub = tmp_path / "mcp-publisher-stub"
    stub.write_text(STUB_SOURCE, encoding="utf-8")
    stub.chmod(0o755)
    return stub


def _run(
    fixture: Path,
    target: str,
    *,
    dry_run: bool = False,
    stub: Path | None = None,
    stub_env: dict[str, str] | None = None,
) -> tuple[subprocess.CompletedProcess[str], Path]:
    """Run the reconciler offline against a fixture; returns result + record path."""
    record = fixture.parent / "stub-argv.jsonl"
    environment = os.environ.copy()
    environment["RECONCILE_STUB_RECORD"] = str(record)
    environment["RECONCILE_STUB_FIXTURE"] = str(fixture)
    if stub_env:
        environment.update(stub_env)
    command = [
        sys.executable,
        str(SCRIPT),
        "--target",
        target,
        "--from-file",
        str(fixture),
    ]
    if stub is not None:
        command.extend(["--publisher-bin", str(stub)])
    if dry_run:
        command.append("--dry-run")
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )
    return result, record


def _invocations(record: Path) -> list[list[str]]:
    if not record.exists():
        return []
    return [json.loads(line) for line in record.read_text(encoding="utf-8").splitlines()]


def test_plan_from_fixture_targets_only_stale_active() -> None:
    plan = build_plan(_fixture_entries(), "0.13.0")

    assert plan == ["3.4.6"]


def test_target_never_planned_even_when_only_active() -> None:
    entries = [
        _entry("0.13.0", "active", is_latest=False),
        _entry("3.4.6", "active", is_latest=True),
        _entry("9.9.9", "active"),
    ]

    plan = build_plan(entries, "0.13.0")

    assert "0.13.0" not in plan
    assert plan == ["3.4.6", "9.9.9"]


def test_plan_is_empty_when_only_active_version_is_the_target() -> None:
    entries = [
        _entry("0.13.0", "active", is_latest=True),
        _entry("3.4.6", "deprecated"),
        _entry("1.0.1", "deprecated"),
    ]

    assert build_plan(entries, "0.13.0") == []
    assert active_versions(entries) == ["0.13.0"]


def test_dry_run_invokes_no_publisher_and_exits_zero(tmp_path: Path) -> None:
    fixture = tmp_path / "versions.json"
    fixture.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    stub = _stub_publisher(tmp_path)

    result, record = _run(fixture, "0.13.0", dry_run=True, stub=stub)

    assert result.returncode == 0, result.stderr
    assert "3.4.6" in result.stdout
    assert "total: 1" in result.stdout
    assert "--status" not in result.stdout
    assert "Superseded by" not in result.stdout
    assert _invocations(record) == []


def test_apply_invokes_publisher_per_planned_version_flags_before_positionals(
    tmp_path: Path,
) -> None:
    payload = _payload(
        _entry("0.13.0", "active", is_latest=True),
        _entry("3.4.6", "active", is_latest=False),
        _entry("9.9.9", "active"),
        _entry("1.0.0", "deprecated"),
    )
    fixture = tmp_path / "versions.json"
    fixture.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    stub = _stub_publisher(tmp_path)

    result, record = _run(fixture, "0.13.0", stub=stub, stub_env={"RECONCILE_STUB_MUTATE": "1"})

    assert result.returncode == 0, result.stderr
    invocations = _invocations(record)
    assert [argv[-1] for argv in invocations] == ["3.4.6", "9.9.9"]
    message = "Superseded by 0.13.0; canonical surfaces updated"
    for argv in invocations:
        server_index = argv.index(SERVER_NAME)
        assert argv.index("--status") < server_index
        assert argv[argv.index("--status") + 1] == "deprecated"
        assert argv.index("--message") < server_index
        assert argv[argv.index("--message") + 1] == message
        assert argv[-2:] == [SERVER_NAME, argv[-1]]
    assert "deleted" not in " ".join(" ".join(argv) for argv in invocations)


def test_already_deprecated_failure_is_treated_as_success(tmp_path: Path) -> None:
    fixture = tmp_path / "versions.json"
    fixture.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    stub = _stub_publisher(tmp_path)

    result, record = _run(
        fixture,
        "0.13.0",
        stub=stub,
        stub_env={
            "RECONCILE_STUB_EXIT": "1",
            "RECONCILE_STUB_OUTPUT": "error: version 3.4.6 already deprecated",
            "RECONCILE_STUB_MUTATE": "1",
        },
    )

    assert result.returncode == 0, result.stderr
    assert len(_invocations(record)) == 1
    assert "already deprecated" in result.stdout


def test_other_publisher_failure_exits_nonzero_and_surfaces_output(tmp_path: Path) -> None:
    fixture = tmp_path / "versions.json"
    fixture.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    stub = _stub_publisher(tmp_path)

    result, _ = _run(
        fixture,
        "0.13.0",
        stub=stub,
        stub_env={
            "RECONCILE_STUB_EXIT": "3",
            "RECONCILE_STUB_OUTPUT": "publisher exploded: rate limit exceeded",
        },
    )

    assert result.returncode != 0
    output = result.stdout + result.stderr
    assert "rate limit exceeded" in output
    assert "3.4.6" in output


def test_post_state_with_two_active_versions_exits_nonzero(tmp_path: Path) -> None:
    # The stub "succeeds" but never mutates the fixture, so the re-read still
    # observes two active versions: the post-state check must fail loud.
    fixture = tmp_path / "versions.json"
    fixture.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    stub = _stub_publisher(tmp_path)

    result, _ = _run(fixture, "0.13.0", stub=stub, stub_env={"RECONCILE_STUB_MUTATE": "0"})

    assert result.returncode != 0
    output = result.stdout + result.stderr
    assert "0.13.0" in output
    assert "3.4.6" in output


def test_entry_is_latest_defaults_to_false_when_meta_or_field_missing() -> None:
    no_meta = {"server": {"version": "3.5.0"}}
    no_official = {"server": {"version": "3.5.0"}, "_meta": {}}
    no_field = {"_meta": {META_KEY: {"status": "active"}}}

    assert entry_is_latest(no_meta) is False
    assert entry_is_latest(no_official) is False
    assert entry_is_latest(no_field) is False
    assert entry_is_latest(_entry("3.5.0", "active", is_latest=True)) is True


def test_post_state_with_target_carrying_is_latest_exits_zero(tmp_path: Path) -> None:
    # True registry shape once the release line outranks the standing entry:
    # the published version is the only active one AND carries isLatest.
    payload = _payload(
        _entry("3.5.0", "active", is_latest=True),
        _entry("3.4.6", "active", is_latest=False),
    )
    fixture = tmp_path / "versions.json"
    fixture.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    stub = _stub_publisher(tmp_path)

    result, record = _run(fixture, "3.5.0", stub=stub, stub_env={"RECONCILE_STUB_MUTATE": "1"})

    assert result.returncode == 0, result.stderr
    assert [argv[-1] for argv in _invocations(record)] == ["3.4.6"]
    assert "isLatest" in result.stdout


def test_post_state_with_is_latest_on_other_version_exits_one(tmp_path: Path) -> None:
    # The stub only flips status, never isLatest: after deprecating 3.4.6 the
    # target is the sole active version but isLatest stays on the superseded
    # higher version — exactly the consumer-facing failure this assertion closes.
    payload = _payload(
        _entry("3.5.0", "active", is_latest=False),
        _entry("3.4.6", "active", is_latest=True),
    )
    fixture = tmp_path / "versions.json"
    fixture.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    stub = _stub_publisher(tmp_path)

    result, _ = _run(fixture, "3.5.0", stub=stub, stub_env={"RECONCILE_STUB_MUTATE": "1"})

    assert result.returncode == 1
    output = result.stdout + result.stderr
    assert "isLatest" in output
    assert "3.4.6" in output
    assert "3.5.0" in output


def test_post_state_with_is_latest_absent_exits_one(tmp_path: Path) -> None:
    # Absence is not a pass: a payload with no isLatest field anywhere must
    # fail the post-state check, not default its way through it.
    entry = {
        "server": {"name": SERVER_NAME, "version": "3.5.0", "title": "DataPulse"},
        "_meta": {META_KEY: {"status": "active"}},
    }
    payload = {"servers": [entry], "metadata": {}}
    fixture = tmp_path / "versions.json"
    fixture.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    stub = _stub_publisher(tmp_path)

    result, _ = _run(fixture, "3.5.0", stub=stub)

    assert result.returncode == 1
    output = result.stdout + result.stderr
    assert "isLatest" in output
    assert "(none)" in output


REBASE_FLOOR = "3.5.0"


def _semver_tuple(value: str) -> tuple[int, ...]:
    """Parse a plain numeric X.Y.Z version into a semantically comparable tuple."""
    parts = value.split(".")
    if len(parts) != 3 or not all(part.isascii() and part.isdigit() for part in parts):
        raise ValueError(f"not a plain numeric X.Y.Z version: {value!r}")
    return tuple(int(part) for part in parts)


def version_authority_problems(
    manifest: str,
    version_txt: str,
    server_json: str,
) -> list[str]:
    """Cross-check the three version authorities; empty list means healthy.

    Unparseable values are reported as problems, never raised past this
    function. Disagreement is reported naming the outlier. An agreed version
    below REBASE_FLOOR is reported because the MCP Registry ranks isLatest
    by semver across all non-deleted versions, so it could never win isLatest.
    """
    labeled = (
        ("manifest", manifest),
        ("VERSION.txt", version_txt),
        ("server.json", server_json),
    )
    problems: list[str] = []
    parsed: list[tuple[int, ...]] = []
    for label, value in labeled:
        try:
            parsed.append(_semver_tuple(value))
        except ValueError as error:
            problems.append(f"{label}: {error}")
    if problems:
        return problems
    groups: dict[str, list[str]] = {}
    for label, value in labeled:
        groups.setdefault(value, []).append(label)
    if len(groups) > 1:
        described = ", ".join(
            f"{value} ({', '.join(labels)})" for value, labels in groups.items()
        )
        problems.append(f"version authorities disagree: {described}")
        return problems
    if parsed[0] < _semver_tuple(REBASE_FLOOR):
        problems.append(
            f"agreed version {manifest} is below the {REBASE_FLOOR} re-base floor "
            "(the MCP Registry ranks isLatest by semver across non-deleted "
            "versions, so it could never win isLatest)"
        )
    return problems


def test_version_authorities_agree_and_never_fall_below_rebase_floor() -> None:
    """Release Please bumps all three authorities together, so the durable
    invariants are agreement (drift is the real hazard) and the 3.5.0 floor:
    the MCP Registry ranks isLatest by semver across all non-deleted
    versions, so a version below 3.5.0 can never win isLatest."""
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads(
        (root / ".release-please-manifest.json").read_text(encoding="utf-8")
    )
    version_txt = (root / "VERSION.txt").read_text(encoding="utf-8").strip()
    server_json = json.loads((root / "server.json").read_text(encoding="utf-8"))

    assert (
        version_authority_problems(
            manifest.get(".", ""),
            version_txt,
            server_json.get("version", ""),
        )
        == []
    )


def test_authority_problems_release_bump_is_healthy() -> None:
    # The release-PR case the old equality pin broke: all three authorities
    # move together to the new version.
    assert version_authority_problems("3.6.0", "3.6.0", "3.6.0") == []


def test_authority_problems_current_rebase_version_is_healthy() -> None:
    assert version_authority_problems("3.5.0", "3.5.0", "3.5.0") == []


def test_authority_problems_catches_drift_between_authorities() -> None:
    problems = version_authority_problems("3.6.0", "3.5.0", "3.6.0")

    assert problems != []
    assert any("VERSION.txt" in problem for problem in problems)


def test_authority_problems_catches_regression_below_floor() -> None:
    problems = version_authority_problems("3.4.6", "3.4.6", "3.4.6")

    assert problems != []
    assert any(REBASE_FLOOR in problem for problem in problems)


def test_authority_problems_rejects_empty_version_without_raising() -> None:
    problems = version_authority_problems("", "3.5.0", "3.5.0")

    assert problems != []
    assert any("manifest" in problem for problem in problems)


def test_authority_problems_rejects_prerelease_suffix_without_raising() -> None:
    problems = version_authority_problems("3.5.0-rc1", "3.5.0-rc1", "3.5.0-rc1")

    assert problems != []
    assert any("rc1" in problem for problem in problems)


def test_authority_floor_comparison_is_semantic_not_lexicographic() -> None:
    # "3.10.0" sorts BELOW "3.5.0" as a string ('1' < '5'), so a naive
    # string comparison would flag it as a regression; semantically it sits
    # above the floor and must be healthy.
    assert "3.10.0" < REBASE_FLOOR
    assert _semver_tuple("3.10.0") > _semver_tuple(REBASE_FLOOR)
    assert version_authority_problems("3.10.0", "3.10.0", "3.10.0") == []


def test_publish_workflow_contains_wired_reconcile_step() -> None:
    steps = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["publish"]["steps"]
    names = [step.get("name") for step in steps]
    reconcile_index = names.index("Reconcile registry lifecycle status")
    publish_index = names.index("Publish server to MCP Registry")
    login_index = names.index("Authenticate to MCP Registry via GitHub OIDC")

    assert login_index < publish_index < reconcile_index
    run = steps[reconcile_index]["run"]
    assert "scripts/reconcile_registry_status.py" in run
    assert "--server-name io.github.r3dz4r/datapulse-my" in run
    assert '--target "$VERSION"' in run
    assert "--publisher-bin ./mcp-publisher" in run
