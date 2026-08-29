# P6 attestation architecture decision — 2026-08-24

## Decision

P6 will not continue OpenBao + private Rekor as DataPulse's primary near-term production dependency.

The private stack is technically valid but operationally disproportionate at the current product stage. The live incident demonstrated the failure chain: missing/invalid signer credential -> OpenBao 403 -> Rekor checkpoint-signing failure -> Rekor API 500 -> 245 queued publication requests. The marker remains absent and no publisher replay is authorized.

## Near-term architecture

Retain the sovereign/private architecture, but separate its roles and failure boundaries:

1. Legacy Ed25519 health binding remains the compatibility and local-integrity path.
2. Cosign Sigstore bundle/reference remains the external-witness artifact shape already present in the repository.
3. OpenBao remains the operator-controlled private key-custody boundary.
4. Private Rekor remains the sovereign transparency witness.
5. The witness/signing implementation is asynchronous and replaceable; its failure must never block health publication, Pages, API, or MCP.
6. The Rekor checkpoint signer and DataPulse artifact signer remain separate identities and credentials.
7. The private signer must use an explicit pinned key version, immutable public-key snapshot, stable LogID, and local signature verification; do not rely on generic `openbao://` latest-version behavior.
8. DSSE/in-toto is deferred until a consumer requires predicate-level interoperability; do not add a second format now.

The operational burden is accepted because sovereignty is a hard requirement. The solution is not migrating to public OIDC; it is making the private lane bounded, recoverable, auditable, and non-blocking.

## Evidence

- Current Sigstore documentation supports OpenBao KMS URIs, Cosign bundles, keyless OIDC signing, and custom Sigstore services:
  - https://docs.sigstore.dev/cosign/key_management/overview/
  - https://docs.sigstore.dev/cosign/signing/signing_with_blobs/
  - https://docs.sigstore.dev/cosign/signing/overview/
- OpenBao Transit supports ECDSA P-256 and versioned keys:
  - https://openbao.org/docs/secrets/transit/
- Rekor is a standalone transparency log and can support custom manifest schemas:
  - https://docs.sigstore.dev/logging/overview/
- in-toto and SLSA remain future interoperability options, not an immediate second format:
  - https://in-toto.io/docs/specs/
  - https://slsa.dev/spec/v1.0/attestation-model

## P6 stages

### P6.0 — operational containment

- Keep the real-lab marker absent.
- Do not start the publisher.
- Preserve the 245 queued requests.
- Reconcile the queue only after Rekor read-only health is restored.
- Recover credentials/configuration only through the protected operator procedure.

### P6.1 — additive witness contract hardening

- Audit the existing `sigstore_rekor_publisher.py`, binding/reference schema, bundle verification, idempotency, read-after-write proof, and failure states.
- Make the signer and witness boundaries explicit and replaceable.
- Verify that legacy Ed25519 publication remains independent.
- Add tests for pending, published, verified, failed, and operator-reconciliation outcomes.
- No live signing or Rekor write in this stage.

### P6.2 — low-risk issuer pilot

- Choose OIDC keyless or managed KMS after the P6.1 audit.
- Sign one fresh health snapshot only.
- Store and independently verify the bundle/reference.
- Require read-after-write inclusion and digest parity.
- No consumer cutover and no backlog replay.

### P6.3 — promotion gate

Promote only after a bounded daily pilot demonstrates stable signing, inclusion, verification, credential lifecycle, and failure recovery. Private OpenBao/Rekor is reconsidered only if the operational and buyer/regulatory case outweighs its maintenance burden.

## Explicit non-goals

- No bulk replay of queued requests.
- No marker restoration in this source phase.
- No root-token recovery through chat.
- No public Rekor/Fulcio/OIDC/TUF deployment changes without a separate decision.
- No replacement of Ed25519.
- No API/MCP behavior changes.
