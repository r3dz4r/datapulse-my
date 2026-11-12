#!/usr/bin/env python3
"""Best-effort batch signer for deterministic per-dataset evidence receipts.

Each statement is signed independently: one dataset failing never discards the
bundles of the datasets that signed. The run always records what it achieved in
``data/receipts-manifest.json`` (schema ``datapulse/v1/receipt-coverage``) so a
reader can tell a receipt that was not published from a publisher that wrote no
coverage record at all.
"""

from __future__ import annotations

import argparse
import enum
import json
import logging
import os
import shutil
import subprocess
import time
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path


LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]
MANIFEST_SCHEMA = "datapulse/v1/receipt-coverage"
MANIFEST_NAME = "receipts-manifest.json"
STATEMENT_SUFFIX = ".receipt.statement.json"
EVIDENCE_SUFFIX = ".receipt.evidence.json"
BUNDLE_SUFFIX = ".receipt.sigstore.json"
# Closed vocabulary for why a dataset carries no published receipt. Exception
# text never reaches the manifest; only these codes do.
UNSIGNED_REASONS = frozenset({
    "signer_unavailable",   # cosign is not installed on the signing runner
    "oidc_unavailable",     # the keyless OIDC token endpoint is not available
    "evidence_missing",     # the canonical evidence row for the statement is absent
    "signing_failed",       # cosign did not produce a bundle within the retry bound
    "verification_failed",  # a bundle was produced but did not verify; withheld
    "signing_skipped",      # the signing step did not run for this publication
})
MAX_ATTEMPTS = 2
RETRY_BACKOFF_SECONDS = 2.0
# Six sampled deploy runs on 2026-11-12 each lost one *different* dataset to a
# cosign failure (bnm_interbank_swap, deaths, arrivals, bnm_interest_rate), which
# is consistent with Sigstore (Fulcio/Rekor) rate limiting rather than a bad
# statement. The earlier pool of 8 predates that measurement, so the pool is
# kept small and each dataset gets one bounded retry.
MAX_WORKERS = 3


class SigningResult(str, enum.Enum):
    """Outcome of one signing run; the value is what the result file carries."""

    SIGNED = "signed"      # every statement produced a bundle
    PARTIAL = "partial"    # at least one, but not every, statement produced a bundle
    UNSIGNED = "unsigned"  # no statement produced a bundle


class SigningError(RuntimeError):
    """A per-dataset signing failure carrying a closed-vocabulary reason."""

    def __init__(self, reason: str) -> None:
        if reason not in UNSIGNED_REASONS:
            raise ValueError(f"unknown unsigned reason: {reason}")
        super().__init__(reason)
        self.reason = reason


def _warning(message: str) -> None:
    LOGGER.warning("::warning title=Sigstore per-dataset signing unavailable::%s", message)


def _identifier(statement: Path) -> str:
    return statement.name.removesuffix(STATEMENT_SUFFIX)


def _result_for(signed: int, total: int) -> SigningResult:
    if total and signed == total:
        return SigningResult.SIGNED
    if signed:
        return SigningResult.PARTIAL
    return SigningResult.UNSIGNED


def _write_result(path: Path | None, result: SigningResult) -> None:
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{result.value}\n", encoding="utf-8")


def _write_manifest(path: Path, *, signed: Iterable[str], unsigned: dict[str, str]) -> SigningResult:
    """Atomically write the coverage manifest and return the matching result."""
    signed_ids = sorted(set(signed))
    overlap = set(signed_ids) & set(unsigned)
    if overlap:
        raise ValueError(f"datasets cannot be both signed and unsigned: {sorted(overlap)}")
    for reason in unsigned.values():
        if reason not in UNSIGNED_REASONS:
            raise ValueError(f"unknown unsigned reason: {reason}")
    total = len(signed_ids) + len(unsigned)
    document = {
        "schema": MANIFEST_SCHEMA,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "total": total,
        "signed_count": len(signed_ids),
        "signed": signed_ids,
        "unsigned": [{"id": identifier, "reason": unsigned[identifier]} for identifier in sorted(unsigned)],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)
    return _result_for(len(signed_ids), total)


def _record_all_unsigned(*, statements: list[Path], reason: str, manifest_out: Path, result_out: Path | None) -> SigningResult:
    result = _write_manifest(manifest_out, signed=(), unsigned={_identifier(s): reason for s in statements})
    _write_result(result_out, result)
    return result


def _run_cosign(argv: list[str]) -> subprocess.CompletedProcess[str]:
    """The single cosign call boundary (tests replace this; nothing else shells out)."""
    return subprocess.run(argv, check=False, capture_output=True, text=True)


def _sign_one(*, statement: Path, data_dir: Path, staging: Path, cosign: str) -> Path:
    """Sign a single receipt statement into the staging dir, retrying a bounded number of times."""
    identifier = _identifier(statement)
    evidence = data_dir / f"{identifier}{EVIDENCE_SUFFIX}"
    if not evidence.is_file():
        raise SigningError("evidence_missing")
    bundle = staging / f"{identifier}{BUNDLE_SUFFIX}"
    for attempt in range(1, MAX_ATTEMPTS + 1):
        bundle.unlink(missing_ok=True)
        try:
            completed = _run_cosign([
                cosign, "attest-blob", "--yes", "--statement", str(statement),
                "--bundle", str(bundle), str(evidence),
            ])
        except (OSError, subprocess.SubprocessError):
            completed = None
        if completed is not None and completed.returncode == 0 and bundle.is_file() and bundle.stat().st_size:
            return bundle
        bundle.unlink(missing_ok=True)
        if attempt < MAX_ATTEMPTS:
            LOGGER.info("cosign attempt %d/%d failed for %s; retrying", attempt, MAX_ATTEMPTS, identifier)
            time.sleep(RETRY_BACKOFF_SECONDS * attempt)
    LOGGER.warning("cosign failed while signing %s after %d attempt(s)", identifier, MAX_ATTEMPTS)
    raise SigningError("signing_failed")


def _sign_or_reason(**kwargs: object) -> str | None:
    """Return None on success or the closed-vocabulary failure reason."""
    try:
        _sign_one(**kwargs)  # type: ignore[arg-type]
    except SigningError as exc:
        return exc.reason
    except OSError:
        return "signing_failed"
    return None


def sign_receipts(
    *, data_dir: Path, cosign: str, result_out: Path | None = None, manifest_out: Path | None = None,
) -> SigningResult:
    """Sign every receipt independently and record per-dataset coverage.

    Bundles are replaced only by bundles this run produced; a bundle this run
    did not create is never deleted, and a failure for one dataset never
    clears the bundles of the others.
    """
    manifest_out = manifest_out or data_dir / MANIFEST_NAME
    statements = sorted(data_dir.glob(f"*{STATEMENT_SUFFIX}"))
    if not statements:
        _warning("no per-dataset receipt statements were found")
        return _record_all_unsigned(statements=[], reason="signing_skipped", manifest_out=manifest_out, result_out=result_out)
    if shutil.which(cosign) is None:
        _warning("cosign is not installed; canonical health publication will continue unsigned")
        return _record_all_unsigned(statements=statements, reason="signer_unavailable", manifest_out=manifest_out, result_out=result_out)
    if not os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL"):
        _warning("GitHub Actions OIDC token endpoint is unavailable; canonical health publication will continue unsigned")
        return _record_all_unsigned(statements=statements, reason="oidc_unavailable", manifest_out=manifest_out, result_out=result_out)
    staging = data_dir / ".per-dataset-receipt-staging"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir()
    signed: list[str] = []
    unsigned: dict[str, str] = {}
    try:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            outcomes = list(pool.map(
                lambda statement: (
                    _identifier(statement),
                    _sign_or_reason(statement=statement, data_dir=data_dir, staging=staging, cosign=cosign),
                ),
                statements,
            ))
        for identifier, reason in outcomes:
            if reason is not None:
                unsigned[identifier] = reason
                continue
            try:
                os.replace(staging / f"{identifier}{BUNDLE_SUFFIX}", data_dir / f"{identifier}{BUNDLE_SUFFIX}")
            except OSError:
                unsigned[identifier] = "signing_failed"
            else:
                signed.append(identifier)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    result = _write_manifest(manifest_out, signed=signed, unsigned=unsigned)
    _write_result(result_out, result)
    LOGGER.info("Signed %d of %d per-dataset receipt(s); %d unsigned", len(signed), len(statements), len(unsigned))
    if unsigned:
        _warning(f"{len(unsigned)} of {len(statements)} per-dataset receipt(s) were not signed; they are recorded as unsigned")
    return result


def demote_unverified(
    *, data_dir: Path, identifiers: Iterable[str], result_out: Path | None = None, manifest_out: Path | None = None,
) -> SigningResult:
    """Withhold bundles that failed verification and record them as unsigned.

    Only bundles the manifest lists as signed by this run are removed.
    """
    manifest_out = manifest_out or data_dir / MANIFEST_NAME
    document = json.loads(manifest_out.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or document.get("schema") != MANIFEST_SCHEMA:
        raise ValueError(f"coverage manifest must carry schema {MANIFEST_SCHEMA}")
    signed = set(document["signed"])
    unsigned = {item["id"]: item["reason"] for item in document["unsigned"]}
    for identifier in set(identifiers):
        if identifier not in signed:
            raise ValueError(f"cannot demote a dataset the manifest does not list as signed: {identifier}")
        signed.discard(identifier)
        unsigned[identifier] = "verification_failed"
        (data_dir / f"{identifier}{BUNDLE_SUFFIX}").unlink(missing_ok=True)
    result = _write_manifest(manifest_out, signed=signed, unsigned=unsigned)
    _write_result(result_out, result)
    LOGGER.info("Per-dataset receipt coverage after verification: %d of %d signed", len(signed), len(signed) + len(unsigned))
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--cosign", default="cosign")
    parser.add_argument("--result-out", type=Path)
    parser.add_argument("--manifest-out", type=Path, help="coverage manifest path (default: DATA_DIR/receipts-manifest.json)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--demote", action="append", metavar="DATASET_ID",
                      help="record a signed dataset whose bundle failed verification as unsigned and withhold its bundle")
    mode.add_argument("--record-unsigned", choices=sorted(UNSIGNED_REASONS), metavar="REASON",
                      help="record every statement as unsigned with REASON without signing")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    manifest_out = args.manifest_out or args.data_dir / MANIFEST_NAME
    if args.demote:
        demote_unverified(data_dir=args.data_dir, identifiers=args.demote, result_out=args.result_out, manifest_out=manifest_out)
    elif args.record_unsigned:
        _record_all_unsigned(
            statements=sorted(args.data_dir.glob(f"*{STATEMENT_SUFFIX}")), reason=args.record_unsigned,
            manifest_out=manifest_out, result_out=args.result_out,
        )
    else:
        sign_receipts(data_dir=args.data_dir, cosign=args.cosign, result_out=args.result_out, manifest_out=manifest_out)


if __name__ == "__main__":
    main()
