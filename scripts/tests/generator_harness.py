"""Utilities for exercising repository generators in isolated directories."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
import weakref
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GeneratorRun:
    stdout: str
    stderr: str
    returncode: int
    outputs: dict[str, bytes | None]
    workdir: Path
    duration_seconds: float


def _relative_path(value: str, *, purpose: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{purpose} must be a relative path inside the workdir: {value}")
    return path


def _copy_input(source_root: Path, workdir: Path, value: str) -> None:
    relative = _relative_path(value, purpose="input")
    source = source_root / relative
    if not source.exists():
        raise FileNotFoundError(f"generator input does not exist: {source}")

    resolved_root = source_root.resolve()
    if not source.resolve().is_relative_to(resolved_root):
        raise ValueError(f"generator input escapes source_root: {value}")

    destination = workdir / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        symlinks = [path for path in source.rglob("*") if path.is_symlink()]
        if symlinks:
            raise ValueError(f"generator input directory contains a symlink: {symlinks[0]}")
        shutil.copytree(source, destination)
    else:
        shutil.copy2(source, destination)


def _generator_destination(generator: Path, source_root: Path, workdir: Path) -> Path:
    resolved = generator.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"generator does not exist: {generator}")

    try:
        relative = resolved.relative_to(source_root.resolve())
    except ValueError:
        # Fixture roots need to run the repository's real generator. Preserve the
        # scripts/ layout so Bash generators that derive ROOT from BASH_SOURCE
        # still resolve the isolated workdir rather than the tracked checkout.
        relative = Path("scripts") / resolved.name

    destination = workdir / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(resolved, destination)
    return destination


def _validate_canonical_json_inputs(workdir: Path, inputs: list[str]) -> str | None:
    for relative in ("datapulse.json", "health/latest.json"):
        if relative not in inputs:
            continue
        path = workdir / relative
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            return f"{relative}: unable to parse JSON: {error}"
        if not isinstance(document, dict) or "datasets" not in document:
            return f"{relative}: missing required field 'datasets'"
        if not isinstance(document["datasets"], list):
            return f"{relative}: field 'datasets' must be an array"
    return None


def _capture_outputs(
    workdir: Path, expected_outputs: list[str]
) -> dict[str, bytes | None]:
    captured: dict[str, bytes | None] = {}
    for value in expected_outputs:
        relative = _relative_path(value, purpose="expected output")
        path = workdir / relative
        captured[value] = path.read_bytes() if path.is_file() else None
    return captured


def run_generator(
    source_root: Path,
    generator: str | Path,
    inputs: list[str],
    expected_outputs: list[str],
    workdir_root: Path | None = None,
) -> GeneratorRun:
    """Copy inputs and run one generator without exposing the tracked checkout."""

    source_root = Path(source_root).resolve()
    generator_path = Path(generator)
    if not generator_path.is_absolute():
        generator_path = source_root / generator_path

    owns_workdir = workdir_root is None
    workdir = (
        Path(tempfile.mkdtemp(prefix="datapulse-gen-"))
        if owns_workdir
        else Path(workdir_root)
    )
    if not owns_workdir:
        workdir.mkdir(parents=True, exist_ok=True)
        if any(workdir.iterdir()):
            raise ValueError(f"workdir_root must be empty: {workdir}")

    try:
        for value in inputs:
            _copy_input(source_root, workdir, value)
        isolated_generator = _generator_destination(
            generator_path, source_root, workdir
        )

        started = time.monotonic()
        validation_error = _validate_canonical_json_inputs(workdir, inputs)
        if validation_error is None:
            suffix = isolated_generator.suffix.lower()
            if suffix == ".py":
                command = ["python3", str(isolated_generator)]
            elif suffix == ".sh":
                command = ["bash", str(isolated_generator)]
                if "health/latest.json" in inputs:
                    command.append(str(workdir / "health/latest.json"))
            else:
                raise ValueError(
                    f"unsupported generator type {isolated_generator.suffix!r}"
                )

            environment = os.environ.copy()
            environment["DATAPULSE_REPO_ROOT"] = str(workdir)
            environment["DATAPULSE_ARCHIVES_DIR"] = str(workdir / ".archives")
            completed = subprocess.run(
                command,
                cwd=workdir,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
            stdout = completed.stdout
            stderr = completed.stderr
            returncode = completed.returncode
        else:
            stdout = ""
            stderr = validation_error + "\n"
            returncode = 2

        result = GeneratorRun(
            stdout=stdout,
            stderr=stderr,
            returncode=returncode,
            outputs=_capture_outputs(workdir, expected_outputs),
            workdir=workdir,
            duration_seconds=time.monotonic() - started,
        )
    except Exception:
        if owns_workdir:
            shutil.rmtree(workdir, ignore_errors=True)
        raise

    if owns_workdir:
        weakref.finalize(result, shutil.rmtree, workdir, True)
    return result


def run_generator_twice(
    source_root: Path,
    generator: str | Path,
    inputs: list[str],
    expected_outputs: list[str],
) -> tuple[GeneratorRun, GeneratorRun, dict[str, bool]]:
    """Run a generator twice and compare every requested output byte-for-byte."""

    first = run_generator(source_root, generator, inputs, expected_outputs)
    second = run_generator(source_root, generator, inputs, expected_outputs)
    diff = {
        relative: first.outputs[relative] == second.outputs[relative]
        for relative in expected_outputs
    }
    return first, second, diff
