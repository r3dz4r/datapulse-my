#!/usr/bin/env python3
"""Content-addressed, atomic, bounded store for the historical-observation plane.

Implements the Phase 2 storage layout decided on 2026-09-15 (sections 1-3 of
the storage-plane decisions: the runtime root, the directory tree, the
``sha256:<hex>`` digest convention, and the write limits). Identity patterns
(observation ids, digest namespaces) come from the shipped envelope contract
``historical-observation.schema.json``; this module never invents identity of
its own.

The module is pure on import: no directory is created, no config is read, and
no environment variable is inspected until a public function is called. The
capture stage (Phase 3) writes through this store; nothing here fetches,
probes, or mutates any upstream source.

Deliberately absent (later briefs): retention, pruning, cleanup, budget and
duplicate-reporting gates, and checksum verification on read. This store only
refuses payloads that exceed the configured size limits.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

ROOT_ENVIRONMENT_VARIABLE: Final[str] = "DATAPULSE_OBSERVATION_ROOT"
DEFAULT_ROOT: Final[Path] = Path("/home/redza/runtime/datapulse-observations")

POLICY_CONFIG_NAME: Final[str] = "observation-policies.json"
POLICY_SCHEMA_CONST: Final[str] = "datapulse/v1/observation-policies"
LIMIT_NAMES: Final[tuple[str, ...]] = (
    "max_raw_bytes",
    "max_normalized_bytes",
    "retention_months",
    "total_budget_bytes",
)
ARCHIVING_MODES: Final[frozenset[str]] = frozenset({"full_vintage", "evidence_capture"})

# Same pattern as historical-observation.schema.json $defs.observationId.
# Repeated here verbatim so the store cannot drift from the contract.
OBSERVATION_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^obs-[a-z0-9][a-z0-9_-]{0,127}$")
DIGEST_PATTERN: Final[re.Pattern[str]] = re.compile(r"^sha256:[0-9a-f]{64}$")
MANIFEST_DAY_PATTERN: Final[re.Pattern[str]] = re.compile(r"^\d{4}-\d{2}-\d{2}$")

DIRECTORY_MODE: Final[int] = 0o750
FILE_MODE: Final[int] = 0o640


class ObservationStoreError(Exception):
    """Base class for every store failure; never silently swallowed."""


class PolicyConfigError(ObservationStoreError):
    """The observation policy config is missing, unreadable, or malformed."""


class DigestFormatError(ObservationStoreError):
    """A digest string does not match the sha256:<64 lowercase hex> convention."""


class ObjectNotFoundError(ObservationStoreError):
    """No object is stored under the given digest; the message names it."""


class PayloadTooLargeError(ObservationStoreError):
    """A payload exceeds its configured size limit; nothing was written."""


class EnvelopePlacementError(ObservationStoreError):
    """An envelope, policy, or manifest cannot be placed at a well-defined path."""


# ---------------------------------------------------------------------------
# Root resolution
# ---------------------------------------------------------------------------


def resolve_root(explicit: Path | str | None = None) -> Path:
    """Resolve the store root: explicit argument, then env var, then default.

    The root is never resolved against the current working directory: a
    relative value is an error, because a cwd-dependent archive silently
    scatters evidence across whatever directory a timer happened to run in.
    """
    if explicit is not None:
        candidate = Path(explicit).expanduser()
    else:
        from_environment = os.environ.get(ROOT_ENVIRONMENT_VARIABLE)
        candidate = Path(from_environment).expanduser() if from_environment else DEFAULT_ROOT
    if not candidate.is_absolute():
        raise ObservationStoreError(
            f"observation store root must be an absolute path, got {candidate}; set "
            f"{ROOT_ENVIRONMENT_VARIABLE} or pass an explicit absolute root — the store "
            "never resolves a root relative to the current working directory"
        )
    return candidate


# ---------------------------------------------------------------------------
# Canonical form — the repository's single digest convention
# ---------------------------------------------------------------------------


def canonical_json(payload: Any) -> bytes:
    """Canonical JSON bytes: sort_keys, ensure_ascii=False, compact separators.

    Identical to the convention in scripts/gen_attestations.py. A second
    convention here would let identical payloads hash differently, so none
    is introduced. Key order in the input never changes the output bytes.
    """
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_digest(data: bytes) -> str:
    """Digest string in the envelope contract's form: ``sha256:<64 hex>``."""
    return "sha256:" + hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Atomic writes with mandated modes
# ---------------------------------------------------------------------------


def _ensure_directory(directory: Path) -> None:
    """Create the directory (and missing parents) with mode 750.

    chmod runs after creation on every directory this call created, so the
    process umask can neither loosen nor tighten the mandated mode. Existing
    directories are left untouched.
    """
    missing: list[Path] = []
    step = directory
    while not step.exists() and step != step.parent:
        missing.append(step)
        step = step.parent
    if not missing:
        return
    directory.mkdir(parents=True, exist_ok=True)
    for created in missing:
        os.chmod(created, DIRECTORY_MODE)


def _atomic_write(path: Path, data: bytes) -> None:
    """Write bytes atomically: sibling temporary file, fsync, os.replace.

    A reader never observes a partial file at the final path, and no
    temporary file survives a successful call. Files are mode 640.
    """
    _ensure_directory(path.parent)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        os.fchmod(descriptor, FILE_MODE)
        with os.fdopen(descriptor, "wb") as temporary_file:
            temporary_file.write(data)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Digest validation
# ---------------------------------------------------------------------------


def _parse_digest(digest: str) -> str:
    if not isinstance(digest, str) or not DIGEST_PATTERN.fullmatch(digest):
        raise DigestFormatError(
            f"digest {digest!r} is malformed; expected 'sha256:' followed by exactly "
            "64 lowercase hexadecimal characters"
        )
    return digest[len("sha256:"):]


def _validate_observation_id(observation_id: str) -> None:
    if not isinstance(observation_id, str) or not OBSERVATION_ID_PATTERN.fullmatch(observation_id):
        raise EnvelopePlacementError(
            f"observation_id {observation_id!r} does not match the envelope contract "
            "pattern ^obs-[a-z0-9][a-z0-9_-]{0,127}$; the filesystem must not file an "
            "identity the contract rejects"
        )


def _validate_dataset_id(dataset_id: str) -> None:
    if not isinstance(dataset_id, str) or not dataset_id:
        raise EnvelopePlacementError("dataset_id must be a non-empty string")
    if "/" in dataset_id or "\\" in dataset_id:
        raise EnvelopePlacementError(
            f"dataset_id {dataset_id!r} must not contain a path separator"
        )
    if ".." in dataset_id or dataset_id == ".":
        raise EnvelopePlacementError(f"dataset_id {dataset_id!r} must not contain '..'")


# ---------------------------------------------------------------------------
# Blobs — raw source bytes, content-addressed
# ---------------------------------------------------------------------------


def put_blob(data: bytes, *, root: Path | None = None) -> str:
    """Store raw bytes at blobs/sha256/<first-two-hex>/<hex>.raw.

    Returns the digest string ``sha256:<64 hex>``. Identical bytes already on
    disk are never rewritten — content addressing makes the write an idempotent
    no-op, preserving the original file's timestamp as evidence. A payload
    over the configured ``max_raw_bytes`` is refused and nothing is written.
    """
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise TypeError("put_blob expects bytes-like data")
    blob = bytes(data)
    limits = global_limits()
    if len(blob) > limits["max_raw_bytes"]:
        raise PayloadTooLargeError(
            f"raw payload of {len(blob)} bytes exceeds max_raw_bytes="
            f"{limits['max_raw_bytes']} from config/{POLICY_CONFIG_NAME}; "
            "nothing was written"
        )
    hexdigest = hashlib.sha256(blob).hexdigest()
    digest = f"sha256:{hexdigest}"
    path = resolve_root(root) / "blobs" / "sha256" / hexdigest[:2] / f"{hexdigest}.raw"
    if path.exists():
        return digest
    _atomic_write(path, blob)
    return digest


def blob_path(digest: str, *, root: Path | None = None) -> Path:
    """Path a blob with this digest occupies (or would occupy). No I/O."""
    hexdigest = _parse_digest(digest)
    return resolve_root(root) / "blobs" / "sha256" / hexdigest[:2] / f"{hexdigest}.raw"


def read_blob(digest: str, *, root: Path | None = None) -> bytes:
    """Read back exactly the bytes put_blob stored. Does not re-verify digests."""
    path = blob_path(digest, root=root)
    if not path.is_file():
        raise ObjectNotFoundError(f"no blob stored for digest {digest} (expected {path})")
    return path.read_bytes()


# ---------------------------------------------------------------------------
# Normalized projections — canonical JSON, content-addressed
# ---------------------------------------------------------------------------


def put_normalized(payload: dict[str, Any], *, root: Path | None = None) -> str:
    """Store canonical JSON at normalized/sha256/<first-two-hex>/<hex>.json.

    Byte-stable: key order in the input cannot change the output bytes, so
    the same projection always lands on the same digest and path. Identical
    content already on disk is never rewritten.
    """
    if not isinstance(payload, dict):
        raise TypeError("put_normalized expects a dict payload")
    data = canonical_json(payload)
    limits = global_limits()
    if len(data) > limits["max_normalized_bytes"]:
        raise PayloadTooLargeError(
            f"normalized payload of {len(data)} bytes exceeds max_normalized_bytes="
            f"{limits['max_normalized_bytes']} from config/{POLICY_CONFIG_NAME}; "
            "nothing was written"
        )
    hexdigest = hashlib.sha256(data).hexdigest()
    digest = f"sha256:{hexdigest}"
    path = resolve_root(root) / "normalized" / "sha256" / hexdigest[:2] / f"{hexdigest}.json"
    if path.exists():
        return digest
    _atomic_write(path, data)
    return digest


def normalized_path(digest: str, *, root: Path | None = None) -> Path:
    """Path a normalized projection with this digest occupies. No I/O."""
    hexdigest = _parse_digest(digest)
    return resolve_root(root) / "normalized" / "sha256" / hexdigest[:2] / f"{hexdigest}.json"


def read_normalized(digest: str, *, root: Path | None = None) -> bytes:
    """Read back exactly the canonical JSON bytes put_normalized stored."""
    path = normalized_path(digest, root=root)
    if not path.is_file():
        raise ObjectNotFoundError(
            f"no normalized projection stored for digest {digest} (expected {path})"
        )
    return path.read_bytes()


# ---------------------------------------------------------------------------
# Envelopes, policies, manifests
# ---------------------------------------------------------------------------


def _utc_instant(observed_at: Any, context: str) -> datetime:
    if not isinstance(observed_at, str) or not observed_at.strip():
        raise EnvelopePlacementError(f"{context} must carry an ISO-8601 observed_at string")
    text = observed_at.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        moment = datetime.fromisoformat(text)
    except ValueError as error:
        raise EnvelopePlacementError(
            f"{context} observed_at {observed_at!r} is not a parseable ISO-8601 instant"
        ) from error
    if moment.tzinfo is None:
        raise EnvelopePlacementError(
            f"{context} observed_at {observed_at!r} must carry a timezone offset; "
            "a naive local time is ambiguous by design"
        )
    return moment.astimezone(timezone.utc)


def _normalize_observed_at(observed_at: Any) -> str:
    """Canonical UTC Z-form string, so index ordering is lexicographic."""
    moment = _utc_instant(observed_at, "observation")
    return moment.isoformat().replace("+00:00", "Z")


def put_envelope(
    dataset_id: str,
    observation_id: str,
    envelope: dict[str, Any],
    *,
    root: Path | None = None,
) -> Path:
    """File an envelope at envelopes/<dataset_id>/<YYYY>/<MM>/<observation_id>.json.

    YYYY/MM come from the envelope's own observed_at converted to UTC. The
    observation_id must satisfy the envelope contract's id pattern, and the
    dataset_id must be a single safe path component. Only placement-critical
    members are checked here; full contract validation is
    scripts/validate_historical_observation.py's job at capture time.
    """
    _validate_dataset_id(dataset_id)
    _validate_observation_id(observation_id)
    if not isinstance(envelope, dict):
        raise EnvelopePlacementError("envelope must be a JSON object")
    moment = _utc_instant(envelope.get("observed_at"), "envelope")
    path = (
        resolve_root(root)
        / "envelopes"
        / dataset_id
        / f"{moment:%Y}"
        / f"{moment:%m}"
        / f"{observation_id}.json"
    )
    _atomic_write(path, canonical_json(envelope))
    return path


def put_policy(dataset_id: str, policy: dict[str, Any], *, root: Path | None = None) -> Path:
    """Store a dataset's archive policy at policies/<dataset_id>.json."""
    _validate_dataset_id(dataset_id)
    if not isinstance(policy, dict):
        raise EnvelopePlacementError("policy must be a JSON object")
    path = resolve_root(root) / "policies" / f"{dataset_id}.json"
    _atomic_write(path, canonical_json(policy))
    return path


def write_manifest(day: str, manifest: dict[str, Any], *, root: Path | None = None) -> Path:
    """Store a per-cycle manifest at manifests/<YYYY-MM-DD>.json."""
    if not isinstance(day, str) or not MANIFEST_DAY_PATTERN.fullmatch(day):
        raise EnvelopePlacementError(f"manifest day {day!r} must match YYYY-MM-DD")
    if not isinstance(manifest, dict):
        raise EnvelopePlacementError("manifest must be a JSON object")
    path = resolve_root(root) / "manifests" / f"{day}.json"
    _atomic_write(path, canonical_json(manifest))
    return path


# ---------------------------------------------------------------------------
# Index — acceleration only, never the authority
# ---------------------------------------------------------------------------

OBSERVATION_COLUMNS: Final[tuple[str, ...]] = (
    "dataset_id",
    "observation_id",
    "observed_at",
    "source_digest",
    "observation_digest",
    "envelope_path",
)

_INDEX_TABLE = """
CREATE TABLE IF NOT EXISTS observations (
    dataset_id TEXT NOT NULL,
    observation_id TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    source_digest TEXT,
    observation_digest TEXT,
    envelope_path TEXT NOT NULL,
    PRIMARY KEY (dataset_id, observation_id)
)
"""

_INDEX_ORDER = (
    "CREATE INDEX IF NOT EXISTS observations_dataset_newest "
    "ON observations (dataset_id, observed_at DESC, observation_id DESC)"
)

_SELECT_NEWEST = (
    f"SELECT {', '.join(OBSERVATION_COLUMNS)} FROM observations "
    "WHERE dataset_id = ? ORDER BY observed_at DESC, observation_id DESC"
)

_INSERT_UPSERT = (
    f"INSERT INTO observations ({', '.join(OBSERVATION_COLUMNS)}) "
    "VALUES (?, ?, ?, ?, ?, ?) "
    "ON CONFLICT (dataset_id, observation_id) DO UPDATE SET "
    "observed_at = excluded.observed_at, "
    "source_digest = excluded.source_digest, "
    "observation_digest = excluded.observation_digest, "
    "envelope_path = excluded.envelope_path"
)


def index_path(*, root: Path | None = None) -> Path:
    """Path of the sqlite index: indexes/observations.sqlite. No I/O."""
    return resolve_root(root) / "indexes" / "observations.sqlite"


def ensure_index(*, root: Path | None = None) -> Path:
    """Create the index (idempotently) and return its path.

    The index answers "which observations exist for this dataset, newest
    first" without walking the envelope tree. It is an acceleration layer:
    deleting it must lose nothing, because every row is rebuildable from
    envelope files alone (see rebuild_index_from_envelopes).
    """
    path = index_path(root=root)
    _ensure_directory(path.parent)
    connection = sqlite3.connect(path)
    try:
        connection.execute(_INDEX_TABLE)
        connection.execute(_INDEX_ORDER)
        connection.commit()
    finally:
        connection.close()
    # sqlite honours the process umask on create; the layout mandates 640.
    os.chmod(path, FILE_MODE)
    return path


def _envelope_ref(envelope_path: Path | str, store_root: Path) -> str:
    """Store a root-relative posix reference so rows stay rebuild-comparable."""
    path = Path(envelope_path)
    try:
        return path.resolve().relative_to(store_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def upsert_observation(
    dataset_id: str,
    observation_id: str,
    observed_at: str,
    envelope_path: Path | str,
    *,
    source_digest: str | None = None,
    observation_digest: str | None = None,
    root: Path | None = None,
) -> None:
    """Insert or refresh one row in the index.

    observed_at is normalized to canonical UTC Z-form so newest-first
    ordering is a plain string sort regardless of the producer's offset.
    """
    _validate_dataset_id(dataset_id)
    _validate_observation_id(observation_id)
    normalized_at = _normalize_observed_at(observed_at)
    store_root = resolve_root(root)
    reference = _envelope_ref(envelope_path, store_root)
    path = ensure_index(root=store_root)
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            _INSERT_UPSERT,
            (dataset_id, observation_id, normalized_at, source_digest, observation_digest, reference),
        )
        connection.commit()
    finally:
        connection.close()


def list_observations(dataset_id: str, *, root: Path | None = None) -> list[dict[str, Any]]:
    """Rows for one dataset, newest first (ties broken by observation_id).

    Answers only from the index. An absent index yields an empty list after
    being created empty; the authoritative answer is always the envelope
    tree — call rebuild_index_from_envelopes first if the index may be stale.
    """
    _validate_dataset_id(dataset_id)
    path = ensure_index(root=root)
    connection = sqlite3.connect(path)
    try:
        rows = connection.execute(_SELECT_NEWEST, (dataset_id,)).fetchall()
    finally:
        connection.close()
    return [dict(zip(OBSERVATION_COLUMNS, row)) for row in rows]


def _envelope_row(store_root: Path, dataset_id: str, envelope_file: Path) -> tuple[Any, ...]:
    observation_id = envelope_file.stem
    _validate_observation_id(observation_id)
    try:
        envelope = json.loads(envelope_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise EnvelopePlacementError(f"cannot read envelope {envelope_file}: {error}") from error
    if not isinstance(envelope, dict) or envelope.get("observation_id") != observation_id:
        raise EnvelopePlacementError(
            f"envelope file {envelope_file} does not carry its own observation_id "
            f"{observation_id!r}; the index must not paper over a misfiled envelope"
        )
    declared_dataset = envelope.get("dataset_id")
    if declared_dataset is not None and declared_dataset != dataset_id:
        raise EnvelopePlacementError(
            f"envelope {observation_id} declares dataset_id {declared_dataset!r} "
            f"but is filed under {dataset_id!r}"
        )
    return (
        dataset_id,
        observation_id,
        _normalize_observed_at(envelope.get("observed_at")),
        envelope.get("source_digest"),
        envelope.get("observation_digest"),
        envelope_file.relative_to(store_root).as_posix(),
    )


def _write_fresh_index(store_root: Path, rows: list[tuple[Any, ...]]) -> None:
    directory = store_root / "indexes"
    _ensure_directory(directory)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".observations.sqlite.", suffix=".tmp", dir=directory
    )
    os.close(descriptor)
    try:
        connection = sqlite3.connect(temporary_name)
        try:
            connection.execute(_INDEX_TABLE)
            connection.execute(_INDEX_ORDER)
            connection.executemany(
                f"INSERT INTO observations ({', '.join(OBSERVATION_COLUMNS)}) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                rows,
            )
            connection.commit()
        finally:
            connection.close()
        os.chmod(temporary_name, FILE_MODE)
        os.replace(temporary_name, directory / "observations.sqlite")
    except BaseException:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise


def rebuild_index_from_envelopes(*, root: Path | None = None) -> int:
    """Reconstruct the index purely from envelope files; return the row count.

    The index is not the authority: deleting observations.sqlite and running
    this must reproduce the same rows, because every indexed fact is derived
    from a filed envelope. The replacement database is built beside the old
    one and moved into place atomically.
    """
    store_root = resolve_root(root)
    rows: list[tuple[Any, ...]] = []
    envelopes_directory = store_root / "envelopes"
    if envelopes_directory.is_dir():
        for dataset_directory in sorted(envelopes_directory.iterdir()):
            if not dataset_directory.is_dir():
                continue
            dataset_id = dataset_directory.name
            _validate_dataset_id(dataset_id)
            for envelope_file in sorted(dataset_directory.rglob("*.json")):
                rows.append(_envelope_row(store_root, dataset_id, envelope_file))
    _write_fresh_index(store_root, rows)
    return len(rows)


# ---------------------------------------------------------------------------
# Policy config — the store's limits, and the fail-closed mode lookup
# ---------------------------------------------------------------------------


def policies_config_path() -> Path:
    """Path of the policy config, anchored to the repo, never to the cwd."""
    return Path(__file__).resolve().parents[1] / "config" / POLICY_CONFIG_NAME


def _load_policy_config(config_path: Path | None = None) -> dict[str, Any]:
    path = config_path if config_path is not None else policies_config_path()
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise PolicyConfigError(f"cannot read observation policy config {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise PolicyConfigError(f"observation policy config {path} is not valid JSON: {error}") from error
    if not isinstance(document, dict) or document.get("schema") != POLICY_SCHEMA_CONST:
        raise PolicyConfigError(
            f"observation policy config {path} must declare schema {POLICY_SCHEMA_CONST!r}"
        )
    limits = document.get("limits")
    if not isinstance(limits, dict):
        raise PolicyConfigError(f"observation policy config {path} is missing its limits object")
    for name in LIMIT_NAMES:
        value = limits.get(name)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise PolicyConfigError(
                f"observation policy config {path}: limits.{name} must be a positive integer"
            )
    return document


def global_limits(*, config_path: Path | None = None) -> dict[str, int]:
    """The global limits the store enforces (raw/normalized caps, retention, budget).

    Retention and total budget are recorded here as decided limits; enforcing
    them is a later brief's gate, not this store's write path.
    """
    limits = _load_policy_config(config_path)["limits"]
    return {name: limits[name] for name in LIMIT_NAMES}


def archiving_mode(dataset_id: str, *, config_path: Path | None = None) -> str | None:
    """Archive mode for a dataset, or None when it has no policy entry.

    None means NOT permitted to archive. The config is an explicit allow
    list: a dataset with no entry fails closed to health-only observation and
    must never be treated as allowed by default.
    """
    if not isinstance(dataset_id, str):
        raise PolicyConfigError("dataset_id must be a string")
    datasets = _load_policy_config(config_path).get("datasets")
    entry = datasets.get(dataset_id) if isinstance(datasets, dict) else None
    if not isinstance(entry, dict):
        return None
    mode = entry.get("mode")
    if mode not in ARCHIVING_MODES:
        raise PolicyConfigError(
            f"observation policy config declares unknown mode {mode!r} for {dataset_id!r}"
        )
    return mode


def is_archiving_permitted(dataset_id: str, *, config_path: Path | None = None) -> bool:
    """True only for datasets with an archiving mode entry (fail closed)."""
    return archiving_mode(dataset_id, config_path=config_path) in ARCHIVING_MODES
