# Durable Rekor log-signer design — 2026-08-22

Status: design/blocker; no Rekor production container, log-signing key, signer KMS, or production write changed.

## Critical distinction

There are two different signing identities:

```text
DataPulse artifact signer
  OpenBao Transit ECDSA P-256
  signs the daily DataPulse artifact

Rekor log signer
  separate durable signer
  signs Rekor Merkle checkpoints / signed tree heads
```

The production OpenBao key `datapulse-cosign` must not be reused as the Rekor log signer. Consumers need to distinguish the artifact signer identity from the transparency-log identity.

## Verified Rekor v1.5.4 signer contract

The pinned Rekor v1.5.4 server exposes signer choices including memory, file/PEM, KMS providers, and Tink. The source explicitly says memory and file-based signers are for testing. The v1.5.4 Tink path requires an encrypted keyset and an AWS/GCP KMS key-encryption URI. The v1.5.4 server source does not document an OpenBao-specific Rekor signer URI.

Consequences:

- lab `--rekor_server.signer=memory` is not production-safe;
- a PEM file mounted into production is not an acceptable default because upstream marks file signers as testing-only;
- the OpenBao Transit artifact key does not automatically provide a Rekor checkpoint signer;
- production Rekor cannot be started safely until the log-signer boundary is selected and tested.

## Options

### Option A — Rekor-supported external KMS signer

Use a Rekor signer provider supported by the exact pinned binary and an operator-approved KMS. This inherits upstream support but may cross the national-data sovereignty boundary depending on provider and key location. It is not selected.

### Option B — Encrypted Tink keyset

Use Rekor's Tink signer with an encrypted keyset and supported AWS/GCP KEK URI. This improves key-file handling but still depends on the supported external KEK provider and is not OpenBao-backed in the verified v1.5.4 contract. Not selected.

### Option C — Durable encrypted PEM signer

Store a password-protected PEM key in a root-owned encrypted backup path and mount it read-only to Rekor. This is operationally simple but conflicts with Rekor's own warning that file-based signers are for testing. Reject for production unless an explicit risk acceptance is recorded.

### Option D — OpenBao-compatible Rekor signer implementation

Add or adopt a tested Rekor signer integration that delegates Rekor checkpoint signing to OpenBao Transit, pin the resulting Rekor build, and maintain the compatibility surface. This preserves the operator-controlled boundary but creates a code-maintenance fork or upstream contribution requirement. This is the current preferred direction for sovereignty, but it is not yet implemented or approved.

### Option E — Rekor v2/Tessera migration

Evaluate the tile-based Rekor v2 path and its signer/verifier backends. This may provide a better long-term architecture, but it is a separate adoption track and cannot be assumed compatible with the current Cosign v3.1.3 v1 bundle path without a fixture test.

## Recommendation

Do not start production Rekor yet. Select **Option D** only after a bounded design/implementation review proves:

1. OpenBao can sign the Rekor checkpoint payload without exporting the private key;
2. the Rekor public log key remains stable and distributable through the private trusted root;
3. restart/restore preserves the same log identity and tree state;
4. Cosign v3.1.3 accepts the resulting v1 bundle and verifies inclusion;
5. the signer policy cannot administer or export the DataPulse artifact key;
6. failure of OpenBao fails Rekor checkpoint signing closed rather than changing log identity;
7. old bundles remain verifiable after signer key-version changes.

Until then, the production OpenBao artifact signer may remain initialized and audited, but it must not sign production DataPulse artifacts and production Rekor must not accept writes.

## Sources

[1] https://raw.githubusercontent.com/sigstore/rekor/v1.5.4/cmd/rekor-server/app/root.go — Rekor v1.5.4 signer flags and testing warning
[2] https://raw.githubusercontent.com/sigstore/rekor/v1.5.4/pkg/signer/signer.go — Rekor v1.5.4 signer implementation
[3] https://docs.sigstore.dev/logging/installation/ — Rekor tree identity persistence requirement
[4] https://github.com/sigstore/rekor-tiles — Rekor v2 signer/verifier direction
