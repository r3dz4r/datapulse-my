#!/usr/bin/env python3
"""Enforcement and reporting gates for the observation store (Phase 2, brief B).

Turns the limits the store documents into checks that raise before a payload is
accepted, and produces the dry-run cleanup report that must exist before any
deletion is possible. Every function here is strictly read-only: this module
never creates, modifies, or removes stored objects — not even the sqlite index,
which is why the envelope tree (the store's authority, rebuildable into the
index) is walked directly instead of going through list_observations, whose
ensure_index call would create a database file on a fresh root and break the
"changes nothing on disk" contract of the dry run.
"""
from __future__ import annotations

import calendar
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

try:
    # Absolute form when the repo root is on sys.path (pipeline, pytest rootdir).
    from scripts.observation_store import (
        DIGEST_PATTERN,
        OBSERVATION_ID_PATTERN,
        POLICY_SCHEMA_CONST,
        ObservationStoreError,
        PayloadTooLargeError,
        PolicyConfigError,
        blob_path,
        global_limits,
        index_path,
        normalized_path,
        policies_config_path,
        read_blob,
        read_normalized,
        resolve_root,
        sha256_digest,
    )
except ModuleNotFoundError:  # bare form when scripts/ itself is on sys.path
    from observation_store import (
        DIGEST_PATTERN,
        OBSERVATION_ID_PATTERN,
        POLICY_SCHEMA_CONST,
        ObservationStoreError,
        PayloadTooLargeError,
        PolicyConfigError,
        blob_path,
        global_limits,
        index_path,
        normalized_path,
        policies_config_path,
        read_blob,
        read_normalized,
        resolve_root,
        sha256_digest,
    )

__all__ = [
    "raw_size_check",
    "normalized_size_check",
    "retention_report",
    "budget_report",
    "duplicate_report",
    "compression_anomalies",
    "cleanup_dry_run",
    "report_to_json",
    "IntegrityError",
    "verify_store",
    "read_blob_verified",
    "read_normalized_verified",
]

# Keep reasons — the cleanup taxonomy. would_remove entries carry their own
# cause ("expired" for envelopes, "unreferenced" for orphaned content); the
# four below are the only reasons an object survives a dry run.
KEEP_WITHIN_RETENTION: Final[str] = "within_retention"
KEEP_REFERENCED_BY_ENVELOPE: Final[str] = "referenced_by_envelope"
KEEP_POLICY_ABSENT: Final[str] = "policy_absent"
KEEP_UNREADABLE: Final[str] = "unreadable"

# A normalized projection is a faithful reshape of exactly one raw payload, so
# its size should stay in a fixed relationship to the raw bytes. Far below the
# floor the projection probably truncated content (silent evidence loss); far
# above the ceiling it is ballooning (a normalization bug and a budget risk).
# The band is deliberately wide: it flags drift, not style.
MIN_NORMALIZED_TO_RAW_RATIO: Final[float] = 0.05
MAX_NORMALIZED_TO_RAW_RATIO: Final[float] = 3.0
_RATIO_BAND_BASIS: Final[str] = (
    "below the floor the projection likely truncated content; above the "
    "ceiling it is ballooning relative to the raw payload"
)


# ---------------------------------------------------------------------------
# Instants — canonical UTC, lenient parse, month arithmetic
# ---------------------------------------------------------------------------


def _now_instant(now: datetime | None) -> datetime:
    """Resolve the injectable clock: default to current UTC, reject naive input."""
    if now is None:
        return datetime.now(timezone.utc)
    if not isinstance(now, datetime):
        raise ValueError(f"now must be a timezone-aware datetime, got {type(now).__name__}")
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware; a naive instant is ambiguous by design")
    return now.astimezone(timezone.utc)


def _z_form(moment: datetime) -> str:
    """Canonical UTC Z-form string, matching the store's index convention."""
    return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_instant(value: Any) -> datetime | None:
    """Lenient ISO-8601 parse; None for anything the store's writer would reject."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    if moment.tzinfo is None:
        return None
    return moment.astimezone(timezone.utc)


def _add_months(moment: datetime, months: int) -> datetime:
    """Instant plus whole months, clamping the day to the target month's length."""
    total = moment.month - 1 + months
    year = moment.year + total // 12
    month = total % 12 + 1
    day = min(moment.day, calendar.monthrange(year, month)[1])
    return moment.replace(year=year, month=month, day=day)


# ---------------------------------------------------------------------------
# Policy lookups — per-dataset overrides with global fallback
# ---------------------------------------------------------------------------


def _require_dataset_id(dataset_id: str) -> None:
    if not isinstance(dataset_id, str) or not dataset_id:
        raise PolicyConfigError("dataset_id must be a non-empty string")


def _positive_int(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return None


def _load_policy_document() -> dict[str, Any]:
    """Repo-anchored policy document, with its limits validated by the store itself.

    global_limits() runs first so a malformed limits object fails exactly the
    way the store's write path would, instead of only when a gate needs one of
    the numbers. The document is then re-read for the per-dataset overrides,
    which the store's public API does not expose.
    """
    global_limits()
    path = policies_config_path()
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise PolicyConfigError(f"cannot read observation policy config {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise PolicyConfigError(
            f"observation policy config {path} is not valid JSON: {error}"
        ) from error
    if not isinstance(document, dict) or document.get("schema") != POLICY_SCHEMA_CONST:
        raise PolicyConfigError(
            f"observation policy config {path} must declare schema {POLICY_SCHEMA_CONST!r}"
        )
    return document


def _datasets_table(document: dict[str, Any]) -> dict[str, Any]:
    datasets = document.get("datasets")
    return datasets if isinstance(datasets, dict) else {}


def _effective_raw_limit(dataset_id: str, datasets: dict[str, Any]) -> int:
    """The dataset's own max_raw_bytes when its policy declares one, else the global cap."""
    limits = global_limits()
    entry = datasets.get(dataset_id)
    declared = _positive_int(entry.get("max_raw_bytes")) if isinstance(entry, dict) else None
    return declared if declared is not None else limits["max_raw_bytes"]


def _effective_retention_months(dataset_id: str, datasets: dict[str, Any]) -> int | None:
    """Dataset retention in months, or None when the dataset has no policy entry.

    None means fail closed: with no policy there is no basis to expire anything,
    so such observations are never classified expired and their objects are
    kept under KEEP_POLICY_ABSENT.
    """
    limits = global_limits()
    entry = datasets.get(dataset_id)
    if not isinstance(entry, dict):
        return None
    declared = _positive_int(entry.get("retention_months"))
    return declared if declared is not None else limits["retention_months"]


# ---------------------------------------------------------------------------
# Size gates
# ---------------------------------------------------------------------------


def raw_size_check(dataset_id: str, size_bytes: int, *, root: Path | str | None = None) -> int:
    """Enforce the effective raw-payload limit for a dataset, returning the limit.

    Raises PayloadTooLargeError naming both the limit and the value when
    size_bytes exceeds the dataset's own max_raw_bytes (when its policy
    declares one) or the global max_raw_bytes otherwise.
    """
    _require_dataset_id(dataset_id)
    if not isinstance(size_bytes, int) or isinstance(size_bytes, bool):
        raise TypeError(f"size_bytes must be an int, got {type(size_bytes).__name__}")
    resolve_root(root)  # validation only, so a relative root fails like every store call
    datasets = _datasets_table(_load_policy_document())
    effective = _effective_raw_limit(dataset_id, datasets)
    if size_bytes > effective:
        entry = datasets.get(dataset_id)
        declared = _positive_int(entry.get("max_raw_bytes")) if isinstance(entry, dict) else None
        source = f"dataset {dataset_id!r} override" if declared is not None else "global limits"
        raise PayloadTooLargeError(
            f"raw payload of {size_bytes} bytes exceeds max_raw_bytes={effective} "
            f"({source}) from config/observation-policies.json; refused before anything "
            "was written"
        )
    return effective


def normalized_size_check(dataset_id: str, size_bytes: int, *, root: Path | str | None = None) -> int:
    """Enforce the global normalized-payload limit, returning the limit.

    The policy schema defines no per-dataset normalized override, so the global
    max_normalized_bytes is always the effective limit. Raises
    PayloadTooLargeError naming both the limit and the value when exceeded.
    """
    _require_dataset_id(dataset_id)
    if not isinstance(size_bytes, int) or isinstance(size_bytes, bool):
        raise TypeError(f"size_bytes must be an int, got {type(size_bytes).__name__}")
    resolve_root(root)
    effective = global_limits()["max_normalized_bytes"]
    if size_bytes > effective:
        raise PayloadTooLargeError(
            f"normalized payload of {size_bytes} bytes exceeds max_normalized_bytes="
            f"{effective} from config/observation-policies.json; refused before "
            "anything was written"
        )
    return effective


# ---------------------------------------------------------------------------
# Read-only store scans — the envelope tree is the authority
# ---------------------------------------------------------------------------


def _read_envelope(dataset_id: str, envelope_file: Path, store_root: Path) -> dict[str, Any]:
    """One envelope record, marked readable=False for anything the index rebuild would reject.

    An envelope that cannot be parsed, carries a naive or missing observed_at,
    misdeclares its own observation_id or dataset_id, or names a malformed
    digest is unreadable: the gates must not guess its retention window or its
    blob references, and cleanup must keep it.
    """
    record: dict[str, Any] = {
        "dataset_id": dataset_id,
        "observation_id": envelope_file.stem,
        "path": envelope_file.relative_to(store_root).as_posix(),
        "readable": False,
        "moment": None,
        "source_digest": None,
        "observation_digest": None,
    }
    if OBSERVATION_ID_PATTERN.fullmatch(record["observation_id"]) is None:
        return record
    try:
        envelope = json.loads(envelope_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return record
    if not isinstance(envelope, dict):
        return record
    if envelope.get("observation_id") != record["observation_id"]:
        return record
    declared_dataset = envelope.get("dataset_id")
    if declared_dataset is not None and declared_dataset != dataset_id:
        return record
    moment = _parse_instant(envelope.get("observed_at"))
    if moment is None:
        return record
    source_digest = envelope.get("source_digest")
    observation_digest = envelope.get("observation_digest")
    if source_digest is not None and DIGEST_PATTERN.fullmatch(source_digest) is None:
        return record
    if observation_digest is not None and DIGEST_PATTERN.fullmatch(observation_digest) is None:
        return record
    record.update(
        readable=True,
        moment=moment,
        source_digest=source_digest,
        observation_digest=observation_digest,
    )
    return record


def _scan_envelopes(store_root: Path) -> list[dict[str, Any]]:
    """Every envelope under envelopes/<dataset_id>/**, in a deterministic order."""
    envelopes_directory = store_root / "envelopes"
    if not envelopes_directory.is_dir():
        return []
    records: list[dict[str, Any]] = []
    for dataset_directory in sorted(envelopes_directory.iterdir()):
        if not dataset_directory.is_dir():
            continue
        for envelope_file in sorted(dataset_directory.rglob("*.json")):
            if envelope_file.is_file():
                records.append(_read_envelope(dataset_directory.name, envelope_file, store_root))
    return records


def _scan_content_addressed(
    directory: Path, suffix: str, store_root: Path
) -> tuple[list[Path], list[dict[str, str]]]:
    """Split a content-addressed tree into digest-named files and violations.

    A file only honours the addressing scheme when its stem is 64 lowercase hex
    characters and its parent directory is the first two of them; anything else
    is a violation, because the "one path per content" guarantee is only
    defined for digest-derived paths.
    """
    valid: list[Path] = []
    violations: list[dict[str, str]] = []
    if not directory.is_dir():
        return valid, violations
    for path in sorted(candidate for candidate in directory.rglob("*") if candidate.is_file()):
        stem = path.name.removesuffix(suffix)
        if path.name.endswith(suffix) and DIGEST_PATTERN.fullmatch(f"sha256:{stem}") and path.parent.name == stem[:2]:
            valid.append(path)
        else:
            violations.append(
                {
                    "path": path.relative_to(store_root).as_posix(),
                    "reason": f"path is not digest-derived (expected <first-two-hex>/<64 hex>{suffix})",
                }
            )
    return valid, violations


# ---------------------------------------------------------------------------
# Retention
# ---------------------------------------------------------------------------


def retention_report(*, root: Path | str | None = None, now: datetime | None = None) -> dict[str, Any]:
    """Classify every stored observation as within_retention or expired, with counts and details.

    Counts cover every observation the store knows (from the envelope tree),
    including policy_absent (no config entry — fail closed, never expirable)
    and unreadable entries; the expired list carries observation_id,
    dataset_id, observed_at and days_overdue.
    """
    store_root = resolve_root(root)
    moment_now = _now_instant(now)
    datasets = _datasets_table(_load_policy_document())
    counts = {
        "total": 0,
        "within_retention": 0,
        "expired": 0,
        "policy_absent": 0,
        "unreadable": 0,
    }
    expired_entries: list[dict[str, Any]] = []
    for record in _scan_envelopes(store_root):
        counts["total"] += 1
        if not record["readable"]:
            counts["unreadable"] += 1
            continue
        months = _effective_retention_months(record["dataset_id"], datasets)
        if months is None:
            counts["policy_absent"] += 1
            continue
        expiry = _add_months(record["moment"], months)
        if moment_now >= expiry:
            counts["expired"] += 1
            expired_entries.append(
                {
                    "observation_id": record["observation_id"],
                    "dataset_id": record["dataset_id"],
                    "observed_at": _z_form(record["moment"]),
                    "days_overdue": int((moment_now - expiry).total_seconds() // 86400),
                }
            )
        else:
            counts["within_retention"] += 1
    expired_entries.sort(key=lambda entry: (entry["dataset_id"], entry["observation_id"]))
    return {"now": _z_form(moment_now), "counts": counts, "expired": expired_entries}


# ---------------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------------


def _tree_bytes(directory: Path) -> int:
    """Sum of regular file sizes under a subtree (0 when absent)."""
    if not directory.is_dir():
        return 0
    try:
        return sum(path.stat().st_size for path in sorted(directory.rglob("*")) if path.is_file())
    except OSError as error:
        raise ObservationStoreError(f"cannot measure {directory}: {error}") from error


def budget_report(*, root: Path | str | None = None) -> dict[str, Any]:
    """Report total stored bytes against the configured budget, with headroom and overage.

    Totals cover the four governed categories (blobs, normalized, envelopes,
    indexes); headroom_bytes goes negative when the budget is exceeded, and
    overage_bytes is the non-negative excess.
    """
    store_root = resolve_root(root)
    budget = global_limits()["total_budget_bytes"]
    categories = {
        "blobs": _tree_bytes(store_root / "blobs"),
        "normalized": _tree_bytes(store_root / "normalized"),
        "envelopes": _tree_bytes(store_root / "envelopes"),
        "indexes": _tree_bytes(index_path(root=root).parent),
    }
    total = sum(categories.values())
    return {
        "bytes": {**categories, "total": total},
        "total_budget_bytes": budget,
        "headroom_bytes": budget - total,
        "exceeded": total > budget,
        "overage_bytes": max(0, total - budget),
    }


# ---------------------------------------------------------------------------
# Duplicates
# ---------------------------------------------------------------------------


def _duplicate_envelope_contents(store_root: Path) -> list[dict[str, Any]]:
    """Groups of byte-identical envelope files stored under more than one path.

    Envelopes are identity-addressed, not content-addressed, so a duplicate is
    possible (typically the same envelope misfiled under a second dataset);
    only a byte-level comparison can detect it.
    """
    groups: dict[str, list[str]] = {}
    envelopes_directory = store_root / "envelopes"
    if envelopes_directory.is_dir():
        for envelope_file in sorted(envelopes_directory.rglob("*.json")):
            if not envelope_file.is_file():
                continue
            try:
                content = envelope_file.read_bytes()
            except OSError:
                continue
            groups.setdefault(sha256_digest(content), []).append(
                envelope_file.relative_to(store_root).as_posix()
            )
    return [
        {"content_digest": digest, "kind": "envelope", "paths": paths}
        for digest, paths in sorted(groups.items())
        if len(paths) > 1
    ]


def duplicate_report(*, root: Path | str | None = None) -> dict[str, Any]:
    """Report duplicate content stored under more than one path, or state why none can exist.

    Blob and normalized objects are content-addressed — each path is a pure
    function of the payload's sha256 digest — so the same content cannot land
    on two paths without a sha256 collision; this scan verifies every stored
    path actually is digest-derived before asserting that guarantee. Envelope
    files are identity-addressed, so their bytes are hashed and compared.
    """
    store_root = resolve_root(root)
    blob_files, blob_violations = _scan_content_addressed(store_root / "blobs", ".raw", store_root)
    normalized_files, normalized_violations = _scan_content_addressed(
        store_root / "normalized", ".json", store_root
    )
    violations = sorted(
        blob_violations + normalized_violations, key=lambda violation: violation["path"]
    )
    duplicates = _duplicate_envelope_contents(store_root)
    if duplicates:
        case = "duplicates_found"
        explanation = (
            f"{len(duplicates)} duplicate content group(s) found; see duplicates. Blob and "
            "normalized objects remain impossible to duplicate by construction, but the "
            "listed envelope paths carry byte-identical content."
        )
    elif violations:
        case = "addressing_violations"
        explanation = (
            "Files exist under blobs/ or normalized/ that are not digest-derived, so the "
            "content-addressing guarantee (one path per content) cannot be asserted for "
            "them; investigate the violations before any cleanup."
        )
    else:
        case = "no_duplicates_found"
        explanation = (
            "No duplicate content stored. blobs/ and normalized/ are content-addressed: "
            "each path is a pure function of the payload's sha256 digest, so duplicate "
            "content under more than one path is impossible by construction (this scan "
            "verified every stored path is digest-derived). Envelope files are "
            "identity-addressed, so their bytes were hashed and compared: no two "
            "envelope paths carry identical bytes."
        )
    return {
        "case": case,
        "duplicates": duplicates,
        "addressing_violations": violations,
        "content_addressed": {
            "blob_paths": len(blob_files),
            "normalized_paths": len(normalized_files),
        },
        "explanation": explanation,
    }


# ---------------------------------------------------------------------------
# Compression anomalies
# ---------------------------------------------------------------------------


def compression_anomalies(*, root: Path | str | None = None) -> dict[str, Any]:
    """Flag normalized-to-raw size ratios that fall outside the documented band.

    Pairs come from envelope digests: source_digest sizes the raw blob,
    observation_digest sizes the normalized projection. Pairs where either
    side is missing from disk are not comparable and are skipped.
    """
    store_root = resolve_root(root)
    anomalies: list[dict[str, Any]] = []
    compared = 0
    for record in _scan_envelopes(store_root):
        if not record["readable"]:
            continue
        source_digest = record["source_digest"]
        observation_digest = record["observation_digest"]
        if not source_digest or not observation_digest:
            continue
        raw_file = blob_path(source_digest, root=store_root)
        normalized_file = normalized_path(observation_digest, root=store_root)
        if not (raw_file.is_file() and normalized_file.is_file()):
            continue
        compared += 1
        raw_size = raw_file.stat().st_size
        normalized_size = normalized_file.stat().st_size
        if raw_size == 0 or normalized_size == 0:
            violation = "empty_side"
            ratio: float | None = None
        else:
            ratio = normalized_size / raw_size
            if ratio < MIN_NORMALIZED_TO_RAW_RATIO:
                violation = "below_min"
            elif ratio > MAX_NORMALIZED_TO_RAW_RATIO:
                violation = "above_max"
            else:
                continue
        anomalies.append(
            {
                "dataset_id": record["dataset_id"],
                "observation_id": record["observation_id"],
                "source_digest": source_digest,
                "observation_digest": observation_digest,
                "raw_bytes": raw_size,
                "normalized_bytes": normalized_size,
                "ratio": round(ratio, 6) if ratio is not None else None,
                "violation": violation,
            }
        )
    anomalies.sort(key=lambda entry: (entry["dataset_id"], entry["observation_id"]))
    return {
        "band": {
            "min_ratio": MIN_NORMALIZED_TO_RAW_RATIO,
            "max_ratio": MAX_NORMALIZED_TO_RAW_RATIO,
            "basis": _RATIO_BAND_BASIS,
        },
        "pairs_compared": compared,
        "anomalies": anomalies,
    }


# ---------------------------------------------------------------------------
# Cleanup dry run — report only, never remove
# ---------------------------------------------------------------------------


def cleanup_dry_run(*, root: Path | str | None = None, now: datetime | None = None) -> dict[str, Any]:
    """Decide would_remove vs keep for every stored object with reasons, modifying nothing.

    Objects are blobs, normalized projections and envelope files. A blob (or
    normalized projection) referenced by any envelope is ALWAYS kept even when
    its observation is expired — content addressing shares bytes across
    observations, so removing a referenced blob destroys another observation's
    evidence. would_remove is therefore only ever proposed for expired
    envelopes and for unreferenced (orphaned) content. "unreadable" keeps more
    than unreadable envelopes: strays that break the addressing scheme, and
    orphans while any unreadable envelope exists, because an unparseable
    envelope's references cannot be proven absent.
    """
    store_root = resolve_root(root)
    moment_now = _now_instant(now)
    datasets = _datasets_table(_load_policy_document())
    records = _scan_envelopes(store_root)
    any_unreadable = any(not record["readable"] for record in records)

    blob_referrers: dict[str, list[str]] = {}
    normalized_referrers: dict[str, list[str]] = {}
    decisions: list[dict[str, Any]] = []

    for record in records:
        if not record["readable"]:
            decisions.append(
                {
                    "path": record["path"],
                    "kind": "envelope",
                    "decision": "keep",
                    "reason": KEEP_UNREADABLE,
                }
            )
            continue
        months = _effective_retention_months(record["dataset_id"], datasets)
        if months is None:
            state = "policy_absent"
        elif moment_now < _add_months(record["moment"], months):
            state = "within_retention"
        else:
            state = "expired"
        if state == "expired":
            decisions.append(
                {"path": record["path"], "kind": "envelope", "decision": "would_remove", "reason": "expired"}
            )
        else:
            decisions.append(
                {
                    "path": record["path"],
                    "kind": "envelope",
                    "decision": "keep",
                    "reason": (
                        KEEP_WITHIN_RETENTION if state == "within_retention" else KEEP_POLICY_ABSENT
                    ),
                }
            )
        # Expired envelopes still register their references: the ALWAYS-keep
        # rule for referenced blobs is evaluated against envelopes on disk.
        if record["source_digest"]:
            blob_referrers.setdefault(record["source_digest"], []).append(state)
        if record["observation_digest"]:
            normalized_referrers.setdefault(record["observation_digest"], []).append(state)

    def decide_content_addressed(
        directory: Path, suffix: str, kind: str, referrers: dict[str, list[str]]
    ) -> None:
        valid, violations = _scan_content_addressed(directory, suffix, store_root)
        for violation in violations:
            decisions.append(
                {"path": violation["path"], "kind": kind, "decision": "keep", "reason": KEEP_UNREADABLE}
            )
        for path in valid:
            digest = f"sha256:{path.name.removesuffix(suffix)}"
            states = referrers.get(digest, [])
            if states:
                # Strongest referrer state wins: a live observation outranks a
                # policy-absent one, which outranks reference-by-expired-envelope.
                if "within_retention" in states:
                    reason = KEEP_WITHIN_RETENTION
                elif "policy_absent" in states:
                    reason = KEEP_POLICY_ABSENT
                else:
                    reason = KEEP_REFERENCED_BY_ENVELOPE
                decisions.append(
                    {
                        "path": path.relative_to(store_root).as_posix(),
                        "kind": kind,
                        "decision": "keep",
                        "reason": reason,
                        "referring_observations": len(states),
                    }
                )
            elif any_unreadable:
                decisions.append(
                    {
                        "path": path.relative_to(store_root).as_posix(),
                        "kind": kind,
                        "decision": "keep",
                        "reason": KEEP_UNREADABLE,
                        "referring_observations": 0,
                    }
                )
            else:
                decisions.append(
                    {
                        "path": path.relative_to(store_root).as_posix(),
                        "kind": kind,
                        "decision": "would_remove",
                        "reason": "unreferenced",
                        "referring_observations": 0,
                    }
                )

    decide_content_addressed(store_root / "blobs", ".raw", "blob", blob_referrers)
    decide_content_addressed(store_root / "normalized", ".json", "normalized", normalized_referrers)

    decisions.sort(key=lambda decision: decision["path"])
    keep_by_reason = {reason: 0 for reason in (KEEP_WITHIN_RETENTION, KEEP_REFERENCED_BY_ENVELOPE, KEEP_POLICY_ABSENT, KEEP_UNREADABLE)}
    remove_by_reason = {"expired": 0, "unreferenced": 0}
    for decision in decisions:
        if decision["decision"] == "keep":
            keep_by_reason[decision["reason"]] += 1
        else:
            remove_by_reason[decision["reason"]] += 1
    return {
        "now": _z_form(moment_now),
        "counts": {
            "total_objects": len(decisions),
            "would_remove": sum(remove_by_reason.values()),
            "keep": sum(keep_by_reason.values()),
            "keep_by_reason": keep_by_reason,
            "would_remove_by_reason": remove_by_reason,
        },
        "decisions": decisions,
        "not_in_scope": {
            "paths": ["indexes/", "policies/", "manifests/"],
            "reason": (
                "indexes are a rebuildable acceleration layer, and policies/manifests are "
                "operator-owned projections with no expiry basis"
            ),
        },
    }


# ---------------------------------------------------------------------------
# Deterministic serialisation
# ---------------------------------------------------------------------------


def report_to_json(report: dict[str, Any]) -> str:
    """Serialise a report deterministically: sorted keys, compact separators, stable bytes.

    Matches the store's canonical_json convention (ensure_ascii=False) so a
    report serialised here hashes identically to any canonical re-encoding of
    the same document; allow_nan=False rejects values JSON cannot represent
    deterministically.
    """
    return json.dumps(
        report,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


# ---------------------------------------------------------------------------
# Integrity verification — content addressing is only a guarantee if it is checked
# ---------------------------------------------------------------------------


class IntegrityError(ObservationStoreError):
    """A stored object's bytes no longer match the digest that names them.

    Derived from ObservationStoreError so existing handlers that catch store
    failures keep catching this one. Raised when the digest a path claims and
    the digest the bytes hash to diverge; a missing object is absence, not
    corruption, and keeps raising the store's ObjectNotFoundError.
    """


def _classify_objects(
    directory: Path, suffix: str, kind: str, store_root: Path
) -> list[dict[str, Any]]:
    """One integrity record per file under a content-addressed tree.

    Files honouring the addressing scheme are read and their bytes re-hashed:
    the digest encoded in the filename is the claim, the recomputed SHA-256 is
    the evidence, and a divergence is "corrupt". Files that break the scheme
    are "misnamed"; files that cannot be read at all are "unreadable". Nothing
    here writes, repairs, or removes — classification only.
    """
    records: list[dict[str, Any]] = []
    valid, violations = _scan_content_addressed(directory, suffix, store_root)
    for violation in violations:
        records.append({"classification": "misnamed", "kind": kind, **violation})
    for path in valid:
        digest = f"sha256:{path.name.removesuffix(suffix)}"
        relative = path.relative_to(store_root).as_posix()
        try:
            data = path.read_bytes()
        except OSError as error:
            records.append(
                {
                    "classification": "unreadable",
                    "kind": kind,
                    "path": relative,
                    "digest": digest,
                    "error": str(error),
                }
            )
            continue
        actual = sha256_digest(data)
        if actual == digest:
            records.append({"classification": "ok", "kind": kind, "path": relative, "digest": digest})
        else:
            records.append(
                {
                    "classification": "corrupt",
                    "kind": kind,
                    "path": relative,
                    "digest": digest,
                    "actual_digest": actual,
                }
            )
    return records


def verify_store(*, root: Path | str | None = None) -> dict[str, Any]:
    """Sweep every content-addressed object and envelope reference, modifying nothing.

    Each file under blobs/ and normalized/ is re-hashed and classified
    "ok", "corrupt" (bytes no longer match the digest in the filename),
    "unreadable", or "misnamed". Each readable envelope's source_digest and
    observation_digest is then resolved against the stored blobs and
    projections; a reference with no file behind it is reported as dangling,
    with the dataset id and observation id that carries it. Unreadable
    envelopes can prove their references neither present nor absent, so they
    are counted, not guessed at.

    The return value always carries a count for every classification: a store
    with nothing wrong reports explicit zeros, never an emptiness that could
    be mistaken for "no data". The verifier reports and raises; it never
    repairs, rewrites, or removes stored bytes.
    """
    store_root = resolve_root(root)
    object_records = sorted(
        _classify_objects(store_root / "blobs", ".raw", "blob", store_root)
        + _classify_objects(store_root / "normalized", ".json", "normalized", store_root),
        key=lambda record: record["path"],
    )
    dangling: list[dict[str, Any]] = []
    envelopes_total = 0
    envelopes_unreadable = 0
    for record in _scan_envelopes(store_root):
        envelopes_total += 1
        if not record["readable"]:
            envelopes_unreadable += 1
            continue
        for field, digest in (
            ("source_digest", record["source_digest"]),
            ("observation_digest", record["observation_digest"]),
        ):
            if not digest:
                continue
            expected = (
                blob_path(digest, root=store_root)
                if field == "source_digest"
                else normalized_path(digest, root=store_root)
            )
            if not expected.is_file():
                dangling.append(
                    {
                        "dataset_id": record["dataset_id"],
                        "observation_id": record["observation_id"],
                        "field": field,
                        "digest": digest,
                        "expected_path": expected.relative_to(store_root).as_posix(),
                    }
                )
    dangling.sort(key=lambda entry: (entry["dataset_id"], entry["observation_id"], entry["field"]))
    failures = {
        classification: [record for record in object_records if record["classification"] == classification]
        for classification in ("corrupt", "unreadable", "misnamed")
    }
    counts = {
        "total_objects": len(object_records),
        "ok": sum(1 for record in object_records if record["classification"] == "ok"),
        "corrupt": len(failures["corrupt"]),
        "unreadable": len(failures["unreadable"]),
        "misnamed": len(failures["misnamed"]),
        "envelopes": envelopes_total,
        "envelopes_unreadable": envelopes_unreadable,
        "dangling_references": len(dangling),
    }
    intact = (
        counts["corrupt"] == 0
        and counts["unreadable"] == 0
        and counts["misnamed"] == 0
        and not dangling
    )
    return {
        "counts": counts,
        "failures": failures,
        "dangling_references": dangling,
        "ok": intact,
    }


def read_blob_verified(digest: str, *, root: Path | str | None = None) -> bytes:
    """Read a blob through the store and verify its bytes against its digest.

    The bytes are returned only when their recomputed SHA-256 equals the
    digest naming them. On divergence, IntegrityError names the digest and
    both values — expected (what the path claims) and actual (what the bytes
    hash to). This is an additional verified route: the store's existing read
    path is unchanged, and a missing object still raises the store's
    ObjectNotFoundError rather than being reported as corruption.
    """
    data = read_blob(digest, root=root)
    actual = sha256_digest(data)
    if actual != digest:
        raise IntegrityError(
            f"blob {digest} is corrupt: expected digest {digest}, actual digest {actual} "
            f"({len(data)} bytes on disk do not match the digest that names them); "
            "the bytes are refused as evidence and nothing was modified"
        )
    return data


def read_normalized_verified(digest: str, *, root: Path | str | None = None) -> bytes:
    """Read a normalized projection through the store and verify it against its digest.

    Same contract as read_blob_verified, for canonical JSON projections: the
    stored bytes must hash to the digest in their filename, or IntegrityError
    is raised naming the digest and both the expected and actual values.
    """
    data = read_normalized(digest, root=root)
    actual = sha256_digest(data)
    if actual != digest:
        raise IntegrityError(
            f"normalized projection {digest} is corrupt: expected digest {digest}, "
            f"actual digest {actual} ({len(data)} bytes on disk do not match the "
            "digest that names them); the bytes are refused as evidence and "
            "nothing was modified"
        )
    return data
