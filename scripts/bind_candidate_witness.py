#!/usr/bin/env python3
"""Finalize a new, uncommitted candidate's binding before Git acceptance."""
from __future__ import annotations

import argparse
import base64
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.attestation_sets import discovery, selected_directory, verify_set
from scripts.gen_attestations import load, dump, rekor_binding, sign, writer_lock
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def bind_candidate(root: Path, key_path: Path, reference: Path) -> None:
    """Never edit accepted evidence; sign only the privately prepared binding."""
    with writer_lock(root / ".attestations"):
        directory = selected_directory(root)
        path = directory + "/binding.json"
        committed = subprocess.run(["git", "cat-file", "-e", f"HEAD:{path}"], cwd=root, capture_output=True)
        if committed.returncode == 0:
            raise ValueError("witness upgrade requires a new append; committed binding is immutable")
        binding = load(root / path)
        key = load(key_path)
        if key["key_id"] != binding["payload"]["ed25519"]["key_id"]:
            raise ValueError("candidate signer identity changed")
        metadata = rekor_binding(root, reference, binding["payload"]["health"]["artifact_sha256"])
        binding["rekor"] = metadata
        binding["claims"] = {"artifact_signed": True, "rekor_witnessed": True, "source_truth_verified": False}
        private = Ed25519PrivateKey.from_private_bytes(base64.b64decode(key["private_key_base64"], validate=True))
        binding["signature_base64"] = sign(private, binding["payload"])
        old = (root / path).read_bytes()
        try:
            dump(root / path, binding)
            verify_set(root, directory + "/chain_head.json")
        except BaseException:
            (root / path).write_bytes(old)
            raise
        (root / "attestations/latest/binding.json").write_bytes((root / path).read_bytes())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--private-key", type=Path, required=True)
    parser.add_argument("--rekor-reference", type=Path, required=True)
    args = parser.parse_args()
    bind_candidate(args.root, args.private_key, args.rekor_reference)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
