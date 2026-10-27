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


def test_pages_selects_only_already_accepted_health_without_pr_waits() -> None:
    jobs = workflow()["jobs"]
    steps = jobs["sign_health"]["steps"]
    selection = next(step for step in steps if step.get("id") == "select_accepted_health")
    assert "continue-on-error" not in selection
    assert '--revision "$PROMOTION_SOURCE_SHA"' in selection["run"]
    assert jobs["deploy"]["if"] == "needs.sign_health.outputs.report_state == 'accepted'"
    for forbidden in ("existing_append", "append_submission", "append_acceptance", "APPEND_",
                      "gh pr", "submit_attestation_append.sh", "--wait-for-acceptance"):
        assert forbidden not in WORKFLOW.read_text()


@pytest.mark.parametrize("pending", [False, True])
def test_pending_local_candidate_never_becomes_the_publication_authority(tmp_path: Path, pending: bool) -> None:
    from scripts.select_accepted_health import select_report
    from scripts.tests.test_attestation_projections import accepted_root
    root, key = accepted_root(tmp_path / "accepted")
    source = git(root, "rev-parse", "HEAD")
    accepted_health = (root / "health/latest.json").read_bytes()
    accepted_head = json.loads((root / "attestations/latest/chain_head.json").read_bytes())["chain_head"]
    if pending:
        ga.generate(root, key, NOW + timedelta(hours=1), force_append=True)
        assert json.loads((root / "attestations/latest/chain_head.json").read_bytes())["chain_head"] != accepted_head
    selected = tmp_path / "publication"
    result = select_report(root, source, selected, NOW + timedelta(hours=2))
    assert result["accepted_chain_head"] == accepted_head
    assert (selected / "health/latest.json").read_bytes() == accepted_health
    assert git(root, "rev-parse", "HEAD") == source


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
