Workdir: /home/redza/datapulse-my
Goal: Produce a verified implementation design for an OpenBao-compatible Rekor v1.5.4 log-checkpoint signer without weakening the national-data trust boundary or generating production key material.
Failure mode: A guessed Rekor signer patch could produce unstable log identity, unverifiable signed tree heads, unrecoverable restart state, incompatible Cosign bundles, or a production fork that silently diverges from upstream.
Acceptance test: Audit the pinned Rekor v1.5.4 signer/checkpoint call path and the exact OpenBao Transit API contract; compare viable integration shapes; write a bounded implementation brief with exact files/interfaces, dependency changes, test fixtures, key-version/identity handling, restart/restore acceptance tests, rollback, and explicit crypto/deployment gates. No production key generation, signing, Rekor write, container restart, or commit/push.
Recommended execution model: sol

## Context

DataPulse selected Option 4: OpenBao-compatible Rekor signer implementation.

Already verified:

- DataPulse artifact signing through OpenBao ECDSA P-256 and Cosign v3.1.3 works in the disposable lab.
- Private Rekor v1.5.4 with Trillian/MySQL works in the disposable lab.
- The consistency adapter and ETag fix are pushed in DataPulse commit `cb27f6a0`.
- Production OpenBao 2.6.2 is running on `127.0.0.1:9830`, initialized/unsealed, TLS-enabled, audited, with Transit key `datapulse-cosign` and signer AppRole/policy configured by the operator. Do not access or print the root token, SecretID, or private key.
- Production Rekor is not deployed. The lab uses `--rekor_server.signer=memory`, which is not acceptable for production.
- Rekor v1.5.4 source flags expose signer choices including KMS/Tink/memory/file; upstream marks memory/file signers testing-only. The OpenBao artifact key must not be reused as the Rekor checkpoint signer.

## Required audit questions

1. Trace Rekor v1.5.4 from `--rekor_server.signer` through `pkg/signer`, `pkg/api`, checkpoint creation, shard/log identity, and public key endpoint.
2. Identify the exact signer interface and the bytes OpenBao must sign.
3. Determine whether a minimal OpenBao signer can be added without changing Rekor’s Merkle/checkpoint format.
4. Determine the exact OpenBao Transit endpoint, input encoding, hash/prehashed behavior, signature encoding, and public-key retrieval needed for Rekor’s signer interface. Verify from OpenBao 2.6.x API/source; do not invent parameters.
5. Check whether existing Sigstore Go KMS/provider interfaces can be reused without claiming OpenBao support that Rekor v1.5.4 does not actually have.
6. Decide whether the safe implementation is:
   - a small maintained fork/patch to Rekor v1.5.4;
   - an upstreamable signer provider;
   - a sidecar signer boundary;
   - or a Rekor v2/Tessera migration instead.
7. Define how Rekor log public-key identity remains stable across restart, backup/restore, Transit key version changes, and rotation.
8. Define failure behavior: OpenBao unavailable, wrong key type, signature mismatch, key version unavailable, log identity change, and restore from backup.

## Output artifact

Write the audit and implementation brief to:

`notes/2026-08-22-openbao-rekor-log-signer-implementation-brief.md`

The artifact must include:

- verified current contract with source URLs/commit versions;
- exact proposed files and dependency changes;
- no-go findings and rejected options;
- fixture-only test plan;
- production key/auth/policy assumptions without secrets;
- stable log-identity and key-version policy;
- restart/restore/rollback acceptance criteria;
- resource and operational impact;
- explicit gates: implementation, key generation/import, production signer activation, first Rekor write, and cutover.

Do not modify production code, Docker/systemd configuration, OpenBao state, generated artifacts, or public docs. Do not create keys, call Transit sign, submit Rekor entries, or commit/push.

Report exact artifact path, research findings, and `Pushed: NO`.
