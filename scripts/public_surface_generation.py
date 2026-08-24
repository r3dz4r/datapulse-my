#!/usr/bin/env python3
"""Shared fail-closed primitives for deterministic public-surface generators."""

from __future__ import annotations

import json
import os
import re
import stat
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


PUBLIC_SURFACES_SCHEMA = "datapulse/v1/public-surfaces"
MARKER_RE = re.compile(r"<!-- (BEGIN|END) ([a-z0-9][a-z0-9-]*) -->")
ALLOWED_CONFIG_KEYS = {
    "schema",
    "origins",
    "pages",
    "artifacts",
    "featured_dataset_ids",
}
ALLOWED_ORIGIN_KEYS = {"website", "mcp", "repository"}
OLD_CANONICAL_HOSTS = {"r3dz4r.github.io"}


class GenerationError(Exception):
    """Raised when generation cannot safely produce its complete output set."""


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON object with a path-specific error."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise GenerationError(f"cannot read {path}: {error}") from error
    if not isinstance(value, dict):
        raise GenerationError(f"{path}: root must be an object")
    return value


def _validate_origin(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise GenerationError(f"origin {name!r} must be a string")
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise GenerationError(f"origin {name!r} must be an HTTPS origin")
    if name != "repository" and parsed.path not in ("", "/"):
        raise GenerationError(f"origin {name!r} must not include a path, query, or fragment")
    if parsed.query or parsed.fragment:
        raise GenerationError(f"origin {name!r} must not include a query or fragment")
    if parsed.hostname in OLD_CANONICAL_HOSTS:
        raise GenerationError(f"origin {name!r} uses a non-canonical host")
    if parsed.hostname in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}:
        raise GenerationError(f"origin {name!r} must not use an internal host")
    return value.rstrip("/")


def _validate_paths(name: str, value: object) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise GenerationError(f"{name} must be an explicit string array")
    if len(value) != len(set(value)):
        raise GenerationError(f"{name} contains a duplicate path")
    for item in value:
        parsed = urlsplit(item)
        if not item.startswith("/") or ".." in Path(parsed.path).parts:
            raise GenerationError(f"{name} contains an unsafe path: {item!r}")
        if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment or "\\" in item:
            raise GenerationError(f"{name} must contain local public paths only: {item!r}")
    return list(value)


def load_public_surfaces(root: Path) -> dict[str, Any]:
    """Load and strictly validate the stable public-surface contract."""
    path = root / "config/public-surfaces.json"
    schema_path = root / "config/public-surfaces.schema.json"
    schema = load_json(schema_path)
    if schema.get("additionalProperties") is not False:
        raise GenerationError(f"{schema_path}: root additionalProperties must be false")
    try:
        schema_origins = schema["properties"]["origins"]
        if schema_origins.get("additionalProperties") is not False:
            raise GenerationError(f"{schema_path}: origins additionalProperties must be false")
    except (KeyError, TypeError) as error:
        raise GenerationError(f"{schema_path}: missing strict origins schema: {error}") from error
    document = load_json(path)
    unknown = set(document) - ALLOWED_CONFIG_KEYS
    missing = ALLOWED_CONFIG_KEYS - set(document)
    if unknown:
        raise GenerationError(f"{path}: unknown key(s): {', '.join(sorted(unknown))}")
    if missing:
        raise GenerationError(f"{path}: missing key(s): {', '.join(sorted(missing))}")
    if document["schema"] != PUBLIC_SURFACES_SCHEMA:
        raise GenerationError(f"{path}: unsupported schema {document['schema']!r}")
    origins = document["origins"]
    if not isinstance(origins, dict):
        raise GenerationError(f"{path}: origins must be an object")
    if set(origins) != ALLOWED_ORIGIN_KEYS:
        raise GenerationError(f"{path}: origins must contain exactly {sorted(ALLOWED_ORIGIN_KEYS)}")
    validated_origins = {key: _validate_origin(key, origins[key]) for key in origins}
    for key, value in validated_origins.items():
        expected = schema_origins.get("properties", {}).get(key, {}).get("const")
        if expected != value:
            raise GenerationError(f"{path}: origin {key!r} violates canonical schema constraint")
    pages = _validate_paths("pages", document["pages"])
    artifacts = _validate_paths("artifacts", document["artifacts"])
    if set(pages) & set(artifacts):
        raise GenerationError(f"{path}: pages and artifacts must not overlap")
    featured = document["featured_dataset_ids"]
    if (
        not isinstance(featured, list)
        or not featured
        or not all(isinstance(item, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_./?-]*", item) for item in featured)
        or len(featured) != len(set(featured))
    ):
        raise GenerationError(f"{path}: featured_dataset_ids must be a unique non-empty string array")
    return {
        "schema": document["schema"],
        "origins": validated_origins,
        "pages": pages,
        "artifacts": artifacts,
        "featured_dataset_ids": list(featured),
    }


def replace_owned_block(text: str, marker_name: str, rendered: str) -> str:
    """Replace one unique marker pair while rejecting malformed marker nesting."""
    begin = f"<!-- BEGIN {marker_name} -->"
    end = f"<!-- END {marker_name} -->"
    tokens = [(match.group(1), match.group(2), match.start()) for match in MARKER_RE.finditer(text)]
    stack: list[str] = []
    for kind, name, _ in tokens:
        if kind == "BEGIN":
            if stack:
                raise GenerationError(f"nested owned markers are forbidden: {stack[-1]!r}, {name!r}")
            stack.append(name)
        elif not stack or stack.pop() != name:
            raise GenerationError(f"reversed or mismatched owned marker: {name!r}")
    if stack:
        raise GenerationError(f"missing END marker for {stack[-1]!r}")
    if text.count(begin) != 1 or text.count(end) != 1:
        raise GenerationError(f"expected exactly one {begin!r}/{end!r} block")
    start = text.index(begin)
    finish = text.index(end)
    if finish < start:
        raise GenerationError(f"reversed markers for {marker_name!r}")
    body = rendered.rstrip("\n")
    return text[:start] + f"{begin}\n{body}\n{end}" + text[finish + len(end):]


def serialize_json(value: object) -> str:
    """Serialize public JSON with insertion order and exactly one final newline."""
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def atomic_write_text(path: Path, content: str) -> None:
    """Atomically replace a regular file, preserving its mode and rejecting symlinks."""
    if path.is_symlink():
        raise GenerationError(f"refusing to replace symlink target: {path}")
    if path.exists() and not path.is_file():
        raise GenerationError(f"refusing to replace non-file target: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as output:
            temporary = Path(output.name)
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except (OSError, UnicodeError) as error:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise GenerationError(f"cannot write {path}: {error}") from error


def atomic_write_json(path: Path, value: object) -> None:
    """Atomically write deterministic, ordered JSON."""
    atomic_write_text(path, serialize_json(value))


def publish_text_outputs(outputs: dict[Path, str], *, check: bool = False) -> bool:
    """Publish a fully rendered output set after validating every target first."""
    for path in outputs:
        if path.is_symlink():
            raise GenerationError(f"refusing to replace symlink target: {path}")
        if path.exists() and not path.is_file():
            raise GenerationError(f"refusing to replace non-file target: {path}")
    changed = any(not path.is_file() or path.read_text(encoding="utf-8") != content for path, content in outputs.items())
    if check:
        return changed
    for path, content in outputs.items():
        if not path.is_file() or path.read_text(encoding="utf-8") != content:
            atomic_write_text(path, content)
    return changed
