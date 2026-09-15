#!/usr/bin/env python3
"""Capture source responses at observation time and file truthful envelopes.

A retained observation must be created truthfully rather than reconstructed
later.  An envelope that claims ``capture_status: "captured"`` with nothing
behind it destroys the archive's value: the lie is only discovered years
later when someone tries to replay.  A false capture claim is worse than no
capture, so every claim this module files is backed by bytes the store
actually retained.

Decision table (single source of truth: :func:`capture_decision`)
-----------------------------------------------------------------
1. Policy denies capture (``observation_store.is_archiving_permitted`` is
   false, or the configured archiving mode is absent) -> ``not_captured``
   with ``capture_policy="none"``; reason names the policy; no bytes are
   written.  The config is an explicit allow list and fails closed.
2. No bytes arrived, or the transfer was truncated/non-200 -> ``failed``
   when no bytes arrived, ``partial`` when some did; reason names the
   condition.  Incomplete bytes are never retained as a capture.
3. Policy declines raw bytes (a ``capture_raw_bytes: false`` entry, or an
   ``evidence_capture`` entry that does not declare it) ->
   ``metadata_only``; raw-byte capture was not attempted, so nothing is
   written.  Claiming ``captured`` for bytes the operator explicitly
   refused to retain would be a false capture claim.
4. Body exceeds the effective raw-size limit (``observation_gates.
   raw_size_check`` raises
   :class:`~observation_store.PayloadTooLargeError`) -> ``not_captured``;
   reason names the limit; nothing is written, not even a partial file.
5. Otherwise (complete, successful, within limits) -> ``captured``, with the
   archiving mode mapped onto the public ``capture_policy`` vocabulary
   (``full_vintage``->``full_source_bytes``, ``evidence_capture``->
   ``shape_fingerprint_only``, ``health_only``->``metadata_only``,
   ``not_capturable``->``none``).

When ``store=False`` the call only previews: nothing is retained, so a
"would capture" decision is reported truthfully as ``capture_status:
"metadata_only"`` — a preview envelope claiming ``captured`` would be the
false-capture failure mode this module exists to prevent.

Truth rules
-----------
* ``source_digest`` is non-null only when the capture status is
  ``"captured"``, and is exactly what ``observation_store.put_blob``
  returned: the digest of the retained bytes, never of a re-serialization,
  decoded string, or normalized form.
* A failed or denied capture never yields ``replay_state: "replayable"``.
  This module never retains partial bytes, so nothing retained ->
  ``metadata_only``.
* Capture never asserts verification: ``verification.verification_status``
  is ``"unverified"`` here.
* Unmeasured members are declared, never guessed: each goes into
  ``unknown_reasons`` (schema vocabulary only) when genuinely unresolved,
  or carries a ``not_measured``/``not_delivered`` provenance basis whose
  ``not_measured_reason`` explains why.
* Raw bytes are never overwritten with normalized forms; a member that
  cannot be computed is ``null`` with provenance saying why.
* ``observed_at`` is when DataPulse filed the observation; ``retrieved_at``
  is when the transfer completed (``RetrievalResult.retrieved_ended_at``);
  ``source_content_date`` is the source's own vintage claim.  They are never
  conflated and never substituted for one another.

Seal order (documented so ``observation_digest`` is reproducible)
-----------------------------------------------------------------
1. ``inner`` = ``observation:sha256:`` + SHA-256 over the canonical JSON of
   the envelope without ``observation_digest`` and without ``cycle_root``.
2. ``cycle_root`` = single-leaf ``merkle-sha256`` commitment over ``inner``;
   at capture time the cycle contains exactly this observation (cycle
   aggregation and proof issuance are a later phase).
3. ``observation_digest`` = ``observation:sha256:`` + SHA-256 over the
   canonical JSON of the envelope without ``observation_digest``, so it
   covers ``cycle_root`` and every other member exactly as filed.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import logging
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Final, Mapping, Sequence

try:
    # Absolute form when the repo root is on sys.path (pipeline, pytest rootdir).
    from scripts.observation_gates import raw_size_check
    from scripts.observation_store import (
        PayloadTooLargeError,
        PolicyConfigError,
        archiving_mode,
        canonical_json,
        is_archiving_permitted,
        list_observations,
        policies_config_path,
        put_blob,
        put_envelope,
        read_blob,
        sha256_digest,
        upsert_observation,
    )
    from scripts.validate_historical_observation import validate_envelope
except ModuleNotFoundError:  # bare form when scripts/ itself is on sys.path
    from observation_gates import raw_size_check
    from observation_store import (
        PayloadTooLargeError,
        PolicyConfigError,
        archiving_mode,
        canonical_json,
        is_archiving_permitted,
        list_observations,
        policies_config_path,
        put_blob,
        put_envelope,
        read_blob,
        sha256_digest,
        upsert_observation,
    )
    from validate_historical_observation import validate_envelope

__all__ = [
    "RetrievalResult",
    "CaptureError",
    "EnvelopeValidationError",
    "capture_decision",
    "capture_observation",
    "main",
]

logger = logging.getLogger(__name__)


class CaptureError(RuntimeError):
    """Raised when a capture cannot proceed truthfully."""


class EnvelopeValidationError(CaptureError):
    """Raised when an envelope fails validation before reaching the store."""


@dataclass(frozen=True)
class RetrievalResult:
    """One completed HTTP retrieval of a dataset source, as observed at transfer time.

    Attributes:
        source_url: The canonical source URL recorded in the manifest.
        observed_request_url: The URL actually requested this cycle (may
            differ from ``source_url`` after redirects).
        http_status: HTTP status code returned by the source.
        content_type: Value of the ``Content-Type`` response header, if sent.
        retrieved_started_at: ISO-8601 UTC instant the transfer started.
        retrieved_ended_at: ISO-8601 UTC instant the transfer ended.
        body: Raw response bytes, or ``None`` when nothing arrived.
        etag: Value of the ``ETag`` response header, if sent.
        last_modified: Value of the ``Last-Modified`` response header, if sent.
        source_content_date: The content date asserted by the source itself
            (header or payload), if any.  Never used as an observation time.
        truncated: True when the transfer ended before the full body arrived.
    """

    source_url: str
    observed_request_url: str
    http_status: int
    content_type: str | None
    retrieved_started_at: str
    retrieved_ended_at: str
    body: bytes | None
    etag: str | None
    last_modified: str | None
    source_content_date: str | None
    truncated: bool = False


REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[1]

SCHEMA_CONST: Final[str] = "historical-observation/v2"
NORMALIZATION_PROFILE_VERSION: Final[str] = "datapulse-normalization-profile/v1"
IDENTITY_LIMITATION: Final[str] = (
    "Identity is declared or independently supported; it is not a certification "
    "of authority, control, or authenticity."
)
VERIFICATION_LIMITATION: Final[str] = (
    "Verification status is cryptographic and procedural only; it is neither a "
    "freshness classification nor a statement of semantic truth."
)

CAPTURE_POLICY_BY_MODE: Final[Mapping[str, str]] = {
    "full_vintage": "full_source_bytes",
    "evidence_capture": "shape_fingerprint_only",
    "health_only": "metadata_only",
    "not_capturable": "none",
    "none": "none",
}

SOURCE_DIGEST_PATTERN: Final[re.Pattern[str]] = re.compile(r"^sha256:[0-9a-f]{64}$")
OBSERVATION_DIGEST_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^observation:sha256:[0-9a-f]{64}$"
)
DATE_PATTERN: Final[re.Pattern[str]] = re.compile(r"^\d{4}-\d{2}-\d{2}$")

NULL_COUNTERS: Final[dict[str, None]] = {
    "rows": None,
    "delivered": None,
    "empty": None,
    "stringified": None,
    "truncated": None,
}

_FUELPRICE_CSV: Final[bytes] = (
    "TIMESTAMP,SERIES,RON95,RON97,DIESEL\n"
    "2026-09-10,weekly,2.05,3.35,2.88\n"
    "2026-09-03,weekly,2.05,3.35,2.88\n"
    "2026-08-27,weekly,2.05,3.32,2.85\n"
    "2026-08-20,weekly,2.05,3.30,2.80\n"
    "2026-08-13,weekly,2.05,3.28,2.78\n"
    "2026-08-06,weekly,2.05,3.27,2.75\n"
    "2026-07-30,weekly,2.05,3.25,2.72\n"
).encode("utf-8")

_CPI_CSV: Final[bytes] = (
    "period,series,index\n"
    "2026-08,all_items,133.9\n"
    "2026-07,all_items,133.6\n"
    "2026-06,all_items,133.4\n"
).encode("utf-8")


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _provenance(
    basis: str,
    *,
    state: str = "measured",
    reason: str | None = None,
    transform: str | None = None,
) -> dict[str, Any]:
    """One field_provenance entry; ``derived`` follows the schema's basis rule."""
    derived = basis in ("platform_computed", "configured_by_policy")
    return {
        "basis": basis,
        "derived": derived,
        "state": state,
        "not_measured_reason": reason,
        "transform": transform,
        "counters": dict(NULL_COUNTERS),
    }


def _utc_z_form(moment: datetime, context: str) -> str:
    """Canonical UTC Z-form ISO-8601 string; naive instants are rejected."""
    if moment.tzinfo is None:
        raise CaptureError(
            f"{context} must be a timezone-aware instant; "
            "a naive local time is ambiguous by design"
        )
    return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_instant(value: str, context: str) -> str:
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        moment = datetime.fromisoformat(text)
    except ValueError as error:
        raise CaptureError(f"{context} {value!r} is not a parseable ISO-8601 instant") from error
    return _utc_z_form(moment, context)


def _observation_instant(now: datetime | str | None) -> str:
    """When DataPulse files the observation; never the source's own date."""
    if now is None:
        return _utc_z_form(datetime.now(timezone.utc), "now")
    if isinstance(now, datetime):
        return _utc_z_form(now, "now")
    return _parse_instant(now, "now")


def _observation_id(dataset_id: str, observed_at: str) -> str:
    """Deterministic id from dataset_id plus the observation instant.

    The same dataset observed at the same instant yields the same id, so an
    idempotent re-file lands on the same path rather than forking history.
    """
    stamp = observed_at[:19].replace("-", "").replace(":", "").lower()
    slug = re.sub(r"[^a-z0-9_-]+", "-", dataset_id.lower()).strip("-") or "dataset"
    tag = hashlib.sha256(f"{dataset_id}\n{observed_at}".encode("utf-8")).hexdigest()[:8]
    return f"obs-{slug[:64]}-{stamp}-{tag}"


def _contract_digest() -> str:
    """Digest of the producing code: this module's own source bytes."""
    return "contract:sha256:" + hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _parse_content_date(value: str | None) -> tuple[str | None, bool]:
    """``(date-or-None, given-but-unparseable)`` for the source's vintage claim."""
    if value is None or not str(value).strip():
        return (None, False)
    text = str(value).strip()
    if DATE_PATTERN.fullmatch(text):
        try:
            date.fromisoformat(text)
            return (text, False)
        except ValueError:
            pass
    return (None, True)


def _policy_entry(dataset_id: str, config_path: Path | None) -> dict[str, Any] | None:
    """The dataset's raw policy entry, or None when it has none."""
    path = config_path if config_path is not None else policies_config_path()
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PolicyConfigError(f"cannot read observation policy config {path}: {error}") from error
    datasets = document.get("datasets") if isinstance(document, dict) else None
    entry = datasets.get(dataset_id) if isinstance(datasets, dict) else None
    return entry if isinstance(entry, dict) else None


# ---------------------------------------------------------------------------
# The decision table
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Decision:
    """One row of the decision table plus the facts behind it."""

    status: str
    policy: str
    reason: str
    mode: str | None
    entry: dict[str, Any] | None
    digest_reason: str  # FP-8 vocabulary reason for a null source_digest; "" when captured


def _decide(dataset_id: str, retrieval: RetrievalResult, config_path: Path | None) -> _Decision:
    mode = archiving_mode(dataset_id, config_path=config_path)
    if not is_archiving_permitted(dataset_id, config_path=config_path):
        if mode is None:
            reason = (
                f"observation policy config has no entry for dataset {dataset_id!r}; "
                "archiving fails closed and capture was not attempted"
            )
        else:
            reason = (
                f"observation policy for dataset {dataset_id!r} declares mode {mode!r}; "
                "capture was not attempted"
            )
        return _Decision("not_captured", "none", reason, mode, None, "capture_not_attempted")

    policy = CAPTURE_POLICY_BY_MODE[mode]
    entry = _policy_entry(dataset_id, config_path)
    body = retrieval.body
    has_bytes = isinstance(body, (bytes, bytearray)) and len(body) > 0

    if not has_bytes:
        detail = "no bytes arrived (body empty or missing)"
        if retrieval.http_status != 200:
            detail += f"; http_status={retrieval.http_status}"
        return _Decision("failed", policy, detail, mode, entry, "source_did_not_deliver")

    if retrieval.truncated:
        reason = (
            f"transfer truncated after {len(body)} bytes (http_status={retrieval.http_status}); "
            "incomplete bytes are never retained as a capture"
        )
        return _Decision("partial", policy, reason, mode, entry, "capture_failed")

    if retrieval.http_status != 200:
        reason = (
            f"http_status={retrieval.http_status} delivered {len(body)} bytes; "
            "a non-200 response is not a complete capture"
        )
        return _Decision("partial", policy, reason, mode, entry, "capture_failed")

    if entry is not None and entry.get("capture_raw_bytes") is False:
        reason = (
            f"policy for dataset {dataset_id!r} declares capture_raw_bytes=false; "
            "raw bytes are not captured by design and capture was not attempted"
        )
        return _Decision("metadata_only", policy, reason, mode, entry, "capture_not_attempted")

    if mode == "evidence_capture" and (entry is None or "capture_raw_bytes" not in entry):
        reason = (
            f"policy for dataset {dataset_id!r} (mode evidence_capture) does not declare "
            "capture_raw_bytes; raw byte capture fails closed"
        )
        return _Decision("metadata_only", policy, reason, mode, entry, "capture_not_attempted")

    try:
        limit = raw_size_check(dataset_id, len(body))
    except PayloadTooLargeError as error:
        reason = f"raw payload of {len(body)} bytes was refused by the size gate: {error}"
        return _Decision("not_captured", policy, reason, mode, entry, "capture_not_attempted")

    reason = f"complete response of {len(body)} bytes within the effective raw limit {limit}"
    return _Decision("captured", policy, reason, mode, entry, "")


def capture_decision(
    dataset_id: str,
    retrieval: RetrievalResult,
    *,
    config_path: str | Path | None = None,
) -> tuple[str, str, str]:
    """Pure decision over whether and how a retrieval may be captured.

    No bytes are written and no store paths are touched; this function is
    the single source of the decision table documented at module scope.

    Args:
        dataset_id: The dataset the retrieval belongs to.
        retrieval: The completed retrieval to judge.
        config_path: Optional override for the observation-policy config
            location, forwarded to the policy readers.

    Returns:
        ``(capture_status, capture_policy, reason)`` where
        ``capture_status`` is one of ``captured | partial | failed |
        metadata_only | not_captured`` and ``capture_policy`` uses the
        public vocabulary (``full_source_bytes | shape_fingerprint_only |
        metadata_only | none``).

    Raises:
        observation_store.PolicyConfigError: If the policy config is
            missing, unreadable, or malformed.
    """
    decision = _decide(dataset_id, retrieval, Path(config_path) if config_path else None)
    return (decision.status, decision.policy, decision.reason)


# ---------------------------------------------------------------------------
# History linkage
# ---------------------------------------------------------------------------


def _previous_history(
    dataset_id: str,
    previous: Mapping[str, Any] | None,
    current_digest: str | None,
    *,
    store: bool,
    root: Path | None,
) -> tuple[str | None, str | None, str | None]:
    """Resolve ``(previous_observation_id, previous_observation_digest, change)``.

    An explicit ``previous`` envelope wins; otherwise, when filing, the
    store index answers.  A preview with no history input declares the
    history unknown rather than guessing ``first_observation`` — the index
    of a store never consulted is not evidence.
    """
    if previous is None and not store:
        return (None, None, "unknown")
    try:
        from scripts.observation_predecessors import PredecessorError, resolve_predecessor
    except ModuleNotFoundError:  # bare form when scripts/ itself is on sys.path
        from observation_predecessors import PredecessorError, resolve_predecessor

    # This signature predates predecessor proof and cannot carry the filing
    # instant, so the delegation bounds ordering by the observation clock —
    # the same clock that produced this capture's observed_at, and the only
    # ordering evidence reachable from here.
    try:
        link = resolve_predecessor(
            dataset_id, _observation_instant(None), root=root, explicit=previous
        )
    except PredecessorError as error:
        raise CaptureError(
            f"predecessor link refused ({error.constraint}): {error.message}"
        ) from error

    if link.relation_basis == "none":
        return (None, None, "first_observation")

    previous_source_digest: str | None = None
    if previous is not None:
        source = previous.get("source_digest")
    else:
        source = None
        for row in list_observations(dataset_id, root=root):
            if row["observation_id"] == link.observation_id:
                source = row.get("source_digest")
                break
    if isinstance(source, str) and SOURCE_DIGEST_PATTERN.fullmatch(source):
        previous_source_digest = source

    previous_id = link.previous_observation_id
    previous_digest = link.previous_observation_digest
    if current_digest is not None and previous_source_digest is not None:
        change = "unchanged" if current_digest == previous_source_digest else "changed"
        return (previous_id, previous_digest, change)
    return (previous_id, previous_digest, "unknown")


# ---------------------------------------------------------------------------
# Envelope construction
# ---------------------------------------------------------------------------


def _declared_entries(decision: _Decision) -> list[dict[str, Any]]:
    config_basis = "operator-reviewed entry in config/observation-policies.json"
    entries: list[dict[str, Any]] = []
    if decision.entry is None:
        entries.append(
            {
                "subject": "archiving_mode",
                "value": "none",
                "basis": "no entry in config/observation-policies.json; archiving fails closed",
            }
        )
        return entries
    entries.append(
        {"subject": "archiving_mode", "value": decision.mode, "basis": config_basis}
    )
    entries.append(
        {"subject": "capture_raw_bytes", "value": decision.entry.get("capture_raw_bytes"), "basis": config_basis}
    )
    raw_limit = decision.entry.get("max_raw_bytes")
    entries.append(
        {
            "subject": "max_raw_bytes",
            "value": raw_limit if isinstance(raw_limit, int) and not isinstance(raw_limit, bool) else None,
            "basis": config_basis,
        }
    )
    return entries


def _observed_entries(retrieval: RetrievalResult, decision: _Decision) -> list[dict[str, Any]]:
    transfer_basis = "recorded from the completed transfer at capture time"
    body = retrieval.body if isinstance(retrieval.body, (bytes, bytearray)) else b""
    entries: list[dict[str, Any]] = [
        {"subject": "http_status", "value": retrieval.http_status, "basis": transfer_basis},
        {"subject": "byte_count", "value": len(body), "basis": transfer_basis},
        {"subject": "truncated", "value": bool(retrieval.truncated), "basis": transfer_basis},
        {"subject": "content_type", "value": retrieval.content_type, "basis": transfer_basis},
        {"subject": "etag", "value": retrieval.etag, "basis": transfer_basis},
        {"subject": "last_modified", "value": retrieval.last_modified, "basis": transfer_basis},
        {
            "subject": "capture_reason",
            "value": decision.reason,
            "basis": "capture decision table outcome for this observation",
        },
    ]
    return entries


def _claim_boundary(status: str, retained: bool) -> dict[str, list[str]]:
    sealed = [
        "the observation was sealed at observed_at and is committed by observation_digest",
        "this observation is unverified: no verification was performed at capture time",
    ]
    fresh_boundary = [
        "that the content is fresh, complete, or correct — freshness is a separate axis",
        "that capture implies verification or semantic truth",
        "that the source is authoritative, controlled, or authentic",
    ]
    if retained:
        return {
            "may_conclude": [
                "the bytes named by source_digest are exactly the bytes observed at retrieved_at, retained in full",
                *sealed,
            ],
            "may_not_conclude": fresh_boundary,
        }
    return {
        "may_conclude": [
            f"no source bytes were retained for this dataset at observed_at (capture_status: {status})",
            *sealed,
        ],
        "may_not_conclude": [
            "that a source_digest exists for this observation",
            "that the source content can be replayed from this observation",
            *fresh_boundary,
        ],
    }


def _seal(envelope: dict[str, Any]) -> None:
    """Fill cycle_root then observation_digest, in the documented seal order."""
    core = {key: value for key, value in envelope.items() if key not in ("observation_digest", "cycle_root")}
    inner = "observation:sha256:" + hashlib.sha256(canonical_json(core)).hexdigest()
    envelope["cycle_root"] = {
        "root": "cycle-root:sha256:" + hashlib.sha256(canonical_json([inner])).hexdigest(),
        "algorithm": "merkle-sha256",
        "observation_count": 1,
    }
    sealed = {key: value for key, value in envelope.items() if key != "observation_digest"}
    envelope["observation_digest"] = (
        "observation:sha256:" + hashlib.sha256(canonical_json(sealed)).hexdigest()
    )


def _build_envelope(
    dataset_id: str,
    retrieval: RetrievalResult,
    decision: _Decision,
    *,
    observed_at: str,
    observation_id: str,
    file_status: str,
    retained_digest: str | None,
    previous_id: str | None,
    previous_digest: str | None,
    change_from_previous: str | None,
    normalized_projection: Mapping[str, Any] | None = None,
    normalization_transform: str | None = None,
) -> dict[str, Any]:
    unknowns: set[str] = {"source_version"}

    retrieved_at: str | None
    if retrieval.retrieved_ended_at and str(retrieval.retrieved_ended_at).strip():
        retrieved_at = _parse_instant(
            str(retrieval.retrieved_ended_at), "RetrievalResult.retrieved_ended_at"
        )
    else:
        retrieved_at = None
        unknowns.add("retrieved_at")

    content_date, content_date_unparseable = _parse_content_date(retrieval.source_content_date)
    if content_date_unparseable:
        unknowns.add("source_content_date")

    first_observation = change_from_previous == "first_observation"
    if not first_observation:
        # Unknown history: members with an unknown basis must be declared,
        # never silently defaulted (validator rule FP-5).
        if previous_id is None:
            unknowns.add("previous_observation_id")
        if previous_digest is None:
            unknowns.add("previous_observation_digest")
        if change_from_previous == "unknown":
            unknowns.add("change_from_previous")

    if retained_digest is not None:
        replay_state = "replayable"
    else:
        replay_state = "metadata_only"

    envelope: dict[str, Any] = {
        "schema": SCHEMA_CONST,
        "observation_id": observation_id,
        "dataset_id": dataset_id,
        "source_identity": {
            "identity_value": None,
            "basis": "unknown",
            "limitation": IDENTITY_LIMITATION,
        },
        "source_url": retrieval.source_url,
        "observed_request_url": retrieval.observed_request_url,
        "observed_at": observed_at,
        "retrieved_at": retrieved_at,
        "source_content_date": content_date,
        "source_version": "unknown",
        "capture_policy": decision.policy,
        "capture_status": file_status,
        "source_digest": retained_digest,
        "observation_digest": "",
        "shape_fingerprint": None,
        "normalized_projection": (
            dict(normalized_projection)
            if normalized_projection is not None
            else {"state": "not_retained", "format": None, "record_count": None}
        ),
        "normalization_profile_version": NORMALIZATION_PROFILE_VERSION,
        "previous_observation_id": previous_id,
        "previous_observation_digest": previous_digest,
        "change_from_previous": change_from_previous,
        "verification": {
            "verification_status": "unverified",
            "verified_at": None,
            "method": None,
            "limitation": VERIFICATION_LIMITATION,
        },
        "attestation_ref": None,
        "witness_refs": [],
        "claim_boundary": _claim_boundary(file_status, retained_digest is not None),
        "unknown_reasons": sorted(unknowns),
        "cycle_root": {},
        "contract_digest": _contract_digest(),
        "superseded_by": None,
        "invalidated_by": None,
        "declared": {"entries": _declared_entries(decision)},
        "observed": {"entries": _observed_entries(retrieval, decision)},
        "publisher_credential": None,
        "verifier_credential": None,
        "replay_state": replay_state,
        "field_provenance": {},
    }

    first_observation = change_from_previous == "first_observation"
    envelope["field_provenance"] = {
        "schema": _provenance("configured_by_policy", transform="constant of historical-observation/v2"),
        "observation_id": _provenance(
            "platform_computed", transform="derived from dataset_id and the observation instant"
        ),
        "dataset_id": _provenance("platform_computed"),
        "source_identity": _provenance(
            "platform_computed",
            transform="identity object declaring unknown identity; no identity instrument exists at capture time",
        ),
        "source_url": _provenance(
            "copied_from_source", transform="reproduced verbatim from the manifest catalogue record"
        ),
        "observed_request_url": _provenance(
            "copied_from_source", transform="reproduced verbatim from the transfer record"
        ),
        "observed_at": _provenance("platform_computed", transform="normalized to UTC Z-form"),
        "retrieved_at": (
            _provenance("platform_computed", transform="request completion instant, normalized to UTC Z-form")
            if retrieved_at is not None
            else _provenance("unknown", state="unmeasured", reason="unresolved")
        ),
        "source_content_date": (
            _provenance("declared_by_source", transform="reproduced verbatim from the source's own claim")
            if content_date is not None
            else _provenance(
                "unknown", state="unmeasured", reason="not_extractable"
            )
            if content_date_unparseable
            else _provenance("not_delivered", state="unmeasured", reason="source_did_not_deliver")
        ),
        "source_version": _provenance("unknown", state="unmeasured", reason="no_instrument"),
        "capture_policy": _provenance("configured_by_policy"),
        "capture_status": _provenance(
            "platform_computed", transform="outcome of the capture decision table"
        ),
        "source_digest": (
            _provenance(
                "platform_computed",
                transform="observation_store.put_blob return over exactly the retained bytes",
            )
            if retained_digest is not None
            else _provenance(
                "not_measured",
                state="unmeasured",
                # A captured decision with no retained digest is a preview:
                # nothing was retained, so nothing was attempted.
                reason=decision.digest_reason or "capture_not_attempted",
            )
        ),
        "observation_digest": _provenance(
            "platform_computed",
            transform="sha256 over the canonical envelope excluding observation_digest",
        ),
        "shape_fingerprint": _provenance(
            "not_measured", state="unmeasured", reason="no_instrument"
        ),
        "normalized_projection": (
            _provenance("platform_computed", transform=normalization_transform)
            if normalization_transform is not None
            else _provenance("configured_by_policy")
        ),
        "normalization_profile_version": _provenance("configured_by_policy"),
        "previous_observation_id": (
            _provenance("platform_computed")
            if previous_id is not None
            else _provenance("not_applicable", state="not_applicable", reason="does_not_apply")
            if first_observation
            else _provenance("unknown", state="unmeasured", reason="unresolved")
        ),
        "previous_observation_digest": (
            _provenance("platform_computed")
            if previous_digest is not None
            else _provenance("not_applicable", state="not_applicable", reason="does_not_apply")
            if first_observation
            else _provenance("unknown", state="unmeasured", reason="unresolved")
        ),
        "change_from_previous": (
            _provenance("platform_computed")
            if change_from_previous in ("changed", "unchanged", "first_observation")
            else _provenance("unknown", state="unmeasured", reason="unresolved")
        ),
        "verification": _provenance(
            "platform_computed", transform="capture never asserts verification; filed as unverified"
        ),
        "attestation_ref": _provenance("not_measured", state="unmeasured", reason="unresolved"),
        "witness_refs": _provenance(
            "platform_computed", transform="no independent witness records exist for this observation"
        ),
        "claim_boundary": _provenance("platform_computed"),
        "unknown_reasons": _provenance("platform_computed"),
        "cycle_root": _provenance(
            "platform_computed",
            transform="single-leaf merkle-sha256 over this observation's pre-seal digest; "
            "cycle aggregation arrives with proof issuance",
        ),
        "contract_digest": _provenance(
            "platform_computed", transform="sha256 over the producing module's source bytes"
        ),
        "superseded_by": _provenance("not_applicable", state="not_applicable", reason="does_not_apply"),
        "invalidated_by": _provenance("not_applicable", state="not_applicable", reason="does_not_apply"),
        "declared": _provenance(
            "platform_computed", transform="entries assembled from the operator-reviewed observation policy"
        ),
        "observed": _provenance(
            "platform_computed", transform="entries assembled from the completed transfer record"
        ),
        "publisher_credential": _provenance("not_applicable", state="not_applicable", reason="does_not_apply"),
        "verifier_credential": _provenance("not_applicable", state="not_applicable", reason="does_not_apply"),
        "replay_state": _provenance(
            "platform_computed", transform="outcome of the capture decision table"
        ),
    }
    return envelope


def capture_observation(
    dataset_id: str,
    retrieval: RetrievalResult,
    *,
    root: str | Path | None = None,
    now: datetime | str | None = None,
    previous: Mapping[str, Any] | None = None,
    profile: str | None = None,
    store: bool = False,
) -> dict[str, Any]:
    """Decide a capture, and file the observation only when ``store=True``.

    The decision always comes from :func:`capture_decision`.  When filing,
    the body is retained via ``observation_store.put_blob`` *first*; the
    envelope embeds that call's return as ``source_digest``; the envelope is
    validated with ``validate_envelope`` (an invalid envelope raises
    :class:`EnvelopeValidationError` and never reaches the store); only then
    are ``put_envelope`` and ``upsert_observation`` called.

    Args:
        dataset_id: The dataset the retrieval belongs to.
        retrieval: The completed retrieval to capture.
        root: Store root override (the production store root is never
            touched by tests or the selftest).
        now: Observation instant; defaults to the current UTC time.  Never
            taken from the source.
        previous: The dataset's previous filed observation envelope, if any,
            used for linkage fields only.
        profile: Optional normalization profile name.  Projections are a
            later task; nothing projection-shaped is written here.
        store: When True, retain bytes and file the envelope atomically
            through the store's helpers.

    Returns:
        The observation envelope dict.

    Raises:
        EnvelopeValidationError: If a to-be-filed envelope fails
            ``validate_envelope``.
        CaptureError: If filing cannot proceed truthfully.
    """
    decision = _decide(dataset_id, retrieval, None)
    observed_at = _observation_instant(now)
    observation_id = _observation_id(dataset_id, observed_at)
    store_root = Path(root) if root is not None else None
    body = retrieval.body if isinstance(retrieval.body, (bytes, bytearray)) else None

    retained_digest: str | None = None
    if store and decision.status == "captured":
        # Retain the bytes first: source_digest may only ever be put_blob's
        # return value over bytes the store actually holds.
        retained_digest = put_blob(bytes(body), root=store_root)
        logger.info(
            "retained %s (%d bytes) for dataset %s", retained_digest, len(body), dataset_id
        )

    file_status = decision.status
    if decision.status == "captured" and not store:
        # A preview retains nothing, so it must not claim retention.
        file_status = "metadata_only"
        logger.debug(
            "preview capture for dataset %s: nothing retained, reported as metadata_only",
            dataset_id,
        )

    normalized_projection: dict[str, Any] | None = None
    normalization_transform: str | None = None
    if profile is not None:
        # Imported lazily and defensively: capture must behave exactly as
        # before when observation_normalize is absent.  The module-path form
        # (not `from scripts import ...`) matches the header imports: a
        # foreign `scripts` namespace package on sys.path must fall through
        # to the bare form, and only ModuleNotFoundError signals absence.
        try:
            import scripts.observation_normalize as observation_normalize
        except ModuleNotFoundError:
            try:
                import observation_normalize
            except ModuleNotFoundError:
                observation_normalize = None
        if observation_normalize is None:
            logger.debug(
                "normalization profile %r supplied; projections arrive with a later task — "
                "nothing projected, nothing projected is claimed",
                profile,
            )
        elif not (store and file_status == "captured" and body is not None):
            # A projection is of retained bytes: a preview or denied capture
            # retains nothing, so nothing projected may be claimed.
            logger.debug(
                "normalization profile %r supplied but nothing was retained; no projection claimed",
                profile,
            )
        else:
            try:
                normalized_result = observation_normalize.normalize(bytes(body), profile)
                observation_normalize.file_normalized(normalized_result, root=store_root)
            except (
                observation_normalize.NormalizationProfileError,
                observation_normalize.NormalizationParseError,
            ) as error:
                # unknown_reasons cannot name normalized_projection (its schema
                # vocabulary is closed), so the failure lands truthfully in the
                # member's own state and its provenance transform, never a crash.
                normalized_projection = {"state": "unknown", "format": None, "record_count": None}
                normalization_transform = f"normalization under profile {profile!r} failed: {error}"
                logger.debug("normalization under profile %r failed: %s", profile, error)
            else:
                normalized_projection = {
                    "state": "retained",
                    "format": normalized_result.format,
                    "record_count": int(normalized_result.record_count),
                }
                normalization_transform = (
                    f"observation_normalize profile {normalized_result.profile_name}/"
                    f"{normalized_result.profile_version}; projection_digest "
                    f"{normalized_result.projection_digest}"
                )
                logger.debug(
                    "normalized %d records under profile %r (%s)",
                    normalized_result.record_count,
                    profile,
                    normalized_result.projection_digest,
                )

    previous_id, previous_digest, change_from_previous = _previous_history(
        dataset_id, previous, retained_digest, store=store, root=store_root
    )

    envelope = _build_envelope(
        dataset_id,
        retrieval,
        decision,
        observed_at=observed_at,
        observation_id=observation_id,
        file_status=file_status,
        retained_digest=retained_digest,
        previous_id=previous_id,
        previous_digest=previous_digest,
        change_from_previous=change_from_previous,
        normalized_projection=normalized_projection,
        normalization_transform=normalization_transform,
    )
    _seal(envelope)

    errors = validate_envelope(envelope)
    if errors:
        message = "envelope for {} ({}) failed validation:\n{}".format(
            dataset_id, observation_id, "\n".join(f"  {error}" for error in errors)
        )
        if store:
            # The blob may already be content-addressed on disk, but no
            # envelope reached the store — bytes without a claim are inert;
            # a claim without valid bytes never exists.
            raise EnvelopeValidationError(message)
        logger.warning("%s", message)
    elif not store:
        logger.debug("preview envelope for %s (%s) validates cleanly", dataset_id, observation_id)

    if store:
        envelope_path = put_envelope(dataset_id, observation_id, envelope, root=store_root)
        upsert_observation(
            dataset_id,
            observation_id,
            envelope["observed_at"],
            envelope_path,
            source_digest=envelope["source_digest"],
            observation_digest=envelope["observation_digest"],
            root=store_root,
        )
        logger.info("filed observation %s for dataset %s at %s", observation_id, dataset_id, envelope_path)

    return envelope


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point.

    Modes:
        ``--selftest``            Run the built-in acceptance selftest
                                  against a scratch store inside the
                                  worktree; exits 0 only when both sample
                                  envelopes validate with zero errors and
                                  the truth rules hold.
        ``--dataset <id>``        Dataset id for a fixture capture.
        ``--fixture <json>``      RetrievalResult fields as JSON (body
                                  base64-encoded under ``body_b64``, or
                                  text under ``body``).
        ``--store <root>``        Store root; supplying it files the
                                  capture (``store=True``).
        ``--profile <name>``      Normalization profile designation; when
                                  given (and bytes were retained), a
                                  normalized projection is filed and the
                                  envelope claims it as ``retained``.

    Returns:
        Process exit code.
    """
    parser = argparse.ArgumentParser(
        prog="observation_capture.py",
        description="Capture source responses at observation time and file truthful envelopes.",
    )
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="run the acceptance selftest against a scratch store inside the worktree",
    )
    parser.add_argument("--dataset", help="dataset id for a fixture capture")
    parser.add_argument(
        "--fixture",
        type=Path,
        metavar="JSON",
        help="RetrievalResult fields as JSON (body base64 under body_b64, or text under body)",
    )
    parser.add_argument(
        "--store",
        type=Path,
        metavar="ROOT",
        help="absolute store root; supplying it files the capture (store=True)",
    )
    parser.add_argument(
        "--profile",
        metavar="DESIGNATION",
        help="normalization profile designation (e.g. fuelprice_csv_v1) to project retained bytes",
    )
    arguments = parser.parse_args(argv)

    if arguments.selftest:
        return _selftest(profile=arguments.profile)
    if not arguments.dataset or arguments.fixture is None:
        parser.error("--dataset and --fixture are required unless --selftest is given")

    try:
        retrieval = _load_fixture(arguments.fixture)
        envelope = capture_observation(
            arguments.dataset,
            retrieval,
            root=arguments.store,
            profile=arguments.profile,
            store=arguments.store is not None,
        )
    except CaptureError as error:
        print(f"ERROR {error}", file=sys.stderr)
        return 2

    print(canonical_json(envelope).decode("utf-8"))
    errors = validate_envelope(envelope)
    print(f"validate_envelope: {len(errors)} errors")
    for error in errors:
        print(f"  {error}", file=sys.stderr)
    return 0 if not errors else 1


def _load_fixture(path: Path) -> RetrievalResult:
    """Build a RetrievalResult from a JSON fixture document."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CaptureError(f"cannot read fixture {path}: {error}") from error
    if not isinstance(document, dict):
        raise CaptureError(f"fixture {path} must be a JSON object")

    source_url = document.get("source_url")
    if not isinstance(source_url, str) or not source_url:
        raise CaptureError(f"fixture {path} must carry a string source_url")
    body: bytes | None
    if "body_b64" in document:
        try:
            body = base64.b64decode(str(document["body_b64"]), validate=True)
        except (ValueError, TypeError) as error:
            raise CaptureError(f"fixture {path} body_b64 is not valid base64: {error}") from error
    elif "body" in document and document["body"] is not None:
        body = str(document["body"]).encode("utf-8")
    else:
        body = None

    http_status = document.get("http_status", 200)
    if not isinstance(http_status, int) or isinstance(http_status, bool):
        raise CaptureError(f"fixture {path} http_status must be an integer")

    def optional_string(key: str) -> str | None:
        value = document.get(key)
        return value if isinstance(value, str) and value else None

    return RetrievalResult(
        source_url=source_url,
        observed_request_url=optional_string("observed_request_url") or source_url,
        http_status=http_status,
        content_type=optional_string("content_type"),
        retrieved_started_at=optional_string("retrieved_started_at") or "",
        retrieved_ended_at=optional_string("retrieved_ended_at") or "",
        body=body,
        etag=optional_string("etag"),
        last_modified=optional_string("last_modified"),
        source_content_date=optional_string("source_content_date"),
        truncated=bool(document.get("truncated", False)),
    )


def _selftest(profile: str | None = None) -> int:
    """Acceptance selftest: one granted full capture, one policy denial.

    Both captures file into a scratch store rooted inside the worktree; the
    production store root is never touched.  When ``profile`` is supplied the
    granted capture also normalizes its retained bytes under that profile and
    the retained-projection truth rules are checked.  Exits 0 only when both
    envelopes validate with zero errors and the truth rules hold.
    """
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    scratch = Path(tempfile.mkdtemp(prefix=".observation-capture-selftest-", dir=REPO_ROOT))
    failures: list[str] = []
    try:
        granted = RetrievalResult(
            source_url="https://storage.data.gov.my/opendata/fuelprice/fuelprice.csv",
            observed_request_url="https://storage.data.gov.my/opendata/fuelprice/fuelprice.csv",
            http_status=200,
            content_type="text/csv",
            retrieved_started_at="2026-09-16T02:04:11+00:00",
            retrieved_ended_at="2026-09-16T02:04:12+00:00",
            body=_FUELPRICE_CSV,
            etag='"8f14e45fceea167a"',
            last_modified="Wed, 16 Sep 2026 00:30:00 GMT",
            source_content_date="2026-09-10",
            truncated=False,
        )
        denied = RetrievalResult(
            source_url="https://storage.dosm.gov.my/cpi/cpi-monthly.csv",
            observed_request_url="https://storage.dosm.gov.my/cpi/cpi-monthly.csv",
            http_status=200,
            content_type="text/csv",
            retrieved_started_at="2026-09-16T02:05:40+00:00",
            retrieved_ended_at="2026-09-16T02:05:41+00:00",
            body=_CPI_CSV,
            etag=None,
            last_modified=None,
            source_content_date=None,
            truncated=False,
        )

        captured = capture_observation(
            "fuelprice",
            granted,
            root=scratch,
            now=datetime(2026, 9, 16, 2, 5, 0, tzinfo=timezone.utc),
            profile=profile,
            store=True,
        )
        refused = capture_observation(
            "dosm_consumer_price_index",
            denied,
            root=scratch,
            now=datetime(2026, 9, 16, 2, 6, 0, tzinfo=timezone.utc),
            store=True,
        )

        for label, envelope in (("granted full capture (fuelprice)", captured), ("policy denial (dataset absent from config)", refused)):
            print(f"--- {label} ---")
            print(canonical_json(envelope).decode("utf-8"))
            errors = validate_envelope(envelope)
            print(f"validate_envelope: {len(errors)} errors")
            failures.extend(f"{label}: {error}" for error in errors)

        digest = captured.get("source_digest")
        recomputed = sha256_digest(read_blob(digest, root=scratch))
        print(f"captured source_digest: {digest}")
        print(f"recomputed from retained bytes: {recomputed}")
        print(f"denied source_digest: {refused.get('source_digest')} (nothing retained; recomputed: n/a)")

        checks: list[tuple[str, bool]] = [
            ("captured envelope claims capture_status=captured", captured.get("capture_status") == "captured"),
            ("captured envelope carries a non-null source_digest", digest is not None),
            ("captured source_digest matches the digest recomputed from the retained blob", digest == recomputed),
            ("captured envelope maps full_vintage to capture_policy=full_source_bytes", captured.get("capture_policy") == "full_source_bytes"),
            ("denied envelope reports capture_status=not_captured", refused.get("capture_status") == "not_captured"),
            ("denied envelope reports capture_policy=none", refused.get("capture_policy") == "none"),
            ("denied envelope carries source_digest=null", refused.get("source_digest") is None),
            ("denied envelope never claims replayable", refused.get("replay_state") != "replayable"),
            ("denied envelope declares metadata_only replay state", refused.get("replay_state") == "metadata_only"),
            ("captured envelope is filed unverified", captured.get("verification", {}).get("verification_status") == "unverified"),
            ("denied envelope is filed unverified", refused.get("verification", {}).get("verification_status") == "unverified"),
        ]
        if profile is not None:
            filed_projection = captured.get("normalized_projection") or {}
            print(f"normalized_projection: {canonical_json(filed_projection).decode('utf-8')}")
            checks.extend(
                (
                    (
                        "captured envelope retains a normalized projection under the supplied profile",
                        filed_projection.get("state") == "retained",
                    ),
                    (
                        "retained projection declares the csv format",
                        filed_projection.get("format") == "csv",
                    ),
                    (
                        "retained projection reports a positive integer record_count",
                        isinstance(filed_projection.get("record_count"), int)
                        and not isinstance(filed_projection.get("record_count"), bool)
                        and filed_projection.get("record_count") > 0,
                    ),
                )
            )
        for description, holds in checks:
            if not holds:
                failures.append(f"truth rule failed: {description}")
    except Exception as error:  # noqa: BLE001 — the selftest reports, never traces
        failures.append(f"selftest raised {type(error).__name__}: {error}")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    if failures:
        for failure in failures:
            print(f"FAIL {failure}", file=sys.stderr)
        return 1
    print("selftest passed: both envelopes validate with 0 errors and the truth rules hold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
