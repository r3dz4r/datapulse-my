#!/usr/bin/env python3
"""Keep exact-byte refusals while bounding historical byte hashing."""
from __future__ import annotations

from datetime import timedelta
import os
from pathlib import Path
import subprocess
import sys

import pytest

from scripts import gen_attestations as ga
from scripts import verify_attestation_append as verifier
from scripts.tests.test_append_set_isolation import NOW, accept, git
from scripts.tests.test_attestations import fixture_root

VERIFIER = Path(verifier.__file__)
WITNESS = "attestations/unreferenced.json"


@pytest.fixture
def accepted(tmp_path: Path) -> tuple[Path, str]:
    root, key = fixture_root(tmp_path)
    ga.generate(root, key, NOW)
    # Discovery does not read this file: only raw-byte integrity protects it.
    (root / WITNESS).write_bytes(b'{"witness":1}\n')
    return root, accept(root)


def run_verifier(root: Path, base: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(VERIFIER), "--root", str(root),
                           "--base", base, *args], capture_output=True, text=True)


@pytest.mark.parametrize("mutation", ["edit", "delete", "index-delete", "staged",
                                      "assume-unchanged", "skip-worktree", "same-size"])
def test_tampered_accepted_file_is_refused(
    accepted: tuple[Path, str], mutation: str,
) -> None:
    root, base = accepted
    path = root / WITNESS
    original_stat = path.stat()
    if mutation in {"delete", "index-delete"}:
        if mutation == "index-delete":
            git(root, "rm", "--cached", WITNESS)
        path.unlink()
    else:
        if mutation in {"assume-unchanged", "skip-worktree"}:
            git(root, "update-index", "--" + mutation, WITNESS)
        path.write_bytes(b'{"witness":2}\n' if mutation == "same-size" else b"tampered\n")
        if mutation == "same-size":
            os.utime(path, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
        if mutation == "staged":
            git(root, "add", WITNESS)
    result = run_verifier(root, base)
    assert result.returncode == 1, result.stderr
    assert result.stderr == f"attestation append: immutable evidence changed or deleted: {WITNESS}\n"


def test_clean_checkout_and_unrelated_modification_pass(accepted: tuple[Path, str]) -> None:
    root, base = accepted
    for changed in (False, True):
        if changed:
            (root / "health/latest.json").write_text("unrelated dirty health\n")
        result = run_verifier(root, base, "--print-paths")
        assert result.returncode == 0, result.stderr
        assert result.stdout == ""


@pytest.mark.parametrize("staged", [False, True])
def test_git_text_normalization_cannot_hide_changed_bytes(
    accepted: tuple[Path, str], staged: bool,
) -> None:
    root, base = accepted
    (root / ".gitattributes").write_text("*.json text eol=lf\n")
    path = root / WITNESS
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    if staged:
        git(root, "add", WITNESS)
    result = run_verifier(root, base)
    assert result.returncode == 1
    assert WITNESS in result.stderr


def test_clean_history_is_not_byte_hashed(
    accepted: tuple[Path, str], monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, base = accepted
    hashed = []
    original = verifier._file_object_id

    def counted(path: Path, algorithm: str) -> str:
        hashed.append(path.relative_to(root).as_posix())
        return original(path, algorithm)

    monkeypatch.setattr(verifier, "_file_object_id", counted)
    verifier.verify_append(root, base)
    assert hashed == [], f"clean accepted history was byte hashed: {hashed}"
    ga.generate(root, root / "private.json", NOW + timedelta(hours=1), force_append=True)
    paths = verifier.append_paths(root, base)
    git(root, "add", "--", *paths)
    verifier.verify_append(root, base)
    assert sorted(hashed) == paths


def test_delta_bytes_must_match_recorded_git_digest(accepted: tuple[Path, str]) -> None:
    root, base = accepted
    ga.generate(root, root / "private.json", NOW + timedelta(hours=1), force_append=True)
    paths = verifier.append_paths(root, base)
    git(root, "add", "--", *paths)
    path = next(path for path in paths if path.endswith("/scores.json"))
    # Signed JSON content is unchanged; only an exact-byte check catches this.
    with (root / path).open("ab") as output:
        output.write(b" ")
    result = run_verifier(root, base)
    assert result.returncode == 1
    assert result.stderr.endswith(f"attestation append: immutable evidence changed or deleted: {path}\n")
