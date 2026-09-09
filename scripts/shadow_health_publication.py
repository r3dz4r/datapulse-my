#!/usr/bin/env python3
"""Create and verify local-only health publication candidates."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any


SCHEMA = "datapulse/v1/shadow-health-publication-envelope"
VERSION = 1
ENVELOPE_KEYS = (
    "schema", "version", "source_commit", "health_commit", "checked_at",
    "dataset_count", "health_sha256", "semantic_sha256",
)
COMMIT_RE = re.compile(r"^[0-9a-f]{7,64}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ShadowPublicationError(Exception):
    """Base error whose message is safe to return to CLI callers."""


class InvalidHealthError(ShadowPublicationError):
    """The canonical health snapshot does not satisfy the minimal contract."""


class InvalidEnvelopeError(ShadowPublicationError):
    """A candidate envelope is malformed or unsafe to compare."""


class UnsafeOutputError(ShadowPublicationError):
    """The requested output path is not safe for a local candidate write."""


def canonical_json(value: object) -> bytes:
    """Return the stable JSON representation used for semantic hashing."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def envelope_json(value: dict[str, object]) -> bytes:
    """Return deterministic envelope bytes in the contract's field order."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def validate_commit(value: str) -> str:
    """Validate and return a lower-case git commit identity."""
    if not COMMIT_RE.fullmatch(value):
        raise ShadowPublicationError("invalid_commit")
    return value


def load_health(path: Path) -> tuple[bytes, dict[str, Any], list[dict[str, str]]]:
    """Read and validate a canonical health snapshot without retaining full rows."""
    try:
        if path.is_symlink() or not path.is_file():
            raise OSError
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InvalidHealthError("invalid_health") from exc
    if not isinstance(value, dict) or "_trust_summary" not in value:
        raise InvalidHealthError("invalid_health")
    checked_at = value.get("checked_at")
    datasets = value.get("datasets")
    if not isinstance(checked_at, str) or not checked_at or not isinstance(datasets, list) or not datasets:
        raise InvalidHealthError("invalid_health")

    identities: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for row in datasets:
        if not isinstance(row, dict):
            raise InvalidHealthError("invalid_health")
        dataset_id = row.get("dataset_id")
        status = row.get("status")
        if not isinstance(dataset_id, str) or not dataset_id or not isinstance(status, str) or not status:
            raise InvalidHealthError("invalid_health")
        if dataset_id in seen_ids:
            raise InvalidHealthError("invalid_health")
        seen_ids.add(dataset_id)
        identities.append({"dataset_id": dataset_id, "status": status})
    return raw, value, identities


def build_envelope(health_path: Path, source_commit: str, health_commit: str) -> dict[str, object]:
    """Build the minimal candidate envelope for one exact health file."""
    raw, health, identities = load_health(health_path)
    semantic = sorted(identities, key=lambda item: (item["dataset_id"], item["status"]))
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "source_commit": validate_commit(source_commit),
        "health_commit": validate_commit(health_commit),
        "checked_at": health["checked_at"],
        "dataset_count": len(semantic),
        "health_sha256": hashlib.sha256(raw).hexdigest(),
        "semantic_sha256": hashlib.sha256(canonical_json(semantic)).hexdigest(),
    }


def assert_safe_output(path: Path, health_path: Path) -> Path:
    """Reject traversal, symlinks, and the canonical health target before writing."""
    if ".." in path.parts:
        raise UnsafeOutputError("unsafe_output")
    absolute = path.absolute()
    health_absolute = health_path.absolute()
    if absolute == health_absolute:
        raise UnsafeOutputError("unsafe_output")
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        if current.is_symlink():
            raise UnsafeOutputError("unsafe_output")
    try:
        absolute.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise UnsafeOutputError("unsafe_output") from exc
    if absolute.is_symlink():
        raise UnsafeOutputError("unsafe_output")
    return absolute


def atomic_write(path: Path, content: bytes) -> None:
    """Atomically replace a local candidate only after complete durable staging."""
    descriptor = -1
    temporary_name = ""
    try:
        descriptor, temporary_name = tempfile.mkstemp(prefix=".shadow-health-", dir=path.parent)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    except OSError as exc:
        raise UnsafeOutputError("write_failed") from exc
    finally:
        if descriptor != -1:
            os.close(descriptor)
        if temporary_name:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass


def create(health_path: Path, output_path: Path, source_commit: str, health_commit: str) -> dict[str, object]:
    """Create a deterministic, local-only candidate envelope."""
    envelope = build_envelope(health_path, source_commit, health_commit)
    output = assert_safe_output(output_path, health_path)
    atomic_write(output, envelope_json(envelope) + b"\n")
    return {"created": True, "dataset_count": envelope["dataset_count"]}


def load_envelope(path: Path) -> dict[str, object]:
    """Read and strictly validate an envelope before any comparison."""
    try:
        if path.is_symlink() or not path.is_file():
            raise OSError
        value = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InvalidEnvelopeError("invalid_envelope") from exc
    if not isinstance(value, dict) or set(value) != set(ENVELOPE_KEYS):
        raise InvalidEnvelopeError("invalid_envelope")
    if value["schema"] != SCHEMA or value["version"] != VERSION:
        raise InvalidEnvelopeError("invalid_envelope")
    if not isinstance(value["checked_at"], str) or not value["checked_at"]:
        raise InvalidEnvelopeError("invalid_envelope")
    if type(value["dataset_count"]) is not int or value["dataset_count"] < 1:
        raise InvalidEnvelopeError("invalid_envelope")
    for key in ("source_commit", "health_commit"):
        if not isinstance(value[key], str) or not COMMIT_RE.fullmatch(value[key]):
            raise InvalidEnvelopeError("invalid_envelope")
    for key in ("health_sha256", "semantic_sha256"):
        if not isinstance(value[key], str) or not SHA256_RE.fullmatch(value[key]):
            raise InvalidEnvelopeError("invalid_envelope")
    return value


def compare(health_path: Path, envelope_path: Path, source_commit: str, health_commit: str) -> dict[str, object]:
    """Compare a candidate envelope to exact current health bytes and identities."""
    source = validate_commit(source_commit)
    health_identity = validate_commit(health_commit)
    envelope = load_envelope(envelope_path)
    if envelope["source_commit"] != source:
        return {"equivalent": False, "error": "source_commit_mismatch"}
    if envelope["health_commit"] != health_identity:
        return {"equivalent": False, "error": "health_commit_mismatch"}
    expected = build_envelope(health_path, source, health_identity)
    fields = ("health_sha256", "checked_at", "dataset_count", "semantic_sha256")
    mismatches = [field for field in fields if envelope[field] != expected[field]]
    if mismatches:
        return {"equivalent": False, "error": "mismatch", "mismatches": mismatches}
    return {"equivalent": True}


def parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    command_parser = argparse.ArgumentParser(description="Local shadow health publication candidate tool")
    commands = command_parser.add_subparsers(dest="command", required=True)
    for name, destination in (("create", "output"), ("compare", "envelope")):
        subparser = commands.add_parser(name)
        subparser.add_argument("--health", required=True)
        subparser.add_argument(f"--{destination}", required=True)
        subparser.add_argument("--source-commit", required=True)
        subparser.add_argument("--health-commit", required=True)
    return command_parser


def emit(value: dict[str, object]) -> None:
    """Emit a machine-readable, non-sensitive result."""
    print(json.dumps(value, sort_keys=True, separators=(",", ":")))


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return a process exit status."""
    args = parser().parse_args(argv)
    try:
        if args.command == "create":
            emit(create(Path(args.health), Path(args.output), args.source_commit, args.health_commit))
            return 0
        result = compare(Path(args.health), Path(args.envelope), args.source_commit, args.health_commit)
        emit(result)
        return 0 if result["equivalent"] is True else 1
    except ShadowPublicationError as exc:
        emit({"equivalent": False, "error": str(exc)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
