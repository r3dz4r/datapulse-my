#!/usr/bin/env python3
"""Best-effort batch signer for deterministic per-dataset evidence receipts."""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import subprocess
from pathlib import Path


LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]


def _warning(message: str) -> None:
    LOGGER.warning("::warning title=Sigstore per-dataset signing unavailable::%s", message)


def _write_result(path: Path | None, signed: bool) -> None:
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("signed\n" if signed else "unsigned\n", encoding="utf-8")


def _clear_bundles(data_dir: Path) -> None:
    for bundle in data_dir.glob("*.receipt.sigstore.json"):
        bundle.unlink()


def sign_receipts(*, data_dir: Path, cosign: str, result_out: Path | None = None) -> bool:
    """Sign every receipt atomically, returning false when keyless signing is unavailable."""
    statements = sorted(data_dir.glob("*.receipt.statement.json"))
    if not statements:
        _warning("no per-dataset receipt statements were found")
        _clear_bundles(data_dir)
        _write_result(result_out, False)
        return False
    if shutil.which(cosign) is None:
        _warning("cosign is not installed; canonical health publication will continue unsigned")
        _clear_bundles(data_dir)
        _write_result(result_out, False)
        return False
    if not os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL"):
        _warning("GitHub Actions OIDC token endpoint is unavailable; canonical health publication will continue unsigned")
        _clear_bundles(data_dir)
        _write_result(result_out, False)
        return False
    staging = data_dir / ".per-dataset-receipt-staging"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir()
    try:
        for statement in statements:
            identifier = statement.name.removesuffix(".receipt.statement.json")
            evidence = data_dir / f"{identifier}.receipt.evidence.json"
            if not evidence.is_file():
                raise ValueError(f"missing canonical evidence row: {evidence}")
            bundle = staging / f"{identifier}.receipt.sigstore.json"
            completed = subprocess.run([
                cosign, "attest-blob", "--yes", "--statement", str(statement),
                "--bundle", str(bundle), str(evidence),
            ], check=False, capture_output=True, text=True)
            if completed.returncode != 0 or not bundle.is_file() or not bundle.stat().st_size:
                raise RuntimeError(f"cosign failed while signing {identifier}")
        for bundle in staging.glob("*.receipt.sigstore.json"):
            os.replace(bundle, data_dir / bundle.name)
    except (OSError, ValueError, RuntimeError) as exc:
        _warning(f"{exc}; canonical health publication will continue unsigned")
        _clear_bundles(data_dir)
        _write_result(result_out, False)
        return False
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    _write_result(result_out, True)
    LOGGER.info("Signed %d per-dataset receipt(s)", len(statements))
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--cosign", default="cosign")
    parser.add_argument("--result-out", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    sign_receipts(data_dir=args.data_dir, cosign=args.cosign, result_out=args.result_out)


if __name__ == "__main__":
    main()
