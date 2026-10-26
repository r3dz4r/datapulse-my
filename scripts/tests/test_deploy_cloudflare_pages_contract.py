"""Contract tests for the canonical native Cloudflare Pages deployment."""

from __future__ import annotations

import json
import ast
import builtins
from datetime import datetime, timedelta, timezone
import re
import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import shutil
import sys
from types import SimpleNamespace

import pytest
import yaml

from scripts.classify_change import is_health_only_change
from scripts.attestation_fetch_refs import fetch_refs
from scripts.tests.test_attestation_projections import accepted_root
from scripts.tests.test_attestations import fixture_root


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/deploy-cloudflare-pages.yml"
SERVED_VERIFIER = ROOT / "scripts/verify_served_release.sh"


def _workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_signed_publication_has_no_candidate_submission_or_append_wait() -> None:
    signing = yaml.safe_load(_workflow())["jobs"]["sign_health"]
    body = yaml.safe_dump(signing)
    for forbidden in ("APPEND_", "submit_attestation_append.sh", "--wait-for-acceptance",
                      "existing_append", "append_acceptance", "append_submission",
                      "refresh_chain_head.sh", "bind_candidate_witness.py", "gh pr "):
        assert forbidden not in body, forbidden
    assert not any(key.startswith("APPEND_") for key in yaml.safe_load(_workflow())["env"])
    assert "accepted_head" in {step.get("id") for step in signing["steps"]}


@pytest.mark.parametrize("damage", ["none", "health", "manifest", "missing_head", "unnamed_head", "witness"])
def test_signed_statement_uses_only_mains_accepted_head(tmp_path: Path, damage: str) -> None:
    """Execute the shipped Git import, binding guard and statement generator."""
    from scripts import gen_attestations as ga
    from scripts.tests.test_append_set_isolation import accept, git
    from scripts.tests.test_attestations import fixture_rekor_reference

    root, key = fixture_root(tmp_path / "checkout")
    now = datetime.now(timezone.utc).replace(microsecond=0)
    health = root / "health/latest.json"
    snapshot = json.loads(health.read_text())
    snapshot["checked_at"] = (now - timedelta(seconds=30)).isoformat().replace("+00:00", "Z")
    snapshot["datasets"][0]["last_checked"] = snapshot["checked_at"]
    health.write_text(json.dumps(snapshot))
    reference = fixture_rekor_reference(root, "rekor-fixture")
    ga.generate(root, key, now, reference if damage != "witness" else None)
    mirror = root / ".attestations/chain_head.json"
    if damage == "missing_head":
        mirror.unlink()
    source = accept(root)
    origin = tmp_path / "origin.git"
    git(root, "clone", "--bare", str(root), str(origin))
    git(root, "remote", "add", "origin", str(origin))
    if damage == "health":
        health.write_bytes(health.read_bytes() + b" ")
    elif damage == "manifest":
        manifest_path = root / "datapulse.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["datasets"][0]["url"] = "https://example.test/changed-source"
        manifest_path.write_text(json.dumps(manifest))
    elif damage == "unnamed_head":
        # A valid private append still cannot be signed before main names it.
        ga.generate(root, key, now + timedelta(seconds=1), reference, force_append=True)
    (root / "scripts").symlink_to(ROOT / "scripts", target_is_directory=True)
    steps = yaml.safe_load(_workflow())["jobs"]["sign_health"]["steps"]
    guard = next(step for step in steps if step.get("id") == "accepted_head")
    generate = next(step for step in steps if step.get("name") == "Generate deterministic health attestation statement")
    runner = tmp_path / "runner"
    runner.mkdir()
    env = {**os.environ, "PROMOTION_SOURCE_SHA": source, "RUNNER_TEMP": str(runner),
           "GITHUB_OUTPUT": str(tmp_path / "output")}
    result = subprocess.run(["bash", "-c", guard["run"] + "\n" + generate["run"]],
                            cwd=root, env=env, capture_output=True, text=True, timeout=30)
    statement = runner / "health.latest.statement.json"
    if damage in {"health", "manifest", "missing_head", "witness", "unnamed_head"}:
        assert result.returncode != 0, result.stdout + result.stderr
        assert not statement.exists(), "Unaccepted inputs must never reach signing"
    else:
        assert result.returncode == 0, result.stdout + result.stderr
        accepted = json.loads(git(root, "show", "origin/main:attestations/chain-index.json"))
        signed = json.loads(statement.read_text())
        assert signed["predicate"]["legacyEd25519"]["chainHead"] == accepted["current_head"]
        assert accepted["current_head"] in accepted["heads"]
        assert (tmp_path / "output").read_text() == "state=accepted\n"
    assert git(root, "rev-parse", "HEAD") == source


def _deploy_step(name: str) -> dict:
    steps = yaml.safe_load(_workflow())["jobs"]["deploy"]["steps"]
    return next(step for step in steps if step.get("name") == name)


def _write_site_json(site: Path, reference: str, value: dict) -> None:
    path = site / reference
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _stage_attestation_selector(fixture_root: Path) -> None:
    scripts = fixture_root / "scripts"
    scripts.mkdir()
    (scripts / "select_served_attestations.py").write_bytes(
        (ROOT / "scripts/select_served_attestations.py").read_bytes()
    )


def test_pages_passes_explicit_full_revision_depth_without_raising_guard() -> None:
    run = _deploy_step("Keep verifier-reachable attestation history")["run"]
    assert "--full-revisions-per-day 1" in run
    assert "--max-files 18000" in run


def test_pages_rejects_projections_different_from_accepted_main_before_publication() -> None:
    steps = yaml.safe_load(_workflow())["jobs"]["deploy"]["steps"]
    names = [step.get("name") for step in steps]
    guard = _deploy_step("Require served projections from committed main")
    run = guard["run"]
    assert names.index("Keep verifier-reachable attestation history") < names.index(guard["name"])
    assert names.index(guard["name"]) < names.index("Deploy isolated Cloudflare Pages preview artifact")
    assert "python3 scripts/gen_attestation_projections.py --root \"$accepted_root\" --check" in run
    assert "served projections must match the committed tree" in run
    assert "served_head=" in run and "committed_head=" in run
    for path in (
        "attestations/latest/index.json",
        "attestations/latest/chain_head.json",
        "attestations/latest/scores.json",
        "attestations/chain-index.json",
        ".attestations/chain_head.json",
    ):
        assert path in run


def test_projection_checkout_covers_committed_heads_revisions(tmp_path: Path) -> None:
    run = _deploy_step("Require served projections from committed main")["run"]
    match = re.search(r'projection_paths="\$\(python3 - "\$accepted_root" <<\'PY\'\n(?P<body>.*?)\nPY\n\)"', run, re.S)
    assert match is not None
    assert "accepted_discovery(root, \"HEAD\")" in match.group("body")
    assert "set_directory(document[\"heads\"][head])" in match.group("body")
    assert "PROJECTIONS, REGISTRY" in match.group("body")
    assert "for name in FILES" in match.group("body")
    assert "sparse-checkout set --no-cone --stdin" in run
    assert '"/$set_dir/"' not in run and ' /attestations/' not in run

    from scripts import attestation_sets, gen_attestation_projections
    from scripts.verify_attestation_append import accepted_discovery

    root, key = accepted_root(tmp_path)
    from scripts import gen_attestations as ga
    ga.generate(root, key, datetime(2026, 8, 15, 2, tzinfo=timezone.utc), force_append=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "accepted revision"], cwd=root,
                   check=True, capture_output=True)
    document = accepted_discovery(root, "HEAD")
    head = document["current_head"]
    directory = attestation_sets.set_directory(document["heads"][head])
    revision_head = f"{directory}/revisions/{head}/chain_head.json"
    if subprocess.run(["git", "cat-file", "-e", f"HEAD:{revision_head}"], cwd=root,
                      capture_output=True).returncode == 0:
        directory = attestation_sets.set_directory(revision_head)
    selected = set(gen_attestation_projections.PROJECTIONS) | {gen_attestation_projections.REGISTRY}
    selected.update(f"{directory}/{name}" for name in attestation_sets.FILES)
    assert len(selected) == 11
    assert "attestations" not in selected
    assert all(not path.endswith("/") for path in selected)
    result = subprocess.run([sys.executable, "-c", match.group("body"), str(root)], cwd=ROOT,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert set(result.stdout.splitlines()) == {"/" + path for path in selected}


def test_projection_checkout_set_is_pointer_derived_and_bounded() -> None:
    run = _deploy_step("Require served projections from committed main")["run"]
    checkout = next(line for line in run.splitlines() if "sparse-checkout set" in line)
    assert '--stdin <<< "$projection_paths"' in checkout
    assert "attestations/" not in checkout and "revisions/" not in checkout
    assert '"/$set_dir/"' not in _workflow()
    match = re.search(
        r'projection_paths="\$\(python3 - "\$accepted_root" <<\'PY\'\n(?P<body>.*?)\nPY\n\)"',
        run, re.S,
    )
    assert match is not None
    body = match.group("body")
    assert 'accepted_discovery(root, "HEAD")' in body
    assert 'head = document["current_head"]' in body
    assert 'directory = set_directory(document["heads"][head])' in body
    assert 'set_directory(revision_head)' in body
    assert 'paths = {*PROJECTIONS, REGISTRY, *(f"{directory}/{name}" for name in FILES)}' in body
    assert 'print("\\n".join("/" + path for path in sorted(paths)))' in body


@pytest.mark.parametrize(
    ("pass_on", "check_status"),
    [(100, 1), (1, 1), (3, 1), (100, 2)],
    ids=["refresh-timeout", "already-fresh", "refresh-passes", "invalid-evidence"],
)
def test_deploy_waits_for_committed_projection_refresh_before_refusing(
    tmp_path: Path, pass_on: int, check_status: int,
) -> None:
    root, _ = accepted_root(tmp_path)
    subprocess.run(["git", "remote", "add", "origin", str(root)], cwd=root, check=True)
    site = root / "_site"
    for path in (
        "attestations/latest/index.json", "attestations/latest/chain_head.json",
        "attestations/latest/binding.json", "attestations/latest/scores.json",
        "attestations/chain-index.json", ".attestations/chain_head.json",
    ):
        target = site / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / path, target)
    head = json.loads((site / "attestations/chain-index.json").read_text())["current_head"]
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "python3").write_text(
        f'#!{sys.executable}\n'
        'import os, pathlib, sys\n'
        'if sys.argv[1] == "-":\n'
        f'    os.execv({sys.executable!r}, [{sys.executable!r}, *sys.argv[1:]])\n'
        'counter = pathlib.Path(os.environ["CHECK_COUNT"])\n'
        'count = int(counter.read_text()) + 1 if counter.exists() else 1\n'
        'counter.write_text(str(count))\n'
        'if count >= int(os.environ["PASS_ON"]):\n'
        '    print("OK: accepted attestation projections match evidence")\n'
        '    sys.exit(0)\n'
        'print("STALE attestations/chain-index.json committed=old derived=new"\n'
        '      if os.environ["CHECK_STATUS"] == "1" else "REFUSED: invalid evidence")\n'
        'sys.exit(int(os.environ["CHECK_STATUS"]))\n'
    )
    (bin_dir / "gh").write_text(
        '#!/bin/bash\nprintf "gh %s\\n" "$*" >> "$CALL_LOG"\n'
        'exit 2\n'
    )
    (bin_dir / "git").write_text(
        '#!/bin/bash\nprintf "git %s\\n" "$*" >> "$CALL_LOG"\n'
        f'exec "{shutil.which("git")}" "$@"\n'
    )
    for stub in bin_dir.iterdir():
        stub.chmod(0o755)
    runner_temp = tmp_path / "runner"
    runner_temp.mkdir()
    count_file = tmp_path / "count"
    calls_file = tmp_path / "calls"
    run = _deploy_step("Require served projections from committed main")["run"]
    assert "gh pr " not in run
    # Advance Bash's clock in the parent shell; exercise the real 600s bound.
    harness = 'sleep() { printf "sleep %s\\n" "$*" >> "$CALL_LOG"; SECONDS=$((SECONDS + $1)); }\n'
    result = subprocess.run(
        ["bash", "-c", harness + run], cwd=root,
        env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}",
             "PYTHONPATH": str(ROOT), "RUNNER_TEMP": str(runner_temp),
             "CHECK_COUNT": str(count_file), "CALL_LOG": str(calls_file),
             "PASS_ON": str(pass_on),
             "CHECK_STATUS": str(check_status)},
        capture_output=True, text=True, timeout=30,
    )
    count = int(count_file.read_text())
    calls = calls_file.read_text().splitlines() if calls_file.exists() else []
    notices = result.stdout + result.stderr
    assert count <= 32
    assert not any(call.startswith("gh ") for call in calls)
    assert sum("fetch --no-tags origin refs/heads/main:refs/remotes/origin/main" in call
               for call in calls) == count
    refusal = "served projections must match the committed tree"
    if result.returncode == 1:
        assert (
            "::error title=Attestation projection mismatch::"
            f"{refusal}: served_head={head} committed_head={head} (committed projections are stale)"
        ) in result.stderr.splitlines()
    # An unchanged remote ref must not trigger repeated worktree resets.
    assert sum("reset --hard HEAD" in call for call in calls) == 1
    if pass_on == 1:
        assert result.returncode == 0, notices
        assert count == 1
        assert "Projections pending refresh" not in notices
        assert not any(call.startswith("sleep ") for call in calls)
    elif check_status != 1:
        assert result.returncode == 1
        assert refusal in result.stderr
        assert count == 1
        assert "Projections pending refresh" not in notices
        assert not any(call.startswith("sleep ") for call in calls)
    elif pass_on == 100:
        assert result.returncode == 1
        assert refusal in result.stderr
        assert count > 1
        assert notices.count("::notice title=Projections pending refresh::") == 1
        assert notices.count("::notice title=Projections pending refresh timed out::") == 1
        assert f"served_head={head} committed_head={head}" in notices
        assert sum(call == "sleep 20" for call in calls) <= 30
    else:
        assert result.returncode == 0, notices
        assert count == pass_on
        assert refusal not in result.stderr
        assert result.stdout.index("Projections pending refresh") < result.stdout.index("OK:")
    assert all(call == "sleep 20" for call in calls if call.startswith("sleep "))


def test_projection_refresh_materializes_moved_main_before_rechecking(tmp_path: Path) -> None:
    from scripts.tests.test_attestation_projections import accept_next_day

    root, key = accepted_root(tmp_path)
    accept_next_day(root, key)
    stale_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/gen_attestation_projections.py"), "--root", str(root)],
        cwd=ROOT, check=True, capture_output=True,
    )
    subprocess.run(["git", "add", "-u"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "refresh accepted projections"], cwd=root,
                   check=True, capture_output=True)
    refresh_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    site = root / "_site"
    from scripts.gen_attestation_projections import PROJECTIONS
    for path in PROJECTIONS:
        target = site / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / path, target)
    subprocess.run(["git", "reset", "--hard", stale_sha], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", str(root)], cwd=root, check=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "python3").write_text(
        f'#!{sys.executable}\n'
        'import os, sys\n'
        'args = sys.argv[1:]\n'
        'if args[0] != "-":\n'
        '    with open(os.environ["CALL_LOG"], "a") as log:\n'
        '        log.write("check\\n")\n'
        f'    args[0] = {str(ROOT / "scripts/gen_attestation_projections.py")!r}\n'
        f'os.execv({sys.executable!r}, [{sys.executable!r}, *args])\n'
    )
    (bin_dir / "gh").write_text(
        '#!/bin/bash\nprintf "gh %s\\n" "$*" >> "$CALL_LOG"\nexit 2\n'
    )
    (bin_dir / "git").write_text(
        '#!/bin/bash\nprintf "git %s\\n" "$*" >> "$CALL_LOG"\n'
        f'exec "{shutil.which("git")}" "$@"\n'
    )
    for stub in bin_dir.iterdir():
        stub.chmod(0o755)
    runner_temp = tmp_path / "runner"
    runner_temp.mkdir()
    calls_file = tmp_path / "calls"
    harness = (
        'sleep() { SECONDS=$((SECONDS + $1)); '
        'command git update-ref refs/heads/main "$REFRESH_SHA"; }\n'
    )
    result = subprocess.run(
        ["bash", "-c", harness + _deploy_step("Require served projections from committed main")["run"]],
        cwd=root, env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}",
                       "PYTHONPATH": str(ROOT), "RUNNER_TEMP": str(runner_temp),
                       "GITHUB_REPOSITORY": "example/data-pulse", "CALL_LOG": str(calls_file),
                       "REFRESH_SHA": refresh_sha}, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.index("Projections pending refresh") < result.stdout.index("OK:")
    accepted = runner_temp / "accepted-projections"
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=accepted, text=True).strip() == refresh_sha
    for path in PROJECTIONS:
        assert (accepted / path).read_bytes() == (site / path).read_bytes()
    calls = calls_file.read_text().splitlines()
    assert not any(call.startswith("gh ") for call in calls)
    assert calls.count("check") == 2
    assert sum("reset --hard HEAD" in call for call in calls) == 2
    selected = subprocess.check_output(["git", "ls-files", "-t"], cwd=accepted, text=True).splitlines()
    assert sum(line.startswith("H ") for line in selected) == 11


@pytest.mark.parametrize("mismatch", [False, True])
def test_pages_projection_guard_checks_assembled_bytes(tmp_path: Path, mismatch: bool) -> None:
    root, _ = accepted_root(tmp_path)
    (root / "scripts").symlink_to(ROOT / "scripts", target_is_directory=True)
    subprocess.run(["git", "remote", "add", "origin", str(root)], cwd=root, check=True)
    site = root / "_site"
    for path in (
        "attestations/latest/index.json",
        "attestations/latest/chain_head.json",
        "attestations/latest/binding.json",
        "attestations/latest/scores.json",
        "attestations/chain-index.json",
        ".attestations/chain_head.json",
    ):
        target = site / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / path, target)
    committed_head = json.loads((root / "attestations/chain-index.json").read_text())["current_head"]
    if mismatch:
        index = site / "attestations/chain-index.json"
        document = json.loads(index.read_text())
        document["current_head"] = "f" * 64
        index.write_text(json.dumps(document))
    runner_temp = tmp_path / "runner"
    runner_temp.mkdir()
    result = subprocess.run(
        ["bash", "-c", _deploy_step("Require served projections from committed main")["run"]],
        cwd=root, env={**os.environ, "RUNNER_TEMP": str(runner_temp)},
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == (1 if mismatch else 0), result.stdout + result.stderr
    if mismatch:
        assert "served projections must match the committed tree" in result.stderr
        assert f"served_head={'f' * 64}" in result.stderr
        assert f"committed_head={committed_head}" in result.stderr


def test_pages_reuses_valid_accepted_day_without_rewriting_projections(tmp_path: Path) -> None:
    from scripts import gen_attestations as ga

    root, key = fixture_root(tmp_path)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    health = root / "health/latest.json"
    snapshot = json.loads(health.read_text())
    observed = (now - timedelta(seconds=30)).isoformat().replace("+00:00", "Z")
    snapshot["checked_at"] = observed
    snapshot["datasets"][0]["last_checked"] = observed
    health.write_text(json.dumps(snapshot))
    subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.test"], cwd=root, check=True)
    (root / ".gitignore").write_text("private.json\n")
    ga.generate(root, key, now)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", "accepted day"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "remote", "add", "origin", str(root)], cwd=root, check=True)
    subprocess.run(["git", "fetch", "origin", "main"], cwd=root, check=True, capture_output=True)
    (root / "scripts").symlink_to(ROOT / "scripts", target_is_directory=True)
    paths = (
        "attestations/latest/index.json",
        "attestations/latest/chain_head.json",
        "attestations/latest/scores.json",
        "attestations/chain-index.json",
        ".attestations/chain_head.json",
    )
    before = {path: ((root / path).read_bytes(), (root / path).stat().st_mtime_ns) for path in paths}
    # Existing witness verification is covered by the strict guard fixtures above.
    from scripts.tests.test_attestations import fixture_rekor_reference
    reference = fixture_rekor_reference(root, "rekor-fixture")
    ga.generate(root, key, now, reference, force_append=True)
    subprocess.run(["git", "add", "attestations", ".attestations"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", "accept witnessed set"], cwd=root, check=True, capture_output=True)
    before = {path: ((root / path).read_bytes(), (root / path).stat().st_mtime_ns) for path in paths}
    guard = next(step for step in yaml.safe_load(_workflow())["jobs"]["sign_health"]["steps"]
                 if step.get("id") == "accepted_head")
    result = subprocess.run(["bash", "-c", guard["run"]], cwd=root, capture_output=True, text=True,
                            env={**os.environ, "PROMOTION_SOURCE_SHA": subprocess.check_output(
                                ["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
                                 "GITHUB_OUTPUT": str(tmp_path / "guard-output")})
    assert result.returncode == 0, result.stdout + result.stderr
    assert before == {path: ((root / path).read_bytes(), (root / path).stat().st_mtime_ns) for path in paths}


@pytest.mark.parametrize(("omitted", "present", "status", "expected"), [
    (True, False, "404", 0),
    (False, False, "404", 1),
    (True, False, "200", 0),
    (True, False, "503", 0),
    (False, True, "404", 1),
    (False, True, "200", 0),
])
def test_served_evidence_distinguishes_retention_from_broken_files(
    tmp_path: Path, omitted: bool, present: bool, status: str, expected: int,
) -> None:
    site = tmp_path / "site"
    reference = "attestations/2026-10-13/revisions/" + "a" * 64 + "/dataset.json"
    _write_site_json(site, "attestations/served-retention.json", {
        "schema": "datapulse/v1/served-attestation-retention",
        "not_served": [reference] if omitted else [],
    })
    if present:
        _write_site_json(site, reference, {})
    source = SERVED_VERIFIER.read_text()
    helpers = source.split("verify_attestation_surface() {", 1)[1].split("# Permit Pages propagation", 1)[0]
    shell = '''set -Eeuo pipefail
site_dir="$1"; smoke_dir="$2"; base_url=https://example.test; status="$3"
fail() { echo "$1" >&2; exit 1; }
retrieve() { echo "retrieved $2"; last_status="$status"; printf '{}' > "$3"; }
fetch() { mkdir -p "$(dirname "$3")"; retrieve "$@"; [[ "$last_status" == 200 ]] || fail "missing or stale served surface (HTTP $last_status)"; }
'''
    result = subprocess.run(
        ["bash", "-c", shell + "verify_attestation_surface() {" + helpers
         + '\nverify_dataset_attestation "$4"', "verify", str(site), str(tmp_path / "smoke"), status, reference],
        text=True, capture_output=True, check=False,
    )
    assert result.returncode == expected, result.stdout + result.stderr
    if expected == 0 and omitted:
        assert "not served (retention policy)" in result.stdout
        assert "retrieved" not in result.stdout
    if not present and not omitted:
        assert "missing required evidence" in result.stderr
    if present and status == "404":
        assert "missing or stale served surface (HTTP 404)" in result.stderr


def test_pages_attestation_selection_keeps_chain_and_citations(tmp_path: Path) -> None:
    _stage_attestation_selector(tmp_path)
    site = tmp_path / "_site"
    old = "attestations/2026-10-03"
    recent = "attestations/2026-10-04"
    cited = "attestations/2026-10-09/revisions/" + "a" * 64
    current = "attestations/2026-10-10"
    directories = (old, recent, cited, current)
    heads = {str(index): f"{directory}/chain_head.json" for index, directory in enumerate(directories)}
    _write_site_json(site, "attestations/chain-index.json", {
        "heads": heads, "envelopes": {key: {} for key in heads},
    })
    _write_site_json(site, "attestations/latest/index.json", {
        "date": "2026-10-10", "attestations": {"example": f"{current}/example.json"},
    })
    _write_site_json(site, "attestations/latest/binding.json", {})
    for directory in directories:
        for name in ("chain_head", "index", "scores", "example", "uncited"):
            _write_site_json(site, f"{directory}/{name}.json", {})
        _write_site_json(site, f"{directory}/binding.json", {"payload": {}})
    proof = "attestations/rekor/2026-10-03/reference.json"
    _write_site_json(site, proof, {})
    _write_site_json(site, f"{old}/binding.json", {"payload": {}, "rekor": {"reference_ref": proof}})
    (site / "data").mkdir()
    (site / "data/example.md").write_text(f"Verify {old}/example.json and {cited}/chain_head.json")

    step = _deploy_step("Keep verifier-reachable attestation history")
    result = subprocess.run(["bash", "-c", step["run"]], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert (site / "attestations/chain-index.json").is_file()
    assert (site / "attestations/latest/binding.json").is_file()
    assert (site / f"{current}/example.json").is_file()
    assert (site / f"{recent}/uncited.json").is_file()
    assert (site / f"{cited}/uncited.json").is_file()
    assert (site / f"{old}/chain_head.json").is_file()
    assert (site / f"{old}/binding.json").is_file()
    assert (site / proof).is_file()
    assert (site / f"{old}/example.json").is_file()
    assert not (site / f"{old}/uncited.json").exists()


def test_pages_attestation_selection_fails_on_missing_published_reference(tmp_path: Path) -> None:
    _stage_attestation_selector(tmp_path)
    site = tmp_path / "_site"
    _write_site_json(site, "attestations/chain-index.json", {"heads": {}, "envelopes": {}})
    _write_site_json(site, "attestations/latest/index.json", {
        "date": "2026-10-10", "attestations": {"example": "attestations/2026-10-10/missing.json"},
    })
    step = _deploy_step("Keep verifier-reachable attestation history")
    result = subprocess.run(["bash", "-c", step["run"]], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode != 0
    assert "published attestation reference is missing" in result.stderr


def test_pages_file_count_guard_reports_count_and_largest_directory(tmp_path: Path) -> None:
    site = tmp_path / "_site"
    (site / "attestations").mkdir(parents=True)
    for index in range(5):
        (site / "attestations" / f"{index}.json").write_text("{}")
    (site / "index.html").write_text("ok")
    step = _deploy_step("Guard Cloudflare Pages file ceiling")
    assert "18000" in step["run"] and "20000" in step["run"]
    passing = subprocess.run(["bash", "-c", step["run"]], cwd=tmp_path, capture_output=True, text=True)
    assert passing.returncode == 0, passing.stderr
    assert "6 files; largest directory attestations: 5 files" in passing.stdout
    failing = subprocess.run(
        ["bash", "-c", step["run"].replace("18000", "4")],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert failing.returncode != 0
    assert "artifact has 6 files" in failing.stderr
    assert "largest directory attestations: 5 files" in failing.stderr


def test_unverified_head_skips_signing_and_all_deployment() -> None:
    workflow = yaml.safe_load(_workflow())
    signing = workflow["jobs"]["sign_health"]
    steps = {step.get("name"): step for step in signing["steps"]}
    assert signing["outputs"]["accepted_head_state"] == "${{ steps.accepted_head.outputs.state }}"
    assert steps["Generate deterministic health attestation statement"]["if"] == (
        "steps.accepted_head.outputs.state == 'accepted'"
    )
    assert steps["Attempt pinned Cosign signer installation for health-only degradation"]["if"] == (
        "steps.accepted_head.outputs.state == 'accepted'"
    )
    assert steps["Sign and verify current health DSSE bundle"]["if"] == (
        "steps.install_cosign.outcome == 'success' && "
        "steps.accepted_head.outputs.state == 'accepted'"
    )
    assert steps["Stage statement into Sigstore publication"]["if"] == (
        "steps.sign_current_health.outputs.state == 'signed' && "
        "steps.accepted_head.outputs.state == 'accepted'"
    )
    assert steps["Generate per-dataset evidence statements"]["if"] == (
        "steps.accepted_head.outputs.state == 'accepted'"
    )
    assert steps["Sign per-dataset evidence statements"]["if"] == (
        "steps.sign_current_health.outputs.state == 'signed' && "
        "steps.accepted_head.outputs.state == 'accepted'"
    )
    assert steps["Record per-dataset receipt result"]["if"] == (
        "always() && steps.accepted_head.outputs.state == 'accepted'"
    )
    assert steps["Upload verified Sigstore bundle"]["if"] == (
        "steps.sign_current_health.outputs.state == 'signed' && "
        "steps.accepted_head.outputs.state == 'accepted'"
    )
    assert steps["Record explicit attestation state"]["if"] == (
        "always() && steps.accepted_head.outputs.state == 'accepted'"
    )
    assert steps["Record Sigstore result"]["if"] == (
        "always() && steps.accepted_head.outputs.state == 'accepted'"
    )
    assert workflow["jobs"]["deploy"]["if"] == (
        "needs.sign_health.outputs.accepted_head_state == 'accepted'"
    )


@pytest.mark.parametrize("health_only", ["true", "false", ""])
@pytest.mark.parametrize("accepted_state", ["accepted", "", "invalid"])
def test_deploy_gate_requires_verified_main_head_for_every_publication(
    health_only: str, accepted_state: str,
) -> None:
    deploy = yaml.safe_load(_workflow())["jobs"]["deploy"]
    assert deploy["needs"] == ["classify", "sign_health"]
    condition = deploy["if"].replace(
        "needs.sign_health.outputs.health_only", repr(health_only),
    ).replace("needs.sign_health.outputs.accepted_head_state", repr(accepted_state))
    # Exercise the workflow's comparison/OR expression, rather than a duplicate
    # predicate. Neither always() nor a failed dependency may enable promotion.
    result = subprocess.run(["bash", "-c", f"[[ {condition} ]]"], capture_output=True, text=True)
    assert result.returncode in (0, 1), result.stderr
    assert (result.returncode == 0) == (accepted_state == "accepted")


def test_health_publication_keeps_verified_source_and_preserves_trust_plane_on_signer_outage() -> None:
    workflow = yaml.safe_load(_workflow())
    signing = workflow["jobs"]["sign_health"]
    outputs = signing["outputs"]
    assert outputs["settled_sha"] == "${{ steps.settled_main.outputs.settled_sha }}"
    assert outputs["health_only"] == "${{ steps.settled_main.outputs.health_only }}"
    assert outputs["attestation_state"] == "${{ steps.attestation_result.outputs.state }}"
    assert outputs["signed"] == "${{ steps.sigstore_result.outputs.signed }}"
    settled = next(step for step in signing["steps"] if step.get("id") == "settled_main")
    assert "if" not in settled
    preserve = _deploy_step("Preserve served attestation plane (health-only path)")
    assert preserve["if"] == (
        "needs.sign_health.outputs.health_only == 'true' && "
        "needs.sign_health.outputs.attestation_state == 'signer_down'"
    )
    assert 'python3 scripts/verify_attestation_plane_state.py --planedir "$preserved_root"' in preserve["run"]
    assemble = _deploy_step("Assemble canonical Pages artifact")
    summary_copy = next(line for line in assemble["run"].splitlines() if "cp " in line and "datapulse_summary.json" in line)
    assert summary_copy.strip().endswith(" _site/")
    assert "if" not in assemble
    assert "rm -f _site/attestations/latest/binding.json" in assemble["run"]
    build = yaml.safe_load((ROOT / ".github/workflows/publish-publication.yml").read_text())
    staging = next(step for step in build["jobs"]["build"]["steps"]
                   if step.get("name") == "Stage only generated publication inputs")
    assert 'datapulse_summary.json' in staging["run"]


def test_attestation_restore_timeouts_cover_measured_cold_restore() -> None:
    restores = re.findall(
        r"timeout -k 5s (\d+)s bash scripts/restore_attestations\.sh"
        r' --source (?:"\$accepted_main"|HEAD)',
        _workflow(),
    )
    assert len(restores) == 2
    assert all(int(seconds) >= 60 for seconds in restores)
    # The delta-only helper keeps the budget; a whole-tree restore must not
    # creep back in beside it.
    assert not re.search(
        r"git restore --source (?:origin/main|HEAD) --worktree"
        r" -- attestations \.attestations/chain_head\.json",
        _workflow(),
    )


def _served_verifier() -> str:
    return SERVED_VERIFIER.read_text(encoding="utf-8")


def _preview_seed_step() -> dict:
    steps = yaml.safe_load(_workflow())["jobs"]["deploy"]["steps"]
    names = [step.get("name") for step in steps]
    name = "Publish health artifacts to isolated preview KV"
    assert name in names
    assert names.index("Verify release artifact before preview deployment") < names.index(name)
    assert names.index(name) < names.index("Deploy isolated Cloudflare Pages preview artifact")
    return steps[names.index(name)]


def test_preview_kv_publication_uses_existing_writer_and_fails_closed() -> None:
    step = _preview_seed_step()
    assert "if" not in step and "continue-on-error" not in step
    assert step["env"]["DATAPULSE_KV_WRITE"] == "${{ secrets.CLOUDFLARE_API_TOKEN }}"
    assert 'python3 scripts/publish_health_index.py --health health/latest.json' in step["run"]
    assert 'DATAPULSE_KV_PUBLICATION_STATE' in step["env"]


@pytest.mark.parametrize("config_case", ["isolated", "production", "default", "missing", "snapshot_mismatch"])
@pytest.mark.parametrize("publisher_status", [0, 2])
def test_preview_kv_step_selects_configured_namespace_and_propagates_errors(
    tmp_path: Path, config_case: str, publisher_status: int,
) -> None:
    step = _preview_seed_step()
    production, default, preview = "1" * 32, "2" * 32, "3" * 32
    selected = {"production": production, "default": default}.get(config_case, preview)
    config = (
        '[[kv_namespaces]]\nbinding="DATAPULSE_HEALTH_INDEX"\nid="' + default + '"\n'
        '[[env.production.kv_namespaces]]\nbinding="DATAPULSE_HEALTH_INDEX"\nid="' + production + '"\n'
    )
    if config_case != "missing":
        config += '[[env.preview.kv_namespaces]]\nbinding="DATAPULSE_HEALTH_INDEX"\nid="' + selected + '"\n'
    (tmp_path / "wrangler.toml").write_text(config)
    for directory in ("health", "_site/health"):
        (tmp_path / directory).mkdir(parents=True)
        (tmp_path / directory / "latest.json").write_text('{"datasets": []}')
    if config_case == "snapshot_mismatch":
        (tmp_path / "_site/health/latest.json").write_text('{"datasets": [1]}')
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/publish_health_index.py").write_text(
        "import json, os, pathlib, sys\n"
        "pathlib.Path('publication.json').write_text(json.dumps([os.environ['DATAPULSE_KV_NAMESPACE_ID'], sys.argv[1:]]))\n"
        f"raise SystemExit({publisher_status})\n"
    )
    result = subprocess.run(["bash", "-c", step["run"]], cwd=tmp_path, capture_output=True, text=True)
    publication = tmp_path / "publication.json"
    if config_case == "isolated":
        assert result.returncode == publisher_status, result.stderr
        assert json.loads(publication.read_text()) == [preview, ["--health", "health/latest.json"]]
    else:
        assert result.returncode != 0
        assert not publication.exists()


def _classifies_as_health_only(paths: tuple[str, ...]) -> bool:
    return is_health_only_change(paths)


def _assert_deploy_resilience(workflow: str) -> None:
    """Require no coalescing gate and bounded rate-limit handling for both Pages deploys."""
    parsed = yaml.safe_load(workflow)
    steps = parsed["jobs"]["deploy"]["steps"]
    assert "superseded_run" not in workflow

    for name, branch in (
        ("Deploy isolated Cloudflare Pages preview artifact", "--branch=staging"),
        ("Deploy canonical Cloudflare Pages artifact", "--branch=main"),
    ):
        deploy = next(step for step in steps if step.get("name") == name)
        run = deploy["run"]
        assert "for attempt in 1 2 3 4; do" in run
        assert "npx --yes wrangler@3.90.0 pages deploy _site --project-name=datapulse-p4b-preview" in run
        assert branch in run
        assert 'grep -q "10429" "$output"' in run
        assert 'if ! grep -q "10429" "$output"; then' in run
        assert "non-rate-limit failure on attempt $attempt; not retrying." in run
        assert 'exit "$status"' in run
        assert 'if [[ "$attempt" -eq 4 ]]; then' in run
        assert 'delay="$((attempt * 60))"' in run
        assert 'sleep "$delay"' in run

    # The staging deploy always runs; the production deploy is conditional on it
    # having succeeded in the same run.
    preview_deploy = next(
        step for step in steps
        if step.get("name") == "Deploy isolated Cloudflare Pages preview artifact"
    )
    assert "if" not in preview_deploy
    production_deploy = next(
        step for step in steps
        if step.get("name") == "Deploy canonical Cloudflare Pages artifact"
    )
    assert production_deploy["if"] == "steps.deploy_preview.outcome == 'success'"


def test_pages_deploy_resilience_contract_and_mutation_proofs() -> None:
    workflow = _workflow()

    _assert_deploy_resilience(workflow)

    mutations = (
        workflow.replace(
            "      - name: Deploy isolated Cloudflare Pages preview artifact",
            "      - id: superseded_run\n      - name: Deploy isolated Cloudflare Pages preview artifact",
            1,
        ),
        workflow.replace("for attempt in 1 2 3 4; do", "for attempt in 1 2 3; do", 1),
        workflow.replace('if ! grep -q "10429" "$output"; then', "if false; then", 1),
    )
    for mutated in mutations:
        with pytest.raises(AssertionError):
            _assert_deploy_resilience(mutated)


def _alias_helper() -> str:
    """Extract the deployed shell helper for direct state-machine testing."""
    match = re.search(r"(?ms)^retrieve\(\) \{.*?^\}\n^fetch_alias\(\) \{.*?^\}\n", _served_verifier())
    assert match is not None, "the alias verifier must remain executable and contract-tested"
    return textwrap.dedent(match.group(0))


def _run_alias_helper(requested_path: str, responses: dict[str, tuple[str, str, str]]) -> subprocess.CompletedProcess[str]:
    """Run the workflow helper against deterministic HTTP responses."""
    response_cases = "\n".join(
        f'    https://example.test{path}) status={status!r}; location={location!r}; body={body!r} ;;'
        for path, (status, location, body) in responses.items()
    )
    script = f"""
set -Eeuo pipefail
smoke_dir=$(mktemp -d)
trap 'rm -rf "$smoke_dir"' EXIT
website_origin='https://example.test'
base_url="$website_origin"
fetch_max_time=120
fail() {{ echo "$1" >&2; return 1; }}
curl() {{
  local dump='' output='' url='' arg
  while (($#)); do
    arg="$1"
    case "$arg" in
      --dump-header) dump="$2"; shift 2 ;;
      --output) output="$2"; shift 2 ;;
      --write-out) shift 2 ;;
      https://*) url="$arg"; shift ;;
      *) shift ;;
    esac
  done
  case "$url" in
{response_cases}
    *) return 1 ;;
  esac
  printf 'HTTP/2 %s\n' "$status" > "$dump"
  if [[ -n "$location" ]]; then printf 'Location: %s\n' "$location" >> "$dump"; fi
  printf '%s' "$body" > "$output"
  printf '%s' "$status"
}}
{_alias_helper()}
fetch_alias 'test alias' "$website_origin{requested_path}"
"""
    return subprocess.run(
        ["bash", "-c", script],
        check=False,
        capture_output=True,
        text=True,
        # The extracted helper shells out to `mktemp -d`, which trusts TMPDIR
        # blindly. `tempfile.gettempdir()` has already resolved a writable
        # fallback, so a sandboxed unwritable TMPDIR cannot fail the suite.
        env={**os.environ, "TMPDIR": tempfile.gettempdir()},
    )


_ALIAS_BODY = (
    '<title>DataPulse dataset register</title>\n'
    '<link rel="canonical" href="/">\n'
    '<meta http-equiv="refresh" content="0; url=/">\n'
    '<a href="/">DataPulse dataset register</a>\n'
)


def _declared_surface_helper() -> str:
    """Extract the declared-surface content gate for direct state-machine testing."""
    match = re.search(r"(?ms)^verify_declared_surface_content\(\) \{.*?^\}\n", _served_verifier())
    assert match is not None, "the declared-surface content gate must remain executable and contract-tested"
    return textwrap.dedent(match.group(0))


def _run_declared_surface_check(surface: str, body: str, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    """Run the workflow content gate against one deterministic served body."""
    body_path = tmp_path / "surface.body"
    body_path.write_text(body, encoding="utf-8")
    script = f"""
set -Eeuo pipefail
fail() {{ echo "::error title=Cloudflare Pages contract failed::$1" >&2; return 1; }}
{_declared_surface_helper()}
verify_declared_surface_content '{surface}' '{body_path}'
"""
    return subprocess.run(["bash", "-c", script], check=False, capture_output=True, text=True)


def test_alias_verifier_accepts_documented_html_normalization_chain() -> None:
    result = _run_alias_helper(
        "/landing.html",
        {
            "/landing.html": ("308", "/landing", ""),
            "/landing": ("200", "", _ALIAS_BODY),
        },
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("path", ("/landing", "/dashboard"))
def test_alias_verifier_accepts_direct_static_alias(path: str) -> None:
    result = _run_alias_helper(path, {path: ("200", "", _ALIAS_BODY)})
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("path", "response"),
    (
        ("/landing.html", ("308", "/index.html", "")),
        ("/landing.html", ("308", "/landing.html", "")),
        ("/landing.html", ("308", "https://evil.example/landing", "")),
        ("/landing", ("200", "/landing", _ALIAS_BODY)),
        ("/dashboard", ("200", "", '<title>dashboard SPA</title>')),
    ),
)
def test_alias_verifier_rejects_cycles_wrong_locations_and_spa_fallback(
    path: str, response: tuple[str, str, str]
) -> None:
    result = _run_alias_helper(path, {path: response})
    assert result.returncode != 0


def test_declared_surface_content_gate_rejects_spa_fallback_for_the_receipt_entry_point(tmp_path: Path) -> None:
    """HTTP 200 with the dashboard SPA fallback must fail the observation surface."""
    result = _run_declared_surface_check(
        "/observation-receipts/chain_head.json",
        "<!doctype html><html><head><title>DataPulse</title></head><body>SPA fallback</body></html>",
        tmp_path,
    )

    assert result.returncode != 0
    assert "datapulse/v1/observation-chain-head" in result.stderr


def test_declared_surface_content_gate_accepts_the_receipt_chain_head_json(tmp_path: Path) -> None:
    result = _run_declared_surface_check(
        "/observation-receipts/chain_head.json",
        json.dumps({"schema": "datapulse/v1/observation-chain-head", "head": "abc"}),
        tmp_path,
    )

    assert result.returncode == 0, result.stderr


def test_declared_surface_content_gate_rejects_json_without_the_declared_marker(tmp_path: Path) -> None:
    result = _run_declared_surface_check(
        "/observation-receipts/chain_head.json",
        json.dumps({"schema": "datapulse/v1/health-snapshot"}),
        tmp_path,
    )

    assert result.returncode != 0
    assert "datapulse/v1/observation-chain-head" in result.stderr


def test_declared_surface_content_gate_leaves_other_declared_surfaces_untouched(tmp_path: Path) -> None:
    result = _run_declared_surface_check("/health/latest.json", "<html>not json</html>", tmp_path)

    assert result.returncode == 0, result.stderr


def test_served_verifier_wires_the_receipt_entry_point_into_the_content_gate() -> None:
    verify = _served_verifier()

    assert "/observation-receipts/chain_head.json" in verify
    assert '.schema == "datapulse/v1/observation-chain-head"' in verify
    assert 'verify_declared_surface_content "$path" "$smoke_dir/surfaces${path%/}/index"' in verify


def test_health_only_path_is_selected_only_by_the_generated_output_classifier() -> None:
    """Commit messages must not choose a production deployment security mode."""
    workflow = _workflow()

    classify = workflow.split("      - id: classify\n", 1)[1].split("\n  sign_health:\n", 1)[0]
    assert "python3 scripts/classify_change.py" in classify
    assert "skip deploy" not in classify.lower()
    assert "head_commit.message" not in workflow
    assert "Embed canonical health dashboard (health-only path)" in workflow
    assert "if: needs.sign_health.outputs.health_only == 'true'" in workflow
    assert "if: needs.sign_health.outputs.health_only != 'true'" in workflow
    deploy_job = workflow.split("  deploy:\n", 1)[1].split("    steps:\n", 1)[0]
    assert (
        "if: needs.sign_health.outputs.accepted_head_state == 'accepted'"
    ) in deploy_job
    assert "Deploy canonical Cloudflare Pages artifact" in workflow


def test_publication_classifier_invocations_pass_no_profile_flags() -> None:
    # Both initial classification and re-settlement must preserve full receipt releases.
    workflow = yaml.safe_load(_workflow())
    invocations = [
        line.strip()
        for job in workflow["jobs"].values()
        for step in job.get("steps", [])
        for line in step.get("run", "").splitlines()
        if re.search(r"\bpython3\s+scripts/classify_change\.py\b", line)
    ]
    assert len(invocations) == 2
    assert all(line.endswith("python3 scripts/classify_change.py; then") for line in invocations)


def test_pages_concurrency_keeps_one_pending_deploy_candidate() -> None:
    workflow = yaml.safe_load(_workflow())

    # New arrivals replace pending deploys without canceling the active run.
    assert workflow["concurrency"] == {
        "group": "cloudflare-pages-deploy",
        "cancel-in-progress": False,
        "queue": "single",
    }
    assert "concurrency" not in workflow["jobs"]["sign_health"]
    assert "concurrency" not in workflow["jobs"]["deploy"]


def test_pages_resettlement_reuses_wait_and_exports_one_downstream_revision() -> None:
    workflow = yaml.safe_load(_workflow())
    jobs = workflow["jobs"]
    settlement = next(step for step in jobs["classify"]["steps"] if step.get("id") == "settled_main")
    guard = next(step for step in jobs["sign_health"]["steps"]
                 if step.get("name") == "Require settled main before signing")
    assert "main moved; re-settling" in guard["run"]
    assert guard["env"]["PROMOTION_SETTLE_RUN"] == settlement["run"]
    assert "max_attempts=2" in guard["run"]
    assert '"$attempts" -ge "$max_attempts"' in guard["run"]
    assert "attempts exhausted after $attempts attempts" in guard["run"]
    assert 'export PROMOTION_SOURCE_SHA="$settled_sha"' in guard["run"]
    assert 'git checkout --detach "$settled_sha"' in guard["run"]
    assert '"$GITHUB_ENV"' in guard["run"] and '"$GITHUB_OUTPUT"' in guard["run"]
    # Two complete waits, all three head reads, two verified checkouts, and
    # classification fit inside the watchdog, including each kill grace.
    ceiling = workflow["env"]["PROMOTION_SETTLED_MAX_WAIT_SECONDS"]
    assert 2 * (ceiling + 10 + 65 + 15 + 15 + 15 + 35 + 15) + 3 * 35 + 35 < guard["timeout-minutes"] * 60
    selected = "${{ needs.sign_health.outputs.settled_sha }}"
    assert jobs["sign_health"]["outputs"]["settled_sha"] == (
        "${{ steps.settled_main.outputs.settled_sha }}"
    )
    assert jobs["deploy"]["env"]["PROMOTION_SOURCE_SHA"] == selected
    checkout = next(step for step in jobs["deploy"]["steps"] if step.get("uses") == "actions/checkout@v4")
    assert checkout["with"]["ref"] == selected


@pytest.mark.parametrize(("sha", "reason"), [("a" * 40, "quiet"), ("b" * 40, "ceiling"), ("", "")])
def test_pages_logs_classify_promotion_source_before_consumption(sha: str, reason: str) -> None:
    steps = yaml.safe_load(_workflow())["jobs"]["classify"]["steps"]
    settlement = next(step for step in steps if step.get("id") == "settled_main")
    diagnostic = next(step for step in steps if step.get("name") == "Log promotion source resolution")
    checkout = next(step for step in steps if step.get("uses") == "actions/checkout@v4")
    assert steps.index(settlement) < steps.index(diagnostic) < steps.index(checkout)
    assert diagnostic["env"] == {
        "SETTLED_SHA": "${{ steps.settled_main.outputs.settled_sha }}",
        "SETTLEMENT_REASON": "${{ steps.settled_main.outputs.settlement_reason }}",
    }
    result = subprocess.run(
        ["bash", "-c", diagnostic["run"]], capture_output=True, text=True, check=True,
        env={**os.environ, "SETTLED_SHA": sha, "SETTLEMENT_REASON": reason},
    )
    assert result.stdout.splitlines() == [
        f"settled_sha={sha or '<empty>'}", f"settlement_reason={reason or '<empty>'}",
    ]


def test_pages_settlement_is_bounded_and_pins_the_promoted_revision() -> None:
    workflow = yaml.safe_load(_workflow())
    jobs = workflow["jobs"]
    steps = jobs["classify"]["steps"]
    settlement = next(
        (step for step in steps if step.get("name") == "Wait for settled main before promoting"),
        None,
    )
    assert settlement is not None, "Pages has no settlement step before signing"
    quiet = workflow["env"]["PROMOTION_SETTLED_QUIET_SECONDS"]
    ceiling = workflow["env"]["PROMOTION_SETTLED_MAX_WAIT_SECONDS"]
    assert str(quiet).isdigit() and str(ceiling).isdigit()
    assert int(quiet) == 300 and int(ceiling) == 900
    assert 0 < int(quiet) < int(ceiling)
    assert int(quiet) + int(ceiling) < jobs["sign_health"]["timeout-minutes"] * 60
    assert int(ceiling) + 10 < jobs["classify"]["timeout-minutes"] * 60
    assert jobs["sign_health"]["needs"] == "classify"
    assert steps.index(settlement) < next(i for i, step in enumerate(steps) if step.get("id") == "classify")
    run = settlement["run"]
    assert 'timeout -k 5s "$((PROMOTION_SETTLED_MAX_WAIT_SECONDS + 5))s" python3' in run
    assert '["timeout", "-k", "5s",' in run
    assert "timeout=call_budget" in run
    assert "time.monotonic()" in run
    assert 'commit["committer"]["date"]' in run
    assert "sha != previous_sha" in run
    assert 'reason = "ceiling"' in run and 'reason = "quiet"' in run
    assert 'settled_sha={sha}' in run and 'settlement_reason={reason}' in run
    assert "::warning title=Main settlement ceiling reached::" in run
    # There is one shell command and one subprocess call in the poll. Both
    # must keep their timeout wrappers; parsing catches additional bare calls.
    shell, source = run.split("<<'PY'\n", 1)
    assert len(shell.strip().splitlines()) == 2
    calls = [node for node in ast.walk(ast.parse(source.rsplit("\nPY", 1)[0]))
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
             and isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess"]
    assert len(calls) == 1 and calls[0].func.attr == "run"
    assert isinstance(calls[0].args[0], ast.List)
    assert [ast.literal_eval(item) for item in calls[0].args[0].elts[:3]] == ["timeout", "-k", "5s"]
    assert any(keyword.arg == "timeout" for keyword in calls[0].keywords)
    for job_name in ("sign_health", "deploy"):
        job = jobs[job_name]
        source_job = "classify" if job_name == "sign_health" else "sign_health"
        selected = "${{ needs." + source_job + ".outputs.settled_sha }}"
        checkout = next(step for step in job["steps"] if step.get("uses") == "actions/checkout@v4")
        assert checkout["with"]["ref"] == selected
        assert job["env"]["PROMOTION_SOURCE_SHA"] == selected
        assert all("$GITHUB_SHA" not in step.get("run", "") for step in job["steps"])
    assert jobs["classify"]["outputs"]["settled_sha"] == "${{ steps.settled_main.outputs.settled_sha }}"
    classifier = next(step for step in steps if step.get("id") == "classify")
    assert classifier["env"]["AFTER_SHA"] == "${{ steps.settled_main.outputs.settled_sha }}"
    guard = next(step for step in jobs["sign_health"]["steps"]
                 if step.get("name") == "Require settled main before signing")
    assert 'timeout -k 5s 30s gh api' in guard["run"]
    assert '"$current_sha" != "$PROMOTION_SOURCE_SHA"' in guard["run"]
    assert jobs["sign_health"]["steps"].index(guard) < next(
        i for i, step in enumerate(jobs["sign_health"]["steps"])
        if step.get("id") == "accepted_head"
    )


@pytest.mark.parametrize("scenario", ["already_quiet", "recent", "backdated_move", "confirmation_move", "busy", "lookup_failure"])
def test_pages_settlement_poll_exercises_quiet_ceiling_and_head_changes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], scenario: str,
) -> None:
    step = next(step for step in yaml.safe_load(_workflow())["jobs"]["classify"]["steps"]
                if step.get("id") == "settled_main")
    source = step["run"].split("<<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
    clock = [0.0]
    calls = []
    epoch = 1_800_000_000
    output = tmp_path / "output"

    class ClockDateTime(datetime):
        @classmethod
        def now(cls, tz: timezone | None = None) -> datetime:
            return datetime.fromtimestamp(epoch + clock[0], tz)

    def sleep(seconds: float) -> None:
        assert 0 <= seconds <= 15
        clock[0] += seconds
        assert clock[0] <= 900

    def read_head(command: list[str], **kwargs: object) -> SimpleNamespace:
        assert command[:3] == ["timeout", "-k", "5s"]
        assert command[4:6] == ["gh", "api"]
        assert command[6].endswith("/commits/refs/heads/main")
        call_budget = float(command[3].removesuffix("s"))
        assert 0 < call_budget <= min(30, 900 - clock[0])
        assert kwargs["timeout"] == call_budget + 6
        assert kwargs["check"] is True
        if scenario == "lookup_failure":
            raise subprocess.CalledProcessError(1, command, stderr="lookup unavailable")
        clock[0] += 0.25
        moved = ((scenario == "backdated_move" and clock[0] >= 60)
                 or (scenario == "confirmation_move" and bool(calls)))
        sha = ("b" if moved else "a") * 40
        timestamp = epoch if scenario == "recent" or (scenario == "backdated_move" and not moved) else epoch - 1000
        if scenario == "busy":
            revision = int(clock[0] // 31)
            sha = f"{revision:040x}"
            timestamp = epoch + revision * 31
        calls.append((clock[0], sha))
        date = datetime.fromtimestamp(timestamp, timezone.utc).isoformat()
        return SimpleNamespace(stdout=json.dumps({"sha": sha, "commit": {"committer": {"date": date}}}))

    modules = {
        "time": SimpleNamespace(monotonic=lambda: clock[0], sleep=sleep),
        "datetime": SimpleNamespace(datetime=ClockDateTime, timezone=timezone),
        "subprocess": SimpleNamespace(run=read_head),
        "os": SimpleNamespace(environ={
            "PROMOTION_SETTLED_QUIET_SECONDS": "300", "PROMOTION_SETTLED_MAX_WAIT_SECONDS": "900",
            "GITHUB_REPOSITORY": "fixture/datapulse", "GITHUB_OUTPUT": str(output),
        }),
    }

    def import_module(name: str, *args: object, **kwargs: object) -> object:
        return modules[name] if name in modules else builtins.__import__(name, *args, **kwargs)

    namespace = {"__builtins__": {**vars(builtins), "__import__": import_module}}
    if scenario == "lookup_failure":
        with pytest.raises(subprocess.CalledProcessError):
            exec(compile(source, str(WORKFLOW), "exec"), namespace)
        assert not output.exists()
        return
    exec(compile(source, str(WORKFLOW), "exec"), namespace)
    outputs = dict(line.split("=", 1) for line in output.read_text().splitlines())
    assert outputs["settled_sha"] == calls[-1][1]
    # Exercise the actual producer output through both YAML references into
    # the guard's shell, rather than injecting an unrelated fixture SHA.
    jobs = yaml.safe_load(_workflow())["jobs"]
    sha_reference = "${{ steps.settled_main.outputs.settled_sha }}"
    job_reference = "${{ needs.classify.outputs.settled_sha }}"
    references = {sha_reference: outputs["settled_sha"]}
    references[job_reference] = references[jobs["classify"]["outputs"]["settled_sha"]]
    guard = next(step for step in jobs["sign_health"]["steps"] if step.get("id") == "settled_main")
    selected_reference = guard["env"].get(
        "PROMOTION_SOURCE_SHA", jobs["sign_health"]["env"]["PROMOTION_SOURCE_SHA"],
    )
    result = subprocess.run(
        ["bash", "-c", guard["run"].split('initial_sha="$PROMOTION_SOURCE_SHA"', 1)[0]],
        capture_output=True, text=True,
        env={**os.environ, "PROMOTION_SOURCE_SHA": references[selected_reference]},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    if scenario == "busy":
        assert clock[0] == 900
        assert outputs["settled_sha"] == f"{int(clock[0] // 31):040x}"
        assert outputs["settlement_reason"] == "ceiling"
        assert "::warning title=Main settlement ceiling reached::" in capsys.readouterr().out
    else:
        assert outputs["settlement_reason"] == "quiet"
        assert clock[0] < 900
        if scenario == "already_quiet":
            assert len(calls) == 2 and clock[0] < 1
        elif scenario == "recent":
            assert clock[0] >= 300
        elif scenario == "backdated_move":
            assert clock[0] >= 360 and outputs["settled_sha"] == "b" * 40
        elif scenario == "confirmation_move":
            assert clock[0] >= 300 and outputs["settled_sha"] == "b" * 40


@pytest.mark.parametrize("scenario", [
    "stable", "once_health", "once_code", "repeated", "ceiling",
    "unreadable", "empty", "malformed", "settle_failure", "unidentified_settle", "missing_commit",
    "selected_empty", "selected_malformed", "history_rewrite",
])
def test_pages_resettlement_guard_exercises_recovery_and_fail_closed(
    tmp_path: Path, scenario: str,
) -> None:
    workflow = yaml.safe_load(_workflow())
    guard = next(step for step in workflow["jobs"]["sign_health"]["steps"]
                 if step.get("name") == "Require settled main before signing")
    remote = tmp_path / "remote"
    remote.mkdir()

    def git(*args: str, cwd: Path = remote) -> str:
        return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()

    git("init", "-q", "-b", "fixture")
    git("config", "user.name", "Fixture")
    git("config", "user.email", "fixture@example.invalid")
    for path in ("attestations/index.json", ".attestations/chain_head.json", "health/latest.json"):
        target = remote / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("{}")
    (remote / "scripts").mkdir()
    (remote / "scripts/classify_change.py").write_bytes((ROOT / "scripts/classify_change.py").read_bytes())
    (remote / "scripts/restore_attestations.sh").write_bytes(
        (ROOT / "scripts/restore_attestations.sh").read_bytes()
    )
    shas = []
    for index in range(4):
        if index == 1 and scenario == "history_rewrite":
            git("checkout", "-q", "--orphan", "rewritten")
        (remote / "health/latest.json").write_text(json.dumps({"revision": index}))
        if index == 1 and scenario == "once_code":
            (remote / "source.py").write_text("# source change\n")
        git("add", ".")
        git("commit", "-qm", f"fixture {index}")
        shas.append(git("rev-parse", "HEAD"))
    checkout = tmp_path / "checkout"
    git("clone", "-q", str(remote), str(checkout))
    git("checkout", "-q", "--detach", shas[0], cwd=checkout)
    # Exercise replacing the earlier step's accepted-evidence overlay too.
    (checkout / "attestations/index.json").write_text('{"imported": true}')
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(textwrap.dedent("""\
        #!/usr/bin/env python3
        import json, os, pathlib, sys
        scenario = os.environ['GUARD_SCENARIO']
        heads = json.loads(os.environ['GUARD_HEADS'])
        counter = pathlib.Path(os.environ['GUARD_COUNTER'])
        reads = int(counter.read_text()) if counter.exists() else 0
        endpoint = sys.argv[2]
        if '/git/ref/' in endpoint:
            if scenario == 'unreadable':
                sys.exit(1)
            head = heads[min(reads, len(heads) - 1)]
            counter.write_text(str(reads + 1))
            print(head)
        else:
            if scenario == 'settle_failure':
                sys.exit(1)
            head = heads[min(max(0, reads - 1), len(heads) - 1)]
            print(json.dumps({'sha': head, 'commit': {'committer': {'date': '2000-01-01T00:00:00Z'}}}))
        """))
    gh.chmod(0o755)
    heads = [shas[0]] if scenario == "stable" else [shas[1]]
    if scenario == "repeated":
        heads = shas[1:]
    elif scenario in ("empty", "malformed", "missing_commit"):
        heads = [{"empty": "", "malformed": "not-a-sha", "missing_commit": "f" * 40}[scenario]]
    wait = guard["env"]["PROMOTION_SETTLE_RUN"]
    if scenario in ("ceiling", "unidentified_settle"):
        sha = shas[1] if scenario == "ceiling" else "invalid"
        reason = "ceiling" if scenario == "ceiling" else "quiet"
        wait = f'printf "settled_sha={sha}\\nsettlement_reason={reason}\\n" >> "$GITHUB_OUTPUT"'
    output, environment = tmp_path / "output", tmp_path / "environment"
    selected = {"selected_empty": "", "selected_malformed": "invalid"}.get(scenario, shas[0])
    result = subprocess.run(
        ["bash", "-c", guard["run"]], cwd=checkout, capture_output=True, text=True, timeout=15,
        env={**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}",
             "GITHUB_REPOSITORY": "fixture/datapulse", "PROMOTION_SOURCE_SHA": selected,
             "PROMOTION_HEALTH_ONLY": "true", "PROMOTION_SETTLE_RUN": wait,
             "PROMOTION_SETTLED_QUIET_SECONDS": "1", "PROMOTION_SETTLED_MAX_WAIT_SECONDS": "3",
             "GITHUB_OUTPUT": str(output), "GITHUB_ENV": str(environment), "RUNNER_TEMP": str(tmp_path),
             "GUARD_SCENARIO": scenario, "GUARD_HEADS": json.dumps(heads),
             "GUARD_COUNTER": str(tmp_path / "reads")},
    )
    if scenario in ("stable", "once_health", "once_code"):
        assert result.returncode == 0, result.stdout + result.stderr
        expected = shas[0] if scenario == "stable" else shas[1]
        outputs = dict(line.split("=", 1) for line in output.read_text().splitlines())
        assert outputs == {"settled_sha": expected, "health_only": "false" if scenario == "once_code" else "true"}
        assert environment.read_text() == f"PROMOTION_SOURCE_SHA={expected}\n"
        assert git("rev-parse", "HEAD", cwd=checkout) == expected
        if scenario == "stable":
            assert "re-settling" not in result.stdout
            assert "after 0 re-settle attempts" in result.stdout
        else:
            assert f"main moved; re-settling {shas[0]} -> {shas[1]}" in result.stdout
            assert f"Re-settled promotion revision: {shas[0]} -> {shas[1]}" in result.stdout
            assert "after 1 re-settle attempts" in result.stdout
            assert json.loads((checkout / "health/latest.json").read_text()) == {"revision": 1}
            assert (checkout / "attestations/index.json").read_text() == "{}"
    else:
        assert result.returncode != 0, result.stdout + result.stderr
        assert not output.exists() and not environment.exists()
        if scenario in ("repeated", "ceiling"):
            assert "attempts exhausted after 2 attempts" in result.stderr
            assert result.stdout.count("main moved; re-settling") == 2
        elif scenario in ("unreadable", "empty", "malformed"):
            assert "Unidentified main revision" in result.stderr
        elif scenario == "settle_failure":
            assert "Main re-settlement failed" in result.stderr
        elif scenario == "unidentified_settle":
            assert "Unidentified re-settled revision" in result.stderr
        elif scenario in ("selected_empty", "selected_malformed"):
            assert "Unidentified promotion revision" in result.stderr
        elif scenario in ("missing_commit", "history_rewrite"):
            assert "Unverified main revision" in result.stderr


def test_attestation_state_machine_fails_closed_outside_health_only_signer_degradation() -> None:
    """Unsigned health publication preserves verified served attestations."""
    workflow = _workflow()
    parsed = yaml.safe_load(workflow)
    sign_job = parsed["jobs"]["sign_health"]
    deploy_steps = parsed["jobs"]["deploy"]["steps"]

    assert sign_job["outputs"]["attestation_state"] == "${{ steps.attestation_result.outputs.state }}"
    assert "DATAPULSE_ALLOW_UNATTESTED_HEALTH" not in workflow
    assert "--allow-unattested-health" not in workflow
    assert workflow.count("continue-on-error: true") == 1
    assert "Attempt pinned Cosign signer installation for health-only degradation" in workflow
    assert "Require signed attestation for full release" in workflow
    full_release_gate = next(
        step for step in deploy_steps if step.get("name") == "Require signed attestation for full release"
    )
    assert full_release_gate["if"] == (
        "needs.sign_health.outputs.health_only != 'true' && "
        "needs.sign_health.outputs.attestation_state != 'signed'"
    )
    assert "signer_down" in full_release_gate["run"]
    preserve = next(
        step for step in deploy_steps if step.get("name") == "Preserve served attestation plane (health-only path)"
    )
    assert preserve["if"] == (
        "needs.sign_health.outputs.health_only == 'true' && "
        "needs.sign_health.outputs.attestation_state == 'signer_down'"
    )


def test_health_cycle_classifier_accepts_verified_multifile_commit_c9a2b943() -> None:
    """A complete health cycle is eligible for the dashboard self-healing path."""
    assert _classifies_as_health_only(
        (
            "attestations/latest/scores.json",
            "catalog-graph.json",
            "catalog-snapshot.json",
            "changelog.json",
            "feed.xml",
            "health/drift.json",
            "health/evidence-coverage.json",
            "health/latest.json",
            "health/reconciliation.json",
            "health/trends.json",
            "record-evidence/pharmaceutical_products/latest.json",
        )
    )


def test_health_cycle_classifier_accepts_verified_multifile_commit_3215ef3b() -> None:
    """The minimal verified health cycle is also eligible for the fast path."""
    assert _classifies_as_health_only(
        (
            "attestations/latest/scores.json",
            "health/latest.json",
            "record-evidence/pharmaceutical_products/latest.json",
        )
    )


def test_health_cycle_classifier_fails_closed_for_mixed_source_and_health_input() -> None:
    """A source change forces the release profile even when health/latest.json changes."""
    assert not _classifies_as_health_only(("datapulse.json", "health/latest.json"))


def test_observation_receipt_changes_select_the_full_release_profile() -> None:
    """Observation receipts are site inputs: a receipts change is never health-only."""
    assert not _classifies_as_health_only(("observation-receipts/chain_head.json",))
    assert not _classifies_as_health_only(
        ("observation-receipts/days/2026-09-18.json", "health/latest.json")
    )


@pytest.mark.parametrize(
    "disallowed_path",
    (
        ".github/workflows/ci.yml",
        "docs/health-methodology.md",
        "unrecognized/generated-output.json",
        "health/unrecognized.json",
        "record-evidence/pharmaceutical_products/nested/latest.json",
        "attestations/latest/unrecognized.json",
        ".attestations/latest/not-json.txt",
        "deltas/not-json.txt",
    ),
)
def test_health_cycle_classifier_fails_closed_outside_generated_ownership(disallowed_path: str) -> None:
    """Workflow, hand-authored, and unknown paths must select the release profile."""
    assert not _classifies_as_health_only(("health/latest.json", disallowed_path))


def test_native_pages_uses_only_canonical_health_input_and_regenerates_embed() -> None:
    workflow = _workflow()
    fast_path = workflow.split("      - name: Embed canonical health dashboard (health-only path)\n", 1)[1].split(
        "      - name: Run release-build generation profile (non-health path)\n", 1
    )[0]

    assert "python3 scripts/embed_dashboard_data.py --health health/latest.json" in fast_path
    assert "health/trends.json" not in fast_path
    assert "health/drift.json" not in fast_path
    assert "health/reconciliation.json" not in fast_path
    assert "curl " not in fast_path


def test_native_pages_preserves_full_release_build_and_surface_contract() -> None:
    workflow = _workflow()

    assert "bash scripts/generate.sh release-build" in workflow
    assert "python3 scripts/verify_release_reproducible.py" in workflow
    assert "bash scripts/verify_release_invariants.sh" in workflow
    for copy in (
        "cp -R docs/. _site/",
        "cp llms.txt robots.txt sitemap.xml feed.xml",
        "cp -R health deltas record-evidence badges samples data _site/",
        "if [ -d observation-receipts ]; then cp -R observation-receipts _site/; fi",
        "cp -R attestations _site/",
        "cp -R .attestations _site/",
    ):
        assert copy in workflow
    assert "test \"$(grep -c '[^[:space:]]' _site/_redirects)\" -ge 4" in workflow
    for redirect_rule in (
        "/methodology /health-methodology 301",
        "/trust-contract /trust-contract.md 301",
        "/okf/ /okf/index.md 301",
        "/okf /okf/index.md 301",
    ):
        assert f"grep -qxF '{redirect_rule}' _site/_redirects" in workflow
    assert "cat _site/" + '_redirects)" = ' not in workflow
    verifier = _served_verifier()
    assert 'fetch_alias landing.html "$base_url/landing.html"' in verifier
    assert 'fetch_alias landing "$base_url/landing"' in verifier
    assert 'fetch_alias dashboard "$base_url/dashboard"' in verifier
    assert "normalized alias redirects again" in verifier


def test_pages_assembly_includes_bounded_public_summary_artifact() -> None:
    """The explicit root-file copy list must publish the advertised summary."""
    steps = yaml.safe_load(_workflow())["jobs"]["deploy"]["steps"]
    assemble = next(step for step in steps if step.get("name") == "Assemble canonical Pages artifact")
    root_file_copy = next(command for command in assemble["run"].splitlines() if command.startswith("cp llms.txt"))

    assert "datapulse_summary.json" in root_file_copy


def test_health_latest_json_cache_rule_is_effective() -> None:
    """Pin the ``_headers`` cache contract for the served health snapshot.

    The rule must use the ``/health/latest.json*`` splat form and keep the exact
    300-second TTL with stale-while-revalidate, so no edit silently drops the
    health snapshot to a shorter or absent edge cache. Cloudflare does not apply
    ``_headers`` to the Pages Function that also serves this path
    (``functions/health/[[path]].js``); the served header is owned there, and
    this test pins the static-layer half of the contract.
    """
    lines = (ROOT / "docs/_headers").read_text(encoding="utf-8").splitlines()

    assert "/health/latest.json*" in lines
    assert "/health/latest.json" not in lines
    rule_index = lines.index("/health/latest.json*")
    assert lines[rule_index + 1].strip() == (
        "Cache-Control: public, max-age=300, stale-while-revalidate=60"
    )

    # The catch-all discovery block and the asset cache rule must both survive.
    assert (
        '  Link: </.well-known/ard.json>; rel="ard", '
        '</.well-known/ai-catalog.json>; rel="ai-catalog"' in lines
    )
    assets_index = lines.index("/assets/*")
    assert lines[assets_index + 1].strip() == "Cache-Control: public, max-age=86400"


def test_health_only_legacy_release_proof_accepts_generated_and_verified_timestamps() -> None:
    workflow = _workflow()
    preserve_step = workflow.split(
        "      - name: Preserve served release proof (health-only path)\n", 1
    )[1].split("      - name: Preserve served attestation plane (health-only path)\n", 1)[0]
    match = re.search(r'"verification timestamp": r"([^"]+)"', preserve_step)
    assert match is not None
    pattern = match.group(1)

    assert re.search(pattern, "- Generated at: `2026-08-29T10:27:58+00:00`\n", re.MULTILINE)
    assert re.search(pattern, "- Verified at: `2026-08-29T10:27:58+00:00`\n", re.MULTILINE)


def test_final_health_only_release_proof_check_accepts_both_timestamp_forms_fail_closed() -> None:
    workflow = _workflow()
    match = re.search(r"'verification timestamp':r'([^']+)'", _served_verifier())
    assert match is not None
    pattern = match.group(1)

    for timestamp in ("Generated", "Verified"):
        assert re.search(pattern, f"- {timestamp} at: `2026-08-29T10:27:58+00:00`", re.MULTILINE)
    for malformed in (
        "- generated at: `2026-08-29T10:27:58+00:00`",
        "- Generated at: 2026-08-29T10:27:58+00:00",
        "- Generated at: `not-a-timestamp`\nextra",
    ):
        assert re.search(pattern, malformed, re.MULTILINE) is None


def test_health_only_signed_sigstore_bundle_skips_legacy_plane_preservation() -> None:
    """A fresh verified bundle must not be blocked by a stale served plane."""
    steps = yaml.safe_load(_workflow())["jobs"]["deploy"]["steps"]
    preserve = next(
        step for step in steps if step.get("name") == "Preserve served attestation plane (health-only path)"
    )
    download = next(step for step in steps if step.get("name") == "Download verified optional Sigstore bundle")
    assemble = next(step for step in steps if step.get("name") == "Assemble canonical Pages artifact")

    assert preserve["if"] == (
        "needs.sign_health.outputs.health_only == 'true' && "
        "needs.sign_health.outputs.attestation_state == 'signer_down'"
    )
    assert download["if"] == (
        "needs.sign_health.outputs.signed == 'true' || "
        "needs.sign_health.outputs.receipts_signed == 'true'"
    )
    for artifact in (
        "health.latest.sigstore.json",
        "health.latest.statement.json",
        "chain_head.json",
        "datapulse.json",
    ):
        assert f'test -s "$RUNNER_TEMP/sigstore-publication/{artifact}"' in assemble["run"]
        assert f'cp "$RUNNER_TEMP/sigstore-publication/{artifact}" _site/signatures/' in assemble["run"]


def test_health_only_signer_down_path_preserves_only_a_verified_served_plane() -> None:
    """Absent a fresh bundle, corrupt served evidence must remain deployment-blocking."""
    steps = yaml.safe_load(_workflow())["jobs"]["deploy"]["steps"]
    preserve = next(
        step for step in steps if step.get("name") == "Preserve served attestation plane (health-only path)"
    )
    assemble = next(step for step in steps if step.get("name") == "Assemble canonical Pages artifact")

    assert "python3 scripts/verify_attestation_plane_state.py --planedir \"$preserved_root\"" in preserve["run"]
    assert "served health/binding plane is inconsistent" in preserve["run"]
    assert "rm -f _site/attestations/latest/binding.json" in assemble["run"]


def test_served_rekor_references_are_limited_to_the_binding_day_directory(tmp_path: Path) -> None:
    """Preservation accepts the documented Rekor layout without widening fetches."""
    steps = yaml.safe_load(_workflow())["jobs"]["deploy"]["steps"]
    preserve = next(
        step for step in steps if step.get("name") == "Preserve served attestation plane (health-only path)"
    )
    assert 'python3 scripts/attestation_fetch_refs.py --root "$preserved_root" --proofs' in preserve["run"]
    directory = "attestations/2026-09-15"
    (tmp_path / "attestations/latest").mkdir(parents=True)
    (tmp_path / directory).mkdir()
    (tmp_path / "attestations/latest/index.json").write_text(json.dumps({"chain_head_ref": directory + "/chain_head.json"}))
    (tmp_path / "attestations/chain-index.json").write_text(json.dumps({"schema": "datapulse/v1/chain-index"}))
    binding = tmp_path / directory / "binding.json"
    for reference in (
        "attestations/rekor/2026-09-15/reference.json",
        "attestations/rekor/2026-09-15/health.sigstore.bundle.json",
        "attestations/2026-09-15/reference.json",
    ):
        binding.write_text(json.dumps({"payload": {"date": "2026-09-15"}, "rekor": {"reference_ref": reference}}))
        assert fetch_refs(tmp_path, proofs=True) == [reference]
    for reference in (
        "attestations/rekor/2026-09-15/../reference.json",
        "attestations/rekor/not-a-date/reference.json",
        "/attestations/rekor/2026-09-15/reference.json",
        "attestations/rekor/2026-09-15/nested/reference.json",
        "attestations/rekor/2026-09-16/reference.json",
    ):
        binding.write_text(json.dumps({"payload": {"date": "2026-09-15"}, "rekor": {"reference_ref": reference}}))
        with pytest.raises(ValueError, match="unsafe Rekor proof reference"):
            fetch_refs(tmp_path, proofs=True)


def test_native_pages_installs_release_dependencies_before_generation() -> None:
    parsed = yaml.safe_load(_workflow())
    steps = parsed["jobs"]["deploy"]["steps"]
    install_index = next(
        index for index, step in enumerate(steps) if step.get("name") == "Install release verification dependencies"
    )
    release_build_index = next(
        index for index, step in enumerate(steps) if step.get("name") == "Run release-build generation profile (non-health path)"
    )
    install_step = steps[install_index]

    assert install_index < release_build_index
    assert install_step["if"] == "needs.sign_health.outputs.health_only != 'true'"
    assert install_step["run"] == (
        "python -m pip install jsonschema --requirement mcp/requirements.txt "
        "'datacontract-cli[duckdb]==0.12.5'"
    )


def test_native_pages_runs_contract_validation_only_for_full_releases() -> None:
    """Contract drift blocks release builds but never a health-only publication."""
    steps = yaml.safe_load(_workflow())["jobs"]["deploy"]["steps"]
    validation = next(step for step in steps if step.get("name") == "Validate DataPulse contract (non-health path)")

    assert validation["if"] == "needs.sign_health.outputs.health_only != 'true'"
    assert validation["run"] == "bash scripts/run_datacontract_validation.sh"


def test_native_pages_installs_pinned_pandoc_before_non_health_release_build() -> None:
    parsed = yaml.safe_load(_workflow())
    steps = parsed["jobs"]["deploy"]["steps"]
    pandoc_index = next(
        index for index, step in enumerate(steps) if step.get("name") == "Install Pandoc"
    )
    release_build_index = next(
        index
        for index, step in enumerate(steps)
        if step.get("name") == "Run release-build generation profile (non-health path)"
    )
    pandoc_step = steps[pandoc_index]

    assert pandoc_index < release_build_index
    assert pandoc_step["if"] == "needs.sign_health.outputs.health_only != 'true'"
    assert pandoc_step["run"].splitlines() == [
        "sudo apt-get update",
        "sudo apt-get install -y pandoc=3.1.3+ds-2",
        "pandoc --version | sed -n '1p'",
    ]


def test_native_pages_scopes_attestation_key_setup_to_non_health_release_build() -> None:
    parsed = yaml.safe_load(_workflow())
    steps = parsed["jobs"]["deploy"]["steps"]
    health_step = next(
        step for step in steps if step.get("name") == "Embed canonical health dashboard (health-only path)"
    )
    release_step = next(
        step for step in steps if step.get("name") == "Run release-build generation profile (non-health path)"
    )
    verify_step = next(
        step for step in steps if step.get("name") == "Verify full release contract (non-health path)"
    )

    secret_expression = "${{ secrets.DATAPULSE_ATTESTATION_PRIVATE_KEY_FILE }}"
    release_run = release_step["run"]
    verify_run = verify_step["run"]
    assert release_step["if"] == "needs.sign_health.outputs.health_only != 'true'"
    assert verify_step["if"] == "needs.sign_health.outputs.health_only != 'true'"
    assert release_step["env"] == {
        "DATAPULSE_ATTESTATION_PRIVATE_KEY_CONTENT": secret_expression,
    }
    assert verify_step["env"] == {
        "DATAPULSE_ATTESTATION_PRIVATE_KEY_CONTENT": secret_expression,
    }
    assert secret_expression not in release_run
    assert secret_expression not in verify_run
    assert secret_expression not in health_step.get("run", "")
    assert "DATAPULSE_ATTESTATION_PRIVATE_KEY_CONTENT" not in health_step
    assert _workflow().count(secret_expression) == 2

    setup = (
        'if [[ -n "$DATAPULSE_ATTESTATION_PRIVATE_KEY_CONTENT" ]]; then',
        'echo "$DATAPULSE_ATTESTATION_PRIVATE_KEY_CONTENT" > /tmp/datapulse-attestation-key.json',
        "chmod 600 /tmp/datapulse-attestation-key.json",
        "export DATAPULSE_ATTESTATION_PRIVATE_KEY_FILE=/tmp/datapulse-attestation-key.json",
    )
    positions = [release_run.index(line) for line in setup]
    assert positions == sorted(positions)
    assert release_run.index("bash scripts/generate.sh release-build") > positions[-1]
    verify_positions = [verify_run.index(line) for line in setup]
    assert verify_positions == sorted(verify_positions)
    invocations = (
        "python3 scripts/verify_release_reproducible.py",
        "bash scripts/verify_release_invariants.sh --local",
    )
    assert all(verify_run.index(invocation) > verify_positions[-1] for invocation in invocations)
    assert "-----BEGIN" not in _workflow()


def test_native_pages_uses_only_cloudflare_secrets_and_project() -> None:
    workflow = _workflow()
    parsed = yaml.safe_load(workflow)

    assert parsed["permissions"] == {"contents": "read"}
    assert "cloudflare/wrangler-action@v3" not in workflow
    assert "npx --yes wrangler@3.90.0" in workflow
    assert "pages deploy _site --project-name=datapulse-p4b-preview --branch=main" in workflow
    assert "secrets.CLOUDFLARE_API_TOKEN" in workflow
    assert "secrets.CLOUDFLARE_ACCOUNT_ID" in workflow
    assert "secrets.DATAPULSE_ATTESTATION_PRIVATE_KEY_FILE" in workflow
    assert "actions/deploy-pages" not in workflow
    assert "pages: write" not in workflow


def test_native_pages_stages_and_verifies_the_assembled_artifact_before_production() -> None:
    """The exact assembled artifact must pass preview invariants before promotion."""
    steps = yaml.safe_load(_workflow())["jobs"]["deploy"]["steps"]
    assemble_index = next(
        index for index, step in enumerate(steps)
        if step.get("name") == "Assemble canonical Pages artifact"
    )
    staging_index = next(
        index for index, step in enumerate(steps)
        if step.get("name") == "Deploy isolated Cloudflare Pages preview artifact"
    )
    preview_index = next(
        index for index, step in enumerate(steps)
        if step.get("name") == "Verify isolated Pages preview before production promotion"
    )
    production_index = next(
        index for index, step in enumerate(steps)
        if step.get("name") == "Deploy canonical Cloudflare Pages artifact"
    )

    staging = steps[staging_index]
    preview = steps[preview_index]
    production = steps[production_index]
    staging_command = staging["run"]
    preview_run = preview["run"]

    assert assemble_index < staging_index < preview_index < production_index
    assert staging["id"] == "deploy_preview"
    assert "pages deploy _site --project-name=datapulse-p4b-preview" in staging_command
    assert re.search(r"--branch=staging(?:\s|$)", staging_command)
    assert "github.run_id" not in staging_command
    assert "GITHUB_RUN_ID" not in staging_command
    assert "--branch=main" not in staging_command
    assert "data-pulse.my" not in staging_command
    assert "www.data-pulse.my" not in staging_command
    assert "if" not in preview
    assert 'preview_branch="staging"' in preview_run
    assert "GITHUB_RUN_ID" not in preview_run
    assert 'preview_origin="https://${preview_branch}.datapulse-p4b-preview.pages.dev"' in preview_run
    assert "bash scripts/verify_served_release.sh" in preview_run
    assert '--base-url "$preview_origin"' in preview_run
    assert '--sigstore-signed "${{ needs.sign_health.outputs.signed }}"' in preview_run
    assert '--sigstore-publication "$RUNNER_TEMP/sigstore-publication"' in preview_run
    assert "verify_release_invariants.sh" not in preview_run
    assert production["id"] == "deploy"
    assert "pages deploy _site --project-name=datapulse-p4b-preview --branch=main" in production["run"]


def test_native_pages_binds_preview_and_promotion_to_one_release_artifact_manifest() -> None:
    """No `_site` generation may occur after its temp-only inventory is recorded."""
    steps = yaml.safe_load(_workflow())["jobs"]["deploy"]["steps"]
    asset_guard_index = next(
        index for index, step in enumerate(steps)
        if step.get("name") == "Exclude oversized Pages assets before upload"
    )
    manifest_create_index = next(
        index for index, step in enumerate(steps)
        if step.get("name") == "Record deterministic release artifact manifest"
    )
    preview_verify_index = next(
        index for index, step in enumerate(steps)
        if step.get("name") == "Verify release artifact before preview deployment"
    )
    preview_served_index = next(
        index for index, step in enumerate(steps)
        if step.get("name") == "Verify isolated Pages preview before production promotion"
    )
    post_preview_verify_index = next(
        index for index, step in enumerate(steps)
        if step.get("name") == "Verify release artifact after preview served verification"
    )
    promotion_verify_index = next(
        index for index, step in enumerate(steps)
        if step.get("name") == "Verify release artifact before canonical production deployment"
    )
    production_index = next(
        index for index, step in enumerate(steps)
        if step.get("name") == "Deploy canonical Cloudflare Pages artifact"
    )

    selection_index = next(
        index for index, step in enumerate(steps)
        if step.get("name") == "Keep verifier-reachable attestation history"
    )
    projection_guard_index = next(
        index for index, step in enumerate(steps)
        if step.get("name") == "Require served projections from committed main"
    )
    ceiling_guard_index = next(
        index for index, step in enumerate(steps)
        if step.get("name") == "Guard Cloudflare Pages file ceiling"
    )
    assert selection_index == next(
        index for index, step in enumerate(steps)
        if step.get("name") == "Assemble canonical Pages artifact"
    ) + 1
    assert projection_guard_index == selection_index + 1
    assert asset_guard_index == projection_guard_index + 1
    assert ceiling_guard_index == asset_guard_index + 1
    assert manifest_create_index == ceiling_guard_index + 1
    assert "set -Eeuo pipefail" in steps[asset_guard_index]["run"]
    assert "python3 scripts/check_pages_asset_sizes.py _site" in steps[asset_guard_index]["run"]
    assert preview_verify_index < next(
        index for index, step in enumerate(steps)
        if step.get("name") == "Deploy isolated Cloudflare Pages preview artifact"
    )
    assert preview_served_index + 1 == post_preview_verify_index
    assert post_preview_verify_index + 1 == promotion_verify_index
    assert promotion_verify_index + 1 == production_index

    manifest_path = '"$RUNNER_TEMP/release-artifact-manifest.json"'
    lifecycle_indices = (
        manifest_create_index,
        preview_verify_index,
        post_preview_verify_index,
        promotion_verify_index,
    )
    for index in lifecycle_indices:
        run = steps[index]["run"]
        assert "python3 scripts/verify_release_artifact.py" in run
        assert manifest_path in run
        assert '--source-commit "$PROMOTION_SOURCE_SHA"' in run
    assert " create " in steps[manifest_create_index]["run"]
    assert all(" verify " in steps[index]["run"] for index in lifecycle_indices[1:])

    for step in steps[manifest_create_index + 1 :]:
        run = step.get("run", "")
        assert "scripts/generate.sh" not in run
        assert "scripts/embed_dashboard_data.py" not in run
        assert "scripts/gen_" not in run


def test_post_deploy_verification_rejects_timestamp_count_and_surface_drift() -> None:
    workflow = _workflow()
    verify = _served_verifier()

    assert 'fetch "dataset register" "$base_url/" "$smoke_dir/index.html"' in verify
    assert 'fetch_alias landing.html "$base_url/landing.html"' in verify
    assert 'fetch_alias landing "$base_url/landing"' in verify
    assert 'fetch_alias dashboard "$base_url/dashboard"' in verify
    assert 'normalized alias redirects again' in verify
    assert 'DataPulse dataset register' in verify
    assert 'expected_dataset_count="$(jq -er' in verify
    assert '"$site_dir/datapulse.json"' in verify
    assert '[[ "$observed_register_rows" -eq "$expected_dataset_count" ]]' in verify
    assert "origin root register rows mismatch: expected $expected_dataset_count, observed $observed_register_rows" in verify
    assert "389 register rows" not in verify
    assert "'/health/index.json'" in verify
    assert 'fetch "health snapshot" "$base_url/health/latest.json"' in verify
    assert 'fetch "dashboard health projection" "$base_url/health/index.json" "$smoke_dir/health/index.json"' in verify
    assert 'for path in "${pages[@]}" "${artifacts[@]}"' in verify
    assert "dashboard health projection is older than served health/latest.json" in verify
    assert "dashboard health projection dataset count differs from served health/latest.json" in verify
    assert "dashboard health projection dataset IDs differ from served health/latest.json" in verify
    assert "--proto '=https'" in verify
    assert "--retry-all-errors" in verify
    assert "exit 1" in verify
    assert "projection['checked_at'] < health['checked_at']" in verify


def test_sign_health_verifies_accepted_head_before_statement_and_cosign() -> None:
    steps = yaml.safe_load(_workflow())["jobs"]["sign_health"]["steps"]
    names = [step.get("name") for step in steps]
    guard = next(step for step in steps if step.get("id") == "accepted_head")
    assert "if" not in guard and "continue-on-error" not in guard
    assert names.index(guard["name"]) < names.index("Generate deterministic health attestation statement")
    assert names.index("Generate deterministic health attestation statement") < names.index("Sign and verify current health DSSE bundle")
    assert 'verify_contract(root, require_rekor=True, allow_newer_health=False)' in guard["run"]


def test_health_only_signed_artifact_carries_and_overlays_the_generated_attestation_plane() -> None:
    """Health-only deployment must publish the generated sign-time trust plane."""
    workflow = _workflow()
    sign_health = workflow.split("  sign_health:\n", 1)[1].split("\n  deploy:\n", 1)[0]
    upload = next(
        step
        for step in yaml.safe_load(_workflow())["jobs"]["sign_health"]["steps"]
        if step.get("name") == "Upload verified Sigstore bundle"
    )
    sign_step = sign_health.split("      - name: Sign and verify current health DSSE bundle\n", 1)[1].split(
        "      - name: Stage statement into Sigstore publication\n", 1
    )[0]
    assemble = workflow.split("      - name: Assemble canonical Pages artifact\n", 1)[1].split(
        "      - name: Deploy canonical Cloudflare Pages artifact\n", 1
    )[0]

    assert 'test -s attestations/latest/chain_head.json' in sign_step
    assert 'test -s attestations/latest/index.json' in sign_step
    assert 'test -s attestations/latest/scores.json' in sign_step
    assert 'test -s attestations/latest/binding.json' in sign_step
    assert 'test -s .attestations/chain_head.json' in sign_step
    assert 'test -s "$publication/datapulse.json"' in sign_step
    assert 'cp -R attestations "$publication/attestations"' in sign_step
    assert 'cp -R .attestations "$publication/.attestations"' in sign_step
    assert upload["with"]["include-hidden-files"] is True

    # Full releases also publish the accepted sign-time head and manifest.
    overlay_condition = 'if [[ "${{ needs.sign_health.outputs.signed }}" == "true" ]]; then'
    assert overlay_condition in assemble
    assert 'test -s "$RUNNER_TEMP/sigstore-publication/datapulse.json"' in assemble
    assert 'test -s "$RUNNER_TEMP/sigstore-publication/attestations/latest/chain_head.json"' in assemble
    assert 'rm -rf _site/attestations' in assemble
    assert 'rm -rf _site/.attestations' in assemble
    assert 'cp "$RUNNER_TEMP/sigstore-publication/datapulse.json" _site/datapulse.json' in assemble
    assert 'cp -R "$RUNNER_TEMP/sigstore-publication/attestations" _site/' in assemble
    assert 'cp -R "$RUNNER_TEMP/sigstore-publication/.attestations" _site/' in assemble


def test_refresh_chain_head_script_fails_closed_without_a_signing_key() -> None:
    """Missing key material must stop the refresh before any repository state changes."""
    env = {key: value for key, value in os.environ.items() if key != "DATAPULSE_ATTESTATION_PRIVATE_KEY_FILE"}
    result = subprocess.run(
        ["bash", "scripts/refresh_chain_head.sh"],
        check=False,
        env=env,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    assert result.returncode != 0
    assert "DATAPULSE_ATTESTATION_PRIVATE_KEY_FILE" in result.stderr
    assert "gen_attestations" not in result.stdout
