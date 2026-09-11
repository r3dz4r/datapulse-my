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


def test_version_authorities_agree_at_rebased_3_5_0() -> None:
    """Pin the re-base: all three version authorities read exactly 3.5.0."""
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads(
        (root / ".release-please-manifest.json").read_text(encoding="utf-8")
    )
    version_txt = (root / "VERSION.txt").read_text(encoding="utf-8").strip()
    server_json = json.loads((root / "server.json").read_text(encoding="utf-8"))

    assert manifest == {".": "3.5.0"}
    assert version_txt == "3.5.0"
    assert server_json["version"] == "3.5.0"


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
