#!/usr/bin/env python3
"""Additive evidence linking for captured historical observations.

This module attaches a :class:`HistoricalReference` — a small, derived
description of an observation envelope already persisted in the observation
store — into an existing evidence document *additively*: the reference is
appended under a new ``historical_observations`` key and nothing else in the
document changes.  Additivity is *proven*, not assumed: the module
canonical-serializes the input document, removes exactly what was added from
the output, and byte-compares the two.  Any difference raises
:class:`AdditivityError` before the caller ever sees a plausible-looking
document.  The original document is therefore recoverable byte-for-byte by
removing the added key (or, when the key already existed, the appended entry).

Design constraints (do not weaken):

* The daily Ed25519 attestation payload and chain semantics live in
  ``scripts/gen_attestations.py`` and are NOT this module's to change.  This
  module never signs, re-signs, or writes anything under ``.attestations/``
  (including ``chain_head.json``); it writes nothing at all outside the
  caller's own document and, in ``--selftest``, a scratch store root written
  through ``observation_store``'s own helpers.
* Digests are carried, never recomputed.  ``source_digest`` is taken from the
  envelope verbatim; a re-serialization of the envelope is never hashed.
* Links the caller did not supply are ``None`` and are named in
  ``HistoricalReference.unlinked`` — an absent link is declared, not implied.
* :func:`verify_reference` is honest about what it did not check.  Verifying a
  reference is NOT a claim that the source bytes are intact: it checks the
  envelope file, identity agreement, and digest shape, and reports
  ``raw_bytes_present`` separately so a verification without source bytes can
  never be mistaken for a re-hash of them.
* Determinism: identical inputs produce byte-identical reference dicts and
  attached documents.  No clock-derived value enters a reference; every
  timestamp comes from the envelope.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import logging
import shutil
import tempfile
from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Optional

try:
    from scripts.observation_store import (
        DIGEST_PATTERN,
        OBSERVATION_ID_PATTERN,
        ObservationStoreError,
        blob_path,
        canonical_json,
        put_blob,
        put_envelope,
        resolve_root,
        sha256_digest,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution
    from observation_store import (
        DIGEST_PATTERN,
        OBSERVATION_ID_PATTERN,
        ObservationStoreError,
        blob_path,
        canonical_json,
        put_blob,
        put_envelope,
        resolve_root,
        sha256_digest,
    )

__all__ = [
    "AdditivityError",
    "ReferenceError",
    "HistoricalReference",
    "build_reference",
    "attach_reference",
    "verify_reference",
    "main",
]

logger = logging.getLogger(__name__)

ATTACHMENT_KEY: str = "historical_observations"

# The optional links a caller may supply.  Every one not supplied is None on
# the reference and named in `unlinked`; this tuple is the closed vocabulary.
OPTIONAL_LINKS: tuple[str, ...] = (
    "normalized_digest",
    "health_observation_ref",
    "attestation_ref",
    "external_witness",
    "source_of_record",
)


class AdditivityError(Exception):
    """Raised when attaching a reference would alter existing evidence content.

    The attachment contract is byte-for-byte additivity: removing exactly what
    was added from the output document must yield a canonical serialization
    identical to the input document's.  This error carries both serializations'
    sha256 digests so a breach is visible, never silent.
    """


class ReferenceError(Exception):
    """Raised when a reference cannot be derived from the given envelope.

    Shadows nothing this module relies on; the name is part of the module's
    public contract.  Raised for envelopes missing the identity members the
    reference must carry verbatim (``observation_id``, ``dataset_id``, a
    parseable timezone-aware ``observed_at``), never for absent optional data
    such as ``source_digest``.
    """


# ---------------------------------------------------------------------------
# Reference construction
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HistoricalReference:
    """A derived, verifiable pointer from an evidence document to a stored
    historical observation.

    Every member except ``envelope_ref`` mirrors a value the envelope already
    carries verbatim (or a link the caller explicitly supplied).  ``unlinked``
    names every optional link that was not supplied — an absent link is
    declared rather than implied by a missing key.
    """

    envelope_ref: str
    observation_id: str
    dataset_id: str
    source_digest: Optional[str]
    captured_at: Optional[str]
    normalized_digest: Optional[str] = None
    health_observation_ref: Optional[str] = None
    attestation_ref: Optional[str] = None
    external_witness: Optional[str] = None
    source_of_record: Optional[str] = None
    unlinked: tuple[str, ...] = field(default_factory=tuple)


def _observed_at_utc(value: Any) -> datetime:
    """Parse an envelope ``observed_at`` into an aware UTC instant.

    Same semantics as the store's placement rule: a trailing Z is accepted, a
    naive timestamp is rejected (ambiguous by design), and the result is
    normalized to UTC because the envelope tree is laid out in UTC.
    """
    if not isinstance(value, str) or not value.strip():
        raise ReferenceError(
            "envelope must carry an ISO-8601 observed_at string; the envelope "
            "tree is laid out by that member, so a reference cannot be derived "
            "without it"
        )
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        moment = datetime.fromisoformat(text)
    except ValueError as error:
        raise ReferenceError(
            f"envelope observed_at {value!r} is not a parseable ISO-8601 instant"
        ) from error
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ReferenceError(
            f"envelope observed_at {value!r} must carry a timezone offset; a "
            "naive local time is ambiguous by design"
        )
    return moment.astimezone(timezone.utc)


def build_reference(
    envelope: dict[str, Any],
    *,
    store_root: Optional[str] = None,
    health: Optional[str] = None,
    attestation: Optional[str] = None,
    witness: Optional[str] = None,
    source_of_record: Optional[str] = None,
) -> HistoricalReference:
    """Derive a :class:`HistoricalReference` from an observation envelope.

    ``observation_id``, ``dataset_id``, ``source_digest`` and ``captured_at``
    are read from the envelope verbatim — never recomputed, never derived from
    a re-serialization.  ``envelope_ref`` is the store-root-relative posix
    path the store's own layout rule assigns this envelope
    (``envelopes/<dataset_id>/<YYYY>/<MM>/<observation_id>.json`` with
    ``YYYY``/``MM`` from the envelope's ``observed_at`` in UTC), so it is
    derivable from the envelope alone and identical on every host.

    ``store_root`` is accepted for call-site symmetry with
    :func:`verify_reference`; it deliberately does not participate in the
    derivation (root-relative references are host-independent) and no I/O is
    performed — existence checks belong to verification.

    Optional links the caller did not supply are ``None`` and are named in
    ``unlinked``.  A reference to an envelope whose ``source_digest`` is null
    (a denial or partial capture) carries ``None`` — the absence is declared,
    never papered over.  This function never invents a link.

    Raises :class:`ReferenceError` when the envelope lacks the identity
    members a reference must carry.  This function is pure: same envelope,
    same links, byte-identical reference.
    """
    del store_root  # documented above: root-relative refs need no root to derive
    if not isinstance(envelope, dict):
        raise ReferenceError(f"envelope must be a JSON object (dict), got {type(envelope).__name__}")

    observation_id = envelope.get("observation_id")
    if not isinstance(observation_id, str) or not OBSERVATION_ID_PATTERN.fullmatch(
        observation_id
    ):
        raise ReferenceError(
            f"envelope observation_id {observation_id!r} does not match the envelope "
            "contract pattern ^obs-[a-z0-9][a-z0-9_-]{0,127}$; a reference must name "
            "an identity the contract accepts"
        )

    dataset_id = envelope.get("dataset_id")
    if not isinstance(dataset_id, str) or not dataset_id:
        raise ReferenceError("envelope must carry a non-empty string dataset_id")

    captured_at = envelope.get("observed_at")
    moment = _observed_at_utc(captured_at)

    source_digest = envelope.get("source_digest")
    if source_digest is not None and not isinstance(source_digest, str):
        raise ReferenceError(
            f"envelope source_digest must be a string or null, got {type(source_digest).__name__}; "
            "the reference carries it verbatim or not at all"
        )

    envelope_ref = (
        f"envelopes/{dataset_id}/{moment:%Y}/{moment:%m}/{observation_id}.json"
    )

    links: dict[str, Optional[str]] = {
        # normalized_digest is never derivable from the envelope (the contract's
        # normalized_projection carries no digest), so it is unlinked unless a
        # caller constructs the reference directly with one.
        "normalized_digest": None,
        "health_observation_ref": health,
        "attestation_ref": attestation,
        "external_witness": witness,
        "source_of_record": source_of_record,
    }
    unlinked = tuple(sorted(name for name, value in links.items() if value is None))

    return HistoricalReference(
        envelope_ref=envelope_ref,
        observation_id=observation_id,
        dataset_id=dataset_id,
        source_digest=source_digest,
        captured_at=captured_at,
        normalized_digest=links["normalized_digest"],
        health_observation_ref=links["health_observation_ref"],
        attestation_ref=links["attestation_ref"],
        external_witness=links["external_witness"],
        source_of_record=links["source_of_record"],
        unlinked=unlinked,
    )


def reference_payload(reference: HistoricalReference) -> dict[str, Any]:
    """Serialize a reference to a JSON-ready dict, deterministically.

    Absent optional links appear as explicit ``null`` AND in ``unlinked``, so
    an absent link is declared rather than implied by a missing key.  The
    ``unlinked`` tuple is emitted as a sorted JSON list.
    """
    payload: dict[str, Any] = {}
    for member in fields(HistoricalReference):
        value = getattr(reference, member.name)
        payload[member.name] = sorted(value) if member.name == "unlinked" else value
    return payload


# ---------------------------------------------------------------------------
# Additive attachment
# ---------------------------------------------------------------------------


def attach_reference(
    evidence_doc: dict[str, Any], reference: HistoricalReference
) -> dict[str, Any]:
    """Return a NEW evidence document with ``reference`` appended additively.

    The reference is appended to a list under the key
    ``historical_observations`` (created if absent).  Existing content is
    untouched: the canonical serialization of the input must equal the
    canonical serialization of the output with exactly the addition removed —
    the key when it was created, the appended entry when the key already
    existed — else :class:`AdditivityError` is raised and nothing is returned.
    The caller's object is never mutated; a deep copy is returned.

    This function writes nothing to disk, never signs or re-signs anything,
    and never touches ``.attestations/``.  Changing the signed daily payload
    is gen_attestations.py's business, not this module's.
    """
    if not isinstance(evidence_doc, dict):
        raise AdditivityError(
            f"evidence document must be a JSON object (dict), got {type(evidence_doc).__name__}"
        )

    before = canonical_json(evidence_doc)
    attached = copy.deepcopy(evidence_doc)
    existing = attached.get(ATTACHMENT_KEY)
    created_key = ATTACHMENT_KEY not in attached
    if created_key:
        attached[ATTACHMENT_KEY] = [reference_payload(reference)]
    elif isinstance(existing, list):
        existing.append(reference_payload(reference))
    else:
        raise AdditivityError(
            f"evidence document member {ATTACHMENT_KEY!r} is not a list "
            f"(got {type(existing).__name__}); refusing to attach into a document "
            "whose recovery rule would be ambiguous"
        )

    # Prove additivity before returning: recover the input from the output by
    # removing exactly what was added, then byte-compare canonical forms.
    if created_key:
        recovered = {key: value for key, value in attached.items() if key != ATTACHMENT_KEY}
    else:
        recovered = copy.deepcopy(attached)
        recovered[ATTACHMENT_KEY] = recovered[ATTACHMENT_KEY][:-1]
    after = canonical_json(recovered)
    if before != after:
        raise AdditivityError(
            "attachment is not additive: removing the added "
            f"{ATTACHMENT_KEY!r} content does not recover the original document "
            f"byte-for-byte (original canonical sha256:{hashlib.sha256(before).hexdigest()}, "
            f"recovered canonical sha256:{hashlib.sha256(after).hexdigest()}); "
            "existing evidence content would have changed — nothing was returned"
        )
    if canonical_json(evidence_doc) != before:
        raise AdditivityError(
            "internal invariant failed: the caller's document changed during "
            "attachment; nothing was returned"
        )
    return attached


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def _digest_format_ok(digest: Any) -> bool:
    return isinstance(digest, str) and bool(DIGEST_PATTERN.fullmatch(digest))


def verify_reference(
    reference: HistoricalReference,
    *,
    store_root: Optional[str] = None,
    require_raw_bytes: bool = False,
) -> dict[str, Any]:
    """Verify a reference against the observation store it names.

    Returns ``{"errors": [...], "checks": [...], "raw_bytes_present": bool,
    "verified_without_raw_bytes": bool}``.

    With ``require_raw_bytes=False`` this succeeds without any source bytes on
    disk: it checks that the envelope file exists under the store, that
    ``observation_id`` matches both the envelope filename and the envelope's
    own ``observation_id`` member, that every digest carried on the reference
    is ``sha256:`` + 64 lowercase hex, and that the reference is consistent
    with the envelope it names (``dataset_id``, ``captured_at`` vs
    ``observed_at``, ``source_digest``).

    ``raw_bytes_present`` is derived from whether the blob named by
    ``source_digest`` exists — reported, never assumed.  When the reference
    carries no ``source_digest`` (a denial or partial capture) the absence is
    reported as a check note, not an error: raw bytes were never claimed.

    With ``require_raw_bytes=True`` the named blob is additionally re-hashed;
    absence or mismatch appends an error.

    IMPORTANT: verifying a reference is NOT a claim that the source bytes are
    intact.  ``verified_without_raw_bytes`` is true only when every check this
    call performed passed (so a failed raw-bytes check under
    ``require_raw_bytes=True`` makes it false); ``raw_bytes_present`` is
    reported separately and never conflated with verification success.
    """
    errors: list[str] = []
    checks: list[str] = []

    def record(name: str, ok: bool, message: str) -> None:
        checks.append(f"{name}:{'ok' if ok else 'failed'}")
        if not ok:
            errors.append(message)

    # --- envelope_ref shape (checked before any filesystem use) -------------
    envelope_ref = reference.envelope_ref
    ref_path = PurePosixPath(envelope_ref) if isinstance(envelope_ref, str) else None
    ref_safe = (
        ref_path is not None
        and not ref_path.is_absolute()
        and ".." not in ref_path.parts
        and ref_path.name != ""
    )
    record(
        "envelope_ref_safe",
        ref_safe,
        f"envelope_ref {envelope_ref!r} must be a non-empty relative posix path without '..' "
        "components; refusing to resolve anything else against the store root",
    )

    filename_id_ok = ref_path is not None and ref_path.stem == reference.observation_id
    record(
        "observation_id_matches_filename",
        filename_id_ok,
        f"envelope_ref {envelope_ref!r} must end in {reference.observation_id}.json; "
        "a reference may not name one observation while pointing at another's file",
    )

    # --- digest shape on the reference itself -------------------------------
    if reference.source_digest is not None:
        record(
            "source_digest_format",
            _digest_format_ok(reference.source_digest),
            f"reference source_digest {reference.source_digest!r} is not "
            "'sha256:' followed by exactly 64 lowercase hex characters",
        )
    else:
        checks.append(
            "source_digest:absent(denial-or-partial-capture); raw bytes neither expected nor claimed"
        )
    if reference.normalized_digest is not None:
        record(
            "normalized_digest_format",
            _digest_format_ok(reference.normalized_digest),
            f"reference normalized_digest {reference.normalized_digest!r} is not "
            "'sha256:' followed by exactly 64 lowercase hex characters",
        )

    # --- raw bytes presence (derived, never assumed) ------------------------
    raw_bytes_present = False
    if reference.source_digest is not None and _digest_format_ok(reference.source_digest):
        try:
            blob = blob_path(reference.source_digest, root=store_root)
        except ObservationStoreError as error:
            errors.append(f"store root resolution failed for blob lookup: {error}")
            blob = None
        raw_bytes_present = blob is not None and blob.is_file()
    checks.append(f"raw_bytes_present:{'true' if raw_bytes_present else 'false'}")

    # --- envelope existence and consistency with the reference --------------
    envelope_checked = False
    if ref_safe and ref_path is not None:
        try:
            root = resolve_root(store_root)
        except ObservationStoreError as error:
            root = None
            errors.append(f"store root resolution failed: {error}")
            checks.append("envelope_exists:skipped(store-root-unresolvable)")
        if root is not None:
            envelope_path = root / Path(*ref_path.parts)
            if envelope_path.is_file():
                checks.append("envelope_exists:ok")
                try:
                    envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as error:
                    errors.append(f"envelope {envelope_path} is unreadable or not JSON: {error}")
                    checks.append("envelope_consistent:skipped(unreadable)")
                else:
                    if not isinstance(envelope, dict):
                        errors.append(
                            f"envelope {envelope_path} is not a JSON object; it cannot carry the "
                            "identity the reference claims"
                        )
                        checks.append("envelope_consistent:skipped(not-an-object)")
                    else:
                        envelope_checked = True
            else:
                errors.append(
                    f"no envelope stored at {envelope_ref} under the resolved store root "
                    f"({envelope_path}); a reference must name an envelope the store holds"
                )
                checks.append("envelope_exists:failed")

    if envelope_checked:
        ok = envelope.get("observation_id") == reference.observation_id
        record(
            "observation_id_matches_envelope",
            ok,
            f"envelope declares observation_id {envelope.get('observation_id')!r} but the "
            f"reference claims {reference.observation_id!r}",
        )
        ok = envelope.get("dataset_id") == reference.dataset_id
        record(
            "dataset_id_matches_envelope",
            ok,
            f"envelope declares dataset_id {envelope.get('dataset_id')!r} but the "
            f"reference claims {reference.dataset_id!r}",
        )
        ok = envelope.get("observed_at") == reference.captured_at
        record(
            "captured_at_matches_envelope_observed_at",
            ok,
            f"envelope declares observed_at {envelope.get('observed_at')!r} but the "
            f"reference carries captured_at {reference.captured_at!r}",
        )
        ok = envelope.get("source_digest") == reference.source_digest
        record(
            "source_digest_matches_envelope",
            ok,
            f"envelope declares source_digest {envelope.get('source_digest')!r} but the "
            f"reference carries {reference.source_digest!r}; the digest is carried verbatim "
            "or the reference is not the one the envelope backs",
        )
        checks.append("envelope_consistent:ok")

    # --- optional raw-bytes requirement -------------------------------------
    if require_raw_bytes:
        if reference.source_digest is None:
            errors.append(
                "raw bytes were required but the reference carries no source_digest "
                "(a denial or partial capture); there is nothing to re-hash"
            )
            checks.append("raw_bytes_rehash:failed(no-source-digest)")
        elif not raw_bytes_present:
            errors.append(
                f"raw bytes were required but no blob is stored for digest "
                f"{reference.source_digest}; the source bytes are absent"
            )
            checks.append("raw_bytes_rehash:failed(blob-absent)")
        else:
            try:
                blob = blob_path(reference.source_digest, root=store_root)
                actual = sha256_digest(blob.read_bytes())
            except (OSError, ObservationStoreError) as error:
                errors.append(f"raw blob could not be re-hashed: {error}")
                checks.append("raw_bytes_rehash:failed(unreadable)")
            else:
                record(
                    "raw_bytes_rehash",
                    actual == reference.source_digest,
                    f"stored blob hashes to {actual} but the reference carries "
                    f"{reference.source_digest}",
                )
    else:
        checks.append("raw_bytes_rehash:skipped(require_raw_bytes=False)")

    return {
        "errors": errors,
        "checks": checks,
        "raw_bytes_present": raw_bytes_present,
        "verified_without_raw_bytes": not errors,
    }


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------


def _selftest_envelope(raw: bytes, source_digest: str) -> dict[str, Any]:
    """A minimal but internally consistent fuelprice observation envelope."""
    envelope: dict[str, Any] = {
        "schema": "historical-observation/v2",
        "observation_id": "obs-fuelprice-selftest-0001",
        "dataset_id": "fuelprice",
        "observed_at": "2026-09-16T08:00:00Z",
        "retrieved_at": "2026-09-16T07:59:58Z",
        "capture_status": "captured",
        "source_digest": source_digest,
    }
    # observation_digest is domain-separated over the canonical envelope
    # excluding itself, per the schema's own definition of the member.
    envelope["observation_digest"] = (
        "observation:" + sha256_digest(canonical_json(envelope))
    )
    return envelope


def _selftest_evidence_doc(raw: bytes) -> dict[str, Any]:
    """A synthetic evidence document shaped like a record-evidence/v1 envelope."""
    record = {
        "record_id": "date:2026-09-16",
        "status": "fresh",
        "evidence_digest": sha256_digest(b"selftest-record-1"),
    }
    return {
        "schema": "record-evidence/v1",
        "dataset_id": "fuelprice",
        "observed_at": "2026-09-16T08:00:00Z",
        "run_date": "2026-09-16",
        "source_url": "https://storage.example.gov.my/fuelprice.csv",
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "record_count": 1,
        "schema_valid_count": 1,
        "freshness": {
            "source_last_modified": "2026-09-16T06:00:00Z",
            "age_days": 0,
            "status": "fresh",
        },
        "records": [record],
    }


def _run_selftest() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    scratch = Path(tempfile.mkdtemp(prefix=".observation-evidence-link-selftest-", dir=repo_root))
    failures: list[str] = []
    try:
        # [1] Synthetic capture: real bytes, real digest, filed through the
        # store's own helpers into a scratch root inside the worktree (never
        # the production store root).
        raw = b"date,ron95,ron97,diesel\n2026-09-16,2.05,3.38,2.85\n"
        source_digest = put_blob(raw, root=scratch)
        envelope = _selftest_envelope(raw, source_digest)
        envelope_path = put_envelope(
            envelope["dataset_id"], envelope["observation_id"], envelope, root=scratch
        )
        reference = build_reference(
            envelope,
            attestation="attestations/2026-09-16/chain_head.json",
        )
        print("[1] built reference:")
        print(canonical_json(reference_payload(reference)).decode("utf-8"))
        if reference.envelope_ref != envelope_path.relative_to(scratch).as_posix():
            failures.append(
                "derived envelope_ref does not match the store's own placement "
                f"({reference.envelope_ref} != {envelope_path.relative_to(scratch).as_posix()})"
            )

        # [2] Additive attachment into a synthetic evidence document.
        evidence_doc = _selftest_evidence_doc(raw)
        before_bytes = canonical_json(evidence_doc)
        attached = attach_reference(evidence_doc, reference)
        print("[2] attached document:")
        print(canonical_json(attached).decode("utf-8"))

        # [3] Prove the pre-existing members are byte-identical after
        # attachment: original canonical vs attached-minus-the-added-key.
        recovered = {key: value for key, value in attached.items() if key != ATTACHMENT_KEY}
        after_bytes = canonical_json(recovered)
        identical = before_bytes == after_bytes
        print(
            "[3] additivity proof: original canonical "
            f"sha256:{hashlib.sha256(before_bytes).hexdigest()} vs recovered canonical "
            f"sha256:{hashlib.sha256(after_bytes).hexdigest()} -> byte-identical={identical}"
        )
        if not identical:
            failures.append("original members are not byte-identical after attachment")
        if canonical_json(evidence_doc) != before_bytes:
            failures.append("attach_reference mutated the caller's document")
        print(
            f"[4] caller document unchanged after attachment: "
            f"{canonical_json(evidence_doc) == before_bytes}"
        )

        # [5] Verification with the blob present, no raw-bytes requirement.
        report = verify_reference(reference, store_root=str(scratch), require_raw_bytes=False)
        print(
            "[5] verification (blob present, require_raw_bytes=False): "
            f"errors={report['errors']} raw_bytes_present={report['raw_bytes_present']} "
            f"verified_without_raw_bytes={report['verified_without_raw_bytes']}"
        )
        if report["errors"] or not report["verified_without_raw_bytes"]:
            failures.append(f"verification with blob present reported errors: {report['errors']}")

        # [6] Verification with the source bytes deleted: the reference must
        # still verify — that is the entire point of the historical plane.
        blob_path(source_digest, root=scratch).unlink()
        report_without_bytes = verify_reference(
            reference, store_root=str(scratch), require_raw_bytes=False
        )
        print(
            "[6] verification (blob removed, require_raw_bytes=False): "
            f"errors={report_without_bytes['errors']} "
            f"raw_bytes_present={report_without_bytes['raw_bytes_present']} "
            f"verified_without_raw_bytes={report_without_bytes['verified_without_raw_bytes']}"
        )
        if report_without_bytes["errors"] or not report_without_bytes["verified_without_raw_bytes"]:
            failures.append(
                f"verification without raw bytes reported errors: {report_without_bytes['errors']}"
            )
        if report_without_bytes["raw_bytes_present"]:
            failures.append("raw_bytes_present is True after the blob was deleted")

        # [7] Determinism: a second build must serialize identically.
        reference_again = build_reference(
            envelope,
            attestation="attestations/2026-09-16/chain_head.json",
        )
        deterministic = canonical_json(
            reference_payload(reference)
        ) == canonical_json(reference_payload(reference_again))
        print(f"[7] determinism: second build serializes identically: {deterministic}")
        if not deterministic:
            failures.append("two builds from identical inputs serialized differently")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    if failures:
        for failure in failures:
            print(f"SELFTEST FAILED: {failure}")
        return 1
    print("SELFTEST PASSED (scratch root removed)")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point.

    ``--selftest`` runs the built-in acceptance selftest against a scratch
    store root inside the worktree.  ``--envelope``/``--evidence`` (with
    optional ``--store``) build, additively attach, and verify one reference,
    printing the attached document to stdout without writing any file.  No
    mode signs, re-signs, or writes under ``.attestations/``.
    """
    parser = argparse.ArgumentParser(
        description="Link captured historical observations into evidence documents additively."
    )
    parser.add_argument("--selftest", action="store_true", help="run the built-in selftest")
    parser.add_argument("--envelope", type=Path, help="path to a historical-observation envelope")
    parser.add_argument("--evidence", type=Path, help="path to the evidence document to attach into")
    parser.add_argument("--store", help="observation store root (absolute path)")
    args = parser.parse_args(argv)

    if args.selftest:
        return _run_selftest()

    if args.envelope is None or args.evidence is None:
        parser.error("--envelope and --evidence are required unless --selftest is given")

    envelope = json.loads(args.envelope.read_text(encoding="utf-8"))
    evidence_doc = json.loads(args.evidence.read_text(encoding="utf-8"))
    reference = build_reference(envelope)
    attached = attach_reference(evidence_doc, reference)
    report = verify_reference(reference, store_root=args.store)
    print(canonical_json(attached).decode("utf-8"))
    print(
        f"verification: errors={report['errors']} "
        f"raw_bytes_present={report['raw_bytes_present']} "
        f"verified_without_raw_bytes={report['verified_without_raw_bytes']}"
    )
    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
