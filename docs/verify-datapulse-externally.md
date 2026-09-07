# Verify DataPulse externally

This guide is for AI agents, auditors, researchers, and procurement teams that
need to check DataPulse evidence without installing DataPulse or trusting a
DataPulse verification command. The verifier below is a single Python file. It
uses only public HTTPS GETs, the published Ed25519 public-key registry, the
public GitHub source record, and the public Rekor transparency log.

## Run it without a checkout

Python 3 is the only requirement. Download the verifier from the public source
record, then run it from any directory:

```bash
curl -fsSLO https://raw.githubusercontent.com/r3dz4r/datapulse-my/main/scripts/verify_external.py
python3 verify_external.py
```

The command exits zero only when the first two layers pass and the third layer
contains a structurally valid Rekor inclusion proof. It prints one clear result
per layer. A public Rekor re-query is attempted as additional evidence. If that
API is temporarily unavailable or cannot retrieve the entry, the output says
`importable evidence present` rather than claiming an independent re-fetch.

To exercise the verifier's offline failure path, including a deliberately
changed payload under a known signature, run:

```bash
python3 verify_external.py --self-test
```

The self-test passes only when the known-good fixture verifies and the tampered
fixture is rejected.

## What the three layers establish

1. **Ed25519 per-dataset envelope signature.** The verifier downloads the
   active key from
   [`/.well-known/datapulse-probe-keys.json`](https://www.data-pulse.my/.well-known/datapulse-probe-keys.json),
   selects the registry's `current_key_id`, and verifies a dated dataset
   envelope. The signed bytes are the envelope's `payload` encoded as UTF-8
   JSON with sorted keys, no extra whitespace, and `ensure_ascii=false`.
   This detects a changed payload, changed signature, wrong key, or broken
   chain link.
2. **Git source-of-record parity.** The same dated envelope is fetched from
   `www.data-pulse.my` and from
   [`raw.githubusercontent.com/r3dz4r/datapulse-my`](https://raw.githubusercontent.com/r3dz4r/datapulse-my/main/attestations/latest/index.json)
   on `main`; their bytes must match. The verifier also checks that the
   repository's `attestations/latest/chain_head.json` is byte-identical to the
   dated head selected by the latest index. This makes a served-only rewrite or
   a stale `latest` pointer visible.
3. **Rekor/Sigstore temporal witness for health.** The verifier reads
   [`/signatures/health.latest.sigstore.json`](https://www.data-pulse.my/signatures/health.latest.sigstore.json),
   requires a transparency-log entry with `logIndex`, `integratedTime`, a
   signed entry timestamp, and an inclusion proof, and reconstructs that
   proof's Merkle root. It then attempts to retrieve the canonicalized entry
   from Rekor's public API. A successful retrieval confirms the public-log
   witness independently; an unavailable retrieval does not erase the served,
   importable evidence and is reported honestly.

These checks establish byte integrity, public-source parity, and a public-log
time witness for the signed health/DSSE statement. They do not establish that an
upstream publisher's underlying data is semantically true, complete, or fit for
a particular use.

## Limits to keep in view

DataPulse currently uses one self-managed active Ed25519 signing key. The public
registry makes the key and its validity window inspectable, but independent
verifiers still decide whether that key-management model meets their policy.

Rekor witnesses the health/DSSE layer and the fresh dated bindings published
going forward. The historical relationship from 2026-08-15 to 2026-09-07 is
disclosed as a sibling gap; it has not been re-signed to create a retrospective
continuous public-log history. A valid signature or inclusion proof therefore
proves the integrity and timing of the stated DataPulse observation, not an
independent observation of the upstream source.
