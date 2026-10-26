#!/usr/bin/env python3
"""Exercise acceptance waiting against real local Git authorities and signed sets."""
from __future__ import annotations

from datetime import timedelta
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import textwrap
from types import SimpleNamespace

import pytest
import yaml

from scripts import gen_attestations as ga
from scripts import verify_attestation_append as verifier
from scripts.tests.test_append_set_isolation import NOW, accept, git
from scripts.tests.test_attestations import fixture_root


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/deploy-cloudflare-pages.yml"


def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text())


def run_wait(
    tmp_path: Path, *, early: bool = False, check: str = "SUCCESS",
    merged: bool = False, proof: int = 75, outer_timeout: bool = False,
    lookup_status: int = 0, new_submission: bool = False, merge_at: int = 2,
    patience: int = 0,
) -> tuple[subprocess.CompletedProcess[str], str, str]:
    """Run the shipped shell; replace only network, Git and expensive proofs."""
    steps = workflow()["jobs"]["sign_health"]["steps"]
    name = ("Wait for an existing append before generating a candidate" if early else
            "Require authoritative acceptance before signing publication")
    step = next(step for step in steps if step.get("name") == name)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for name in ("submit_attestation_append.sh", "close_superseded_appends.sh", "restore_attestations.sh"):
        body = 'echo "$0 $*" >> "$CALL_LOG"\n'
        if name == "submit_attestation_append.sh":
            body += 'if [[ "${1:-}" == --rebuild ]]; then exit 1; fi\n'
        (scripts / name).write_text(body)
    gh = f"#!{sys.executable}\n" + textwrap.dedent('''\
        import json, os, pathlib, sys
        args = sys.argv[1:]
        with open(os.environ["CALL_LOG"], "a") as log:
            log.write("gh " + " ".join(args) + "\\n")
        pr = dict(number=42, headRefName="attestation/append-test", headRefOid="a" * 40,
                  baseRefName="main", isCrossRepository=False, state="OPEN",
                  createdAt="2026-10-14T00:00:00Z", autoMergeRequest={"enabledAt": "now"},
                  statusCheckRollup=[dict(name="deterministic-safety-net", status="COMPLETED",
                                          conclusion=os.environ["CHECK"])])
        if args[:2] == ["pr", "list"]:
            print(json.dumps([] if pathlib.Path("merged").exists() or os.environ["NEW_SUBMISSION"] == "1" else [pr]))
        elif args[:2] == ["pr", "view"]:
            count = pathlib.Path("views")
            n = int(count.read_text()) + 1 if count.exists() else 1
            count.write_text(str(n))
            if n >= 2 and os.environ["LOOKUP_STATUS"] != "0":
                sys.exit(int(os.environ["LOOKUP_STATUS"]))
            if os.environ["MERGE_LATER"] == "1" and n >= int(os.environ["MERGE_AT"]):
                pr["state"] = "MERGED"
                pathlib.Path("merged").touch()
            print(json.dumps(pr))
        elif args[:2] != ["pr", "merge"]:
            sys.exit("unexpected GitHub call: " + repr(args))
    ''')
    programs = {
        "gh": gh,
        "python3": '#!/bin/bash\necho "python3 $*" >> "$CALL_LOG"\n'
                   'if [[ "$*" == *--wait-for-acceptance* ]]; then exit "$PROOF"; fi\n'
                   'if [[ "$*" == *--require-committed* ]]; then exit 1; fi\n',
        "git": '#!/bin/bash\necho "git $*" >> "$CALL_LOG"\n'
               'case "$1" in branch) echo attestation/append-test;; '
               'rev-parse) printf "%040d\\n" 0 | tr 0 a;; esac\n',
        "sleep": '#!/bin/sh\necho "sleep $*" >> "$CALL_LOG"\n',
        "timeout": '#!/bin/bash\nshift 2\ncap="$1"; shift\n'
                   'if [[ "$OUTER_TIMEOUT" == 1 && ( "$cap" == 1800s || "$cap" == 1900s ) ]]; then exit 124; fi\n'
                   'exec "$@"\n',
    }
    for name, body in programs.items():
        path = bin_dir / name
        path.write_text(body)
        path.chmod(0o755)
    output = tmp_path / "output"
    log = tmp_path / "calls"
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}",
           "GITHUB_OUTPUT": str(output), "GITHUB_STEP_SUMMARY": str(tmp_path / "summary"),
           "GITHUB_REPOSITORY": "example/test", "PROMOTION_SOURCE_SHA": "a" * 40,
           "APPEND_PREP_STATE": "ready", "APPEND_BRANCH": "attestation/append-test",
           "APPEND_HEAD_SHA": "a" * 40,
           "APPEND_ACCEPTANCE_PATIENCE_SECONDS": str(patience), "CALL_LOG": str(log),
           "CHECK": check, "MERGE_LATER": str(int(merged)), "PROOF": str(proof),
           "OUTER_TIMEOUT": str(int(outer_timeout)), "LOOKUP_STATUS": str(lookup_status),
           "NEW_SUBMISSION": str(int(new_submission)), "MERGE_AT": str(merge_at)}
    if new_submission and not early:
        prepare = next(item for item in steps if item.get("name") == "Prepare append candidate for acceptance")
        prepared = subprocess.run(["bash", "-c", prepare["run"]], cwd=tmp_path, env=env,
                                  capture_output=True, text=True, timeout=10)
        assert prepared.returncode == 0, prepared.stdout + prepared.stderr
        prep_output = dict(line.split("=", 1) for line in output.read_text().splitlines())
        assert prep_output["state"] == "ready"
        env.update(APPEND_PREP_STATE=prep_output["state"], APPEND_BRANCH=prep_output["branch"],
                   APPEND_HEAD_SHA=prep_output["head_sha"])
        output.unlink()
    result = subprocess.run(["bash", "-c", step["run"]], cwd=tmp_path, env=env,
                            capture_output=True, text=True, timeout=10)
    return result, output.read_text() if output.exists() else "", log.read_text() if log.exists() else ""


@pytest.mark.parametrize("early", [False, True])
def test_open_passed_armed_append_defers_without_acceptance(tmp_path: Path, early: bool) -> None:
    result, output, calls = run_wait(tmp_path, early=early)
    assert result.returncode == 0, result.stderr
    assert "state=append-deferred" in output
    assert "state=accepted" not in output
    assert "append-deferred" in result.stdout + result.stderr
    assert "#42" in result.stdout + result.stderr
    assert "age" in result.stdout + result.stderr
    assert "submit_attestation_append.sh" not in calls
    assert "gh pr merge" not in calls  # Already armed: do not submit/arm twice.
    assert "append-deferred" in (tmp_path / "summary").read_text()


@pytest.mark.parametrize("early", [False, True])
def test_failed_required_check_refuses_without_deferral(tmp_path: Path, early: bool) -> None:
    result, output, _ = run_wait(tmp_path, early=early, check="FAILURE")
    assert result.returncode != 0
    assert "required check failed" in result.stderr
    assert "append-deferred" not in output + result.stdout + result.stderr
    assert "state=accepted" not in output


@pytest.mark.parametrize("early", [False, True])
def test_process_timeout_defers_without_acceptance(tmp_path: Path, early: bool) -> None:
    result, output, _ = run_wait(tmp_path, early=early, outer_timeout=True)
    assert result.returncode == 0, result.stderr
    assert "state=append-deferred" in output
    assert "state=accepted" not in output


@pytest.mark.parametrize("early", [False, True])
@pytest.mark.parametrize("status", [64, 124, 137])
def test_lookup_failure_preserves_refusal_or_timeout_attribution(
    tmp_path: Path, early: bool, status: int,
) -> None:
    result, output, _ = run_wait(tmp_path, early=early, lookup_status=status,
                                 patience=60 if early else 0)
    assert "state=accepted" not in output
    if status in (124, 137):
        if early:
            assert result.returncode != 0
            assert output == "state=append-wait-failed\n"
            assert "timeout -k 5s 20s gh pr view 42" in result.stderr
            assert f"status {status}" in result.stderr
        else:
            assert result.returncode == 0, result.stderr
            assert "state=append-deferred" in output
    else:
        assert result.returncode != 0
        assert "append-deferred" not in output + result.stdout + result.stderr


def test_early_lookup_timeout_before_patience_is_attributed(tmp_path: Path) -> None:
    result, output, _ = run_wait(tmp_path, early=True, lookup_status=124, patience=60)
    assert result.returncode != 0
    assert output == "state=append-wait-failed\n"
    assert "timeout -k 5s 20s gh pr view 42" in result.stderr
    assert "status 124" in result.stderr
    assert "elapsed " in result.stderr
    assert "patience 60s" in result.stderr


def test_lookup_timeout_after_patience_defers_from_enclosing_wait(tmp_path: Path) -> None:
    result, output, _ = run_wait(tmp_path, early=True, lookup_status=124, patience=0)
    assert result.returncode == 0, result.stderr
    assert output == "state=append-deferred\n"
    assert "state=append-wait-failed" not in output
    assert "state=accepted" not in output


@pytest.mark.parametrize("merged", [False, True])
def test_new_submission_uses_the_same_acceptance_gate(tmp_path: Path, merged: bool) -> None:
    result, output, calls = run_wait(tmp_path, new_submission=True, merged=merged,
                                     proof=0 if merged else 75)
    assert result.returncode == 0, result.stderr
    assert "submit_attestation_append.sh" in calls
    assert output == ("state=accepted\n" if merged else "state=append-deferred\n")


@pytest.mark.parametrize("early", [False, True])
def test_merge_between_list_and_view_is_accepted(tmp_path: Path, early: bool) -> None:
    result, output, _ = run_wait(tmp_path, early=early, merged=True, merge_at=1, proof=0)
    assert result.returncode == 0, result.stderr
    assert output == ("state=ready\n" if early else "state=accepted\n")


@pytest.mark.parametrize("early", [False, True])
def test_merge_and_exact_proof_accept_without_deferral(tmp_path: Path, early: bool) -> None:
    result, output, calls = run_wait(tmp_path, early=early, merged=True, proof=0,
                                    merge_at=3, patience=60)
    assert result.returncode == 0, result.stderr
    assert output == ("state=ready\n" if early else "state=accepted\n")
    assert "append-deferred" not in result.stdout + result.stderr
    assert "sleep 15" in calls


def test_merged_append_with_invalid_proof_still_refuses(tmp_path: Path) -> None:
    result, output, _ = run_wait(tmp_path, merged=True, proof=1)
    assert result.returncode != 0
    assert "state=accepted" not in output
    assert "append-deferred" not in output + result.stdout + result.stderr


def test_deferral_gates_candidate_signing_and_deploy() -> None:
    jobs = workflow()["jobs"]
    steps = jobs["sign_health"]["steps"]
    early = next(i for i, step in enumerate(steps) if step.get("id") == "existing_append")
    acceptance = next(i for i, step in enumerate(steps) if step.get("id") == "append_acceptance")
    for step in steps[early + 1:acceptance + 1]:
        assert "steps.existing_append.outputs.state == 'ready'" in step["if"], step["name"]
    for step in steps[acceptance + 1:]:
        assert "steps.append_acceptance.outputs.state == 'accepted'" in step["if"], step["name"]
    assert "needs.sign_health.outputs.append_state == 'accepted'" in jobs["deploy"]["if"]
    assert "append-deferred" in jobs["sign_health"]["outputs"]["append_state"]


@pytest.fixture
def candidate(tmp_path: Path) -> tuple[Path, str, Path, Path, list[str]]:
    root, key = fixture_root(tmp_path / "candidate")
    ga.generate(root, key, NOW)
    source = accept(root)
    origin = tmp_path / "origin.git"
    git(root, "clone", "--bare", str(root), str(origin))
    git(root, "remote", "add", "origin", str(origin))
    authority = tmp_path / "authority"
    git(root, "clone", str(origin), str(authority))
    git(authority, "config", "user.name", "Test")
    git(authority, "config", "user.email", "test@example.test")
    ga.generate(root, key, NOW + timedelta(hours=1), force_append=True)
    paths = verifier.append_paths(root, source)
    for path in paths:
        target = authority / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((root / path).read_bytes())
    return root, source, authority, origin, paths


def test_append_with_mixed_previous_head_projection_is_rejected(
    candidate: tuple[Path, str, Path, Path, list[str]],
) -> None:
    root, source, _, _, _ = candidate
    candidate_binding = (root / "attestations/latest/binding.json").read_bytes()
    for path in ("attestations/chain-index.json", "attestations/latest/index.json",
                 "attestations/latest/chain_head.json", ".attestations/chain_head.json"):
        (root / path).write_bytes(verifier.git_bytes(root, source, path))
    assert (root / "attestations/latest/binding.json").read_bytes() == candidate_binding
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/verify_attestation_append.py"),
         "--root", str(root), "--base", source],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 1
    assert "attestation append: latest projection is stale or mixed" in result.stderr


def test_append_latest_is_judged_against_own_head(
    candidate: tuple[Path, str, Path, Path, list[str]],
) -> None:
    root, source, _, _, _ = candidate
    (root / "attestations/chain-index.json").write_bytes(
        verifier.git_bytes(root, source, "attestations/chain-index.json")
    )
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/verify_attestation_append.py"),
         "--root", str(root), "--base", source],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "append judged against its own head" in result.stderr


def test_append_with_own_head_binding_disagreement_is_rejected(
    candidate: tuple[Path, str, Path, Path, list[str]],
) -> None:
    root, source, _, _, _ = candidate
    binding = root / "attestations/latest/binding.json"
    binding.write_bytes(binding.read_bytes() + b" ")
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/verify_attestation_append.py"),
         "--root", str(root), "--base", source],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 1
    assert "attestation append: latest projection is stale or mixed" in result.stderr
    assert "append judged against its own head" not in result.stderr


def test_append_missing_own_frozen_directory_is_rejected(
    candidate: tuple[Path, str, Path, Path, list[str]],
) -> None:
    root, source, _, _, _ = candidate
    directory = verifier.accepted_day_directory(root, ga.load(root / "attestations/chain-index.json"))
    shutil.rmtree(root / directory)
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/verify_attestation_append.py"),
         "--root", str(root), "--base", source],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 1
    assert "attestation append:" in result.stderr
    assert "append judged against its own head" not in result.stderr


def projection_candidate(tmp_path: Path) -> tuple[Path, str, bytes, bytes]:
    """Accept a new evidence set, then refresh only its four projections."""
    root, key = fixture_root(tmp_path)
    (root / ".gitignore").write_text("private.json\n")
    ga.generate(root, key, NOW)
    git(root, "init", "-b", "main")
    git(root, "config", "user.name", "Test")
    git(root, "config", "user.email", "test@example.test")
    git(root, "add", ".gitignore")
    accept(root)
    old_head = (root / "attestations/latest/chain_head.json").read_bytes()
    old_mirror = (root / ".attestations/chain_head.json").read_bytes()
    ga.generate(root, key, NOW + timedelta(days=1))
    git(root, "restore", "--", "attestations/latest", "attestations/chain-index.json",
        ".attestations/chain_head.json", "datapulse.json")
    git(root, "add", "attestations/2026-08-16")
    git(root, "commit", "-m", "accepted evidence only")
    base = git(root, "rev-parse", "HEAD")
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/gen_attestation_projections.py"), "--root", str(root)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return root, base, old_head, old_mirror


def test_projection_ahead_without_new_evidence_is_accepted(tmp_path: Path) -> None:
    root, base, old_head, _ = projection_candidate(tmp_path)
    assert (root / "attestations/latest/chain_head.json").read_bytes() != old_head
    verifier.verify_append(root, base)
    verifier.verify_append(root, base, require_committed=True)


def test_projection_ahead_with_modified_envelope_is_rejected(tmp_path: Path) -> None:
    root, base, _, _ = projection_candidate(tmp_path)
    envelope = root / "attestations/latest/binding.json"
    envelope.write_bytes(envelope.read_bytes() + b" ")
    with pytest.raises(verifier.ContractError, match="latest projection is stale or mixed") as error:
        verifier.verify_append(root, base)
    assert str(error.value) == "latest projection is stale or mixed"


def test_projection_only_backward_move_is_rejected(tmp_path: Path) -> None:
    root, base, old_head, old_mirror = projection_candidate(tmp_path)
    base = accept(root)
    (root / "attestations/latest/chain_head.json").write_bytes(old_head)
    (root / ".attestations/chain_head.json").write_bytes(old_mirror)
    with pytest.raises(verifier.ContractError, match="latest projection is stale or mixed") as error:
        verifier.verify_append(root, base)
    assert str(error.value) == "latest projection is stale or mixed"


def test_projection_only_mirror_disagreement_is_rejected(tmp_path: Path) -> None:
    root, base, _, old_mirror = projection_candidate(tmp_path)
    (root / ".attestations/chain_head.json").write_bytes(old_mirror)
    with pytest.raises(verifier.ContractError, match="legacy mirror disagrees with current head") as error:
        verifier.verify_append(root, base)
    assert str(error.value).startswith("legacy mirror disagrees with current head")


@pytest.mark.parametrize("binding_only", [False, True])
def test_complete_projection_refresh_enforces_frozen_agreement(
    tmp_path: Path, binding_only: bool,
) -> None:
    root, _, _, old_mirror = projection_candidate(tmp_path)
    latest_index = json.loads((root / "attestations/latest/index.json").read_bytes())
    directory = Path(latest_index["binding_ref"]).parent
    expected_binding = (root / directory / "binding.json").read_bytes()
    expected_scores = (root / directory / "scores.json").read_bytes()
    if not binding_only:
        git(root, "restore", "--", "attestations/latest", "attestations/chain-index.json",
            ".attestations/chain_head.json")
    # Accept the pipeline score first, then the projection writer must project
    # the frozen score belonging to the selected revision.
    scores = root / "attestations/latest/scores.json"
    scores.write_text('{"generated_at":"2000-01-01T00:00:00Z"}\n', encoding="utf-8")
    base = accept(root)
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/gen_attestation_projections.py"), "--root", str(root)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    expected_paths = {"attestations/latest/scores.json"}
    if not binding_only:
        expected_paths.update({
            "attestations/latest/index.json", "attestations/latest/chain_head.json",
            "attestations/latest/binding.json",
            "attestations/chain-index.json", ".attestations/chain_head.json",
        })
    assert set(git(root, "diff", "--name-only", base).splitlines()) == expected_paths
    binding = root / "attestations/latest/binding.json"
    assert binding.read_bytes() == expected_binding
    assert scores.read_bytes() == expected_scores
    verifier.verify_append(root, base)
    verifier.verify_append(root, base, require_committed=True)
    assert verifier.append_paths(root, base) == []

    binding.write_bytes(expected_binding + b" ")
    with pytest.raises(verifier.ContractError, match="^latest projection is stale or mixed$"):
        verifier.verify_append(root, base)
    binding.write_bytes(expected_binding)
    (root / ".attestations/chain_head.json").write_bytes(old_mirror)
    with pytest.raises(verifier.ContractError, match="^legacy mirror disagrees with current head"):
        verifier.verify_append(root, base)


def test_complete_projection_refresh_with_stale_scores_is_rejected(tmp_path: Path) -> None:
    root, base, _, _ = projection_candidate(tmp_path)
    scores_document = json.loads((root / "attestations/latest/scores.json").read_bytes())
    scores_document["generated_at"] = "2000-01-01T00:00:00Z"
    scores = (json.dumps(scores_document, ensure_ascii=False, indent=2) + "\n").encode()
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/gen_attestation_projections.py"), "--root", str(root)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    latest_index = json.loads((root / "attestations/latest/index.json").read_bytes())
    binding = root / "attestations/latest/binding.json"
    assert binding.read_bytes() == (root / latest_index["binding_ref"]).read_bytes()
    frozen_scores = root / Path(latest_index["binding_ref"]).with_name("scores.json")
    assert json.loads(scores)["generated_at"] < json.loads(frozen_scores.read_bytes())["generated_at"]
    (root / "attestations/latest/scores.json").write_bytes(scores)
    with pytest.raises(verifier.ContractError, match="^latest projection is stale or mixed$"):
        verifier.verify_append(root, base)


def merge_append(authority: Path, origin: Path) -> None:
    git(authority, "add", "attestations")
    git(authority, "commit", "-m", "accept immutable append")
    git(authority, "--git-dir=" + str(origin), "fetch", str(authority), "main:main")


def test_wait_observes_later_merge_without_mutating_candidate(
    candidate: tuple[Path, str, Path, Path, list[str]], monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, source, authority, origin, paths = candidate
    frozen = {path: (root / path).read_bytes() for path in paths}
    health = (root / "health/latest.json").read_bytes()
    sleeps = []

    def accept_on_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        assert git(root, "rev-parse", "origin/main") == source
        merge_append(authority, origin)

    # Do not patch the global time module used by subprocess's timeout wait.
    monkeypatch.setattr(verifier, "time", SimpleNamespace(
        sleep=accept_on_sleep, monotonic=verifier.time.monotonic,
    ))
    verifier.wait_for_acceptance(root, source, timeout=60, poll_seconds=1)
    assert sleeps == [1]
    assert git(root, "rev-parse", "HEAD") == source
    assert (root / "health/latest.json").read_bytes() == health
    assert {path: (root / path).read_bytes() for path in paths} == frozen
    verifier.verify_append(root, "origin/main", require_committed=True)


@pytest.mark.parametrize("changed_file", ["head", "binding", "health", "missing"])
def test_wait_rejects_inexact_authoritative_evidence(
    candidate: tuple[Path, str, Path, Path, list[str]], changed_file: str,
) -> None:
    root, source, authority, origin, paths = candidate
    name = {"head": "chain_head.json", "binding": "binding.json",
            "health": "health.json.gz", "missing": "binding.json"}[changed_file]
    path = authority / next(path for path in paths if path.endswith("/" + name))
    if changed_file == "missing":
        path.unlink()
    else:
        path.write_bytes(path.read_bytes() + b" ")
    merge_append(authority, origin)
    with pytest.raises(ValueError, match="bytes disagree|immutable evidence changed|missing"):
        verifier.wait_for_acceptance(root, source, timeout=0)


def test_wait_rejects_main_that_does_not_contain_source(
    candidate: tuple[Path, str, Path, Path, list[str]],
) -> None:
    root, source, authority, origin, _ = candidate
    git(authority, "checkout", "--orphan", "unrelated")
    git(authority, "add", "attestations", "docs", "health", "datapulse.json")
    git(authority, "commit", "-m", "unrelated evidence")
    git(authority, "--git-dir=" + str(origin), "fetch", str(authority), "unrelated:refs/heads/main", "--force")
    with pytest.raises(subprocess.CalledProcessError):
        verifier.wait_for_acceptance(root, source, timeout=0)


def test_wait_fails_closed_on_fetch_error(
    candidate: tuple[Path, str, Path, Path, list[str]],
) -> None:
    root, source, _, _, _ = candidate
    git(root, "remote", "set-url", "origin", str(root / "missing-origin"))
    with pytest.raises(subprocess.CalledProcessError):
        verifier.wait_for_acceptance(root, source, timeout=0)


def test_pending_proof_has_distinct_exit_without_claiming_acceptance(
    candidate: tuple[Path, str, Path, Path, list[str]],
) -> None:
    root, source, _, _, _ = candidate
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/verify_attestation_append.py"),
         "--root", str(root), "--base", source, "--wait-for-acceptance", "0"],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 75
    assert "append-deferred" in result.stderr
    assert result.stdout == ""


def test_fetch_timeout_defers_without_accepting(
    candidate: tuple[Path, str, Path, Path, list[str]], monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, source, _, _, _ = candidate
    run = subprocess.run

    def capped_fetch(args: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        if args[:2] == ["git", "fetch"]:
            raise subprocess.TimeoutExpired(args, 30)
        return run(args, **kwargs)

    monkeypatch.setattr(verifier.subprocess, "run", capped_fetch)
    with pytest.raises(verifier.AcceptancePending, match="append-deferred"):
        verifier.wait_for_acceptance(root, source, timeout=0)


@pytest.mark.parametrize("explicit_number", [False, True])
@pytest.mark.parametrize("protect_old", [False, True])
def test_cleanup_closes_only_older_exact_accepted_blobs_and_never_accepted_pr(
    candidate: tuple[Path, str, Path, Path, list[str]], tmp_path: Path,
    explicit_number: bool, protect_old: bool,
) -> None:
    root, _, authority, origin, paths = candidate
    paths = list(paths)
    for filename in (f"health.{'c' * 64}.statement.json",
                     f"health.{'c' * 64}.sigstore.bundle.json", f"reference.{'c' * 64}.json"):
        witness = authority / "attestations/rekor/2026-08-15" / filename
        witness.parent.mkdir(parents=True, exist_ok=True)
        witness.write_text("{}\n")
        paths.append(witness.relative_to(authority).as_posix())
    merge_append(authority, origin)
    accepted_sha = git(authority, "rev-parse", "HEAD")

    def row(number: int, created: str, **extra: object) -> dict:
        return dict(number=number, headRefName=f"attestation/append-{number}",
                    headRefOid="a" * 40, baseRefName="main", isCrossRepository=False,
                    state="OPEN", createdAt=created, **extra)

    accepted = row(42, "2026-10-15T00:00:00Z", mergeCommit={"oid": accepted_sha})
    accepted.update(state="MERGED", mergedAt="2026-10-15T01:00:00Z")
    older = [row(n, "2026-10-14T00:00:00Z") for n in (41, 40, 39, 38, 37)]
    older[-1]["isCrossRepository"] = True
    # Including the accepted number in the mock open list tests the final guard.
    rows = [{**accepted, "state": "OPEN"}, *older, row(43, "2026-10-16T00:00:00Z")]
    files = [{"filename": path, "sha": git(authority, "rev-parse", f"HEAD:{path}"),
              "status": "added"} for path in paths]
    assert any(file["filename"].endswith("/chain_head.json") for file in files)
    bin_dir = tmp_path / "cleanup-bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(f"#!{sys.executable}\n" + textwrap.dedent('''\
        import json, os, pathlib, sys
        args = sys.argv[1:]
        accepted = json.loads(os.environ["ACCEPTED"])
        rows = json.loads(os.environ["ROWS"])
        if args[:2] == ["pr", "list"]:
            print(json.dumps([accepted] if "merged" in args else rows))
        elif args[:2] == ["pr", "view"]:
            number = int(args[2])
            row = accepted if number == 42 else next(row for row in rows if row["number"] == number)
            if number == 38:
                row["headRefOid"] = "b" * 40
            print(json.dumps(row))
        elif args[0] == "api":
            number = int(args[1].split("/")[-2])
            files = json.loads(os.environ["FILES"])
            if number == 40:
                files[0]["sha"] = "0" * 40
            if number == 39:
                files[0]["status"] = "modified"
            print(json.dumps([files]))
        elif args[:2] == ["pr", "close"]:
            with open(os.environ["CLOSED"], "a") as out:
                out.write(args[2] + "\\n")
        else:
            sys.exit("unexpected GitHub call: " + repr(args))
    '''))
    gh.chmod(0o755)
    closed = tmp_path / "closed"
    env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}",
           "GITHUB_REPOSITORY": "example/test", "ACCEPTED": json.dumps(accepted),
           "ROWS": json.dumps(rows), "FILES": json.dumps(files), "CLOSED": str(closed)}
    before = git(root, "status", "--porcelain")
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/close_superseded_appends.sh"),
         "42" if explicit_number else "", "41" if protect_old else ""], cwd=root, env=env,
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stderr
    if protect_old:
        assert not closed.exists()
    else:
        assert closed.read_text() == "41\n"
        assert "#42" in result.stdout
    assert git(root, "status", "--porcelain") == before
