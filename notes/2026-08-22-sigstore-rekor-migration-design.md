# Sigstore/Rekor migration design — Phase 1 parallel work

Date: 2026-08-22
Status: design artifact; no cryptographic or production change

## Why this can run in parallel

Phase 1 is accumulating longitudinal evidence in the background. This design work does not modify the health timer, signing key, attestation output, or verification behavior. It defines the migration boundary so the later adoption dispatch can be executed without erasing DataPulse's Malaysia-specific evidence semantics.

## Current DataPulse attestation surface

The current implementation is in `scripts/gen_attestations.py` and `mcp/server.py`:

- each daily dataset receipt contains a canonical `datapulse/v1/probe-attestation` payload;
- the payload records publisher/source URL, observed time, access dependency, probe counts, status, staleness, content fingerprint, and key identity;
- the payload is signed with Ed25519;
- dataset receipts are linked through a daily chain head;
- `verify_attestation` performs L1 signature/key checks and optional L2 replay to a Git-tag anchor;
- the public key registry and dated envelopes remain part of the current consumer contract.

This current contract is useful application logic. The migration should replace the signing/transparency primitive, not discard the declared/observed/verdict separation.

## Self-hosted operating model

Rekor self-hosting is not a single-container toggle. The official installation model requires a Rekor server plus Trillian and a MySQL-compatible database; Redis is optional for fast retrieval/search.[5] The first deployment design should therefore use a separate compose/systemd boundary and dedicated persistent volumes rather than reusing Honcho, Plausible, or the NPRA engine database.

Initial topology:

```text
DataPulse health/release pipeline
        │ private authenticated submission
        ▼
self-hosted Rekor API (tailnet/private bind)
        │
        ├── Trillian log server + signer
        ├── dedicated MariaDB/MySQL-compatible storage
        └── optional Redis retrieval index
```

Initial boundary:

- no public Cloudflare route;
- bind to loopback or Tailscale only;
- no exposure on the existing public MCP hostname;
- dedicated credentials and volumes;
- encrypted backup and restore test before production writes;
- explicit Merkle tree/shard persistence and upgrade procedure.

The current VPS already has database services and occupied ports, so the design must not assume a free port or reuse an existing database. Port allocation, container names, volumes, resource limits, health checks, and backup paths must be discovered and approved before deployment.

## Sovereignty boundary gate

**Self-hosted Rekor is necessary but may not be sufficient for a fully sovereign signing chain.** Cosign custom-component guidance describes separate trust material for Rekor, Fulcio, CT log, and TUF roots.[6] A keyless CI path that uses public OIDC, public Fulcio, or public TUF still sends identity/trust operations outside the VPS even if the Rekor log is private.

Before implementation, choose the operating model explicitly:

1. **Self-hosted Rekor + operator-controlled key/KMS:** selected. This keeps the transparency log and signing authority within the approved boundary, while allowing Cosign-compatible bundle verification.
2. **Fully operator-controlled Sigstore stack:** deferred. Self-hosting Fulcio, CT, and TUF adds substantial operational burden and is not required for the first migration if the signing key/KMS is controlled directly.
3. **Public identity/trust components:** deferred. Public Fulcio, OIDC, public TUF, and public Rekor are not the default for this national-data trust layer.

The exact KMS/provider remains a separate infrastructure decision. No key generation, KMS provisioning, or signing operation is authorized by this design note.

## KMS provider recommendation

**Recommended provider: OpenBao Transit.** OpenBao's Transit engine supports signing and verification with Ed25519, key versioning, ACL-controlled operations, and operator-managed key material.[7] Cosign documents OpenBao as a supported KMS provider using an `openbao://` URI and Transit signing/verification permissions.[8]

OpenBao is preferred over introducing HashiCorp Vault here because the existing VPS has neither installed, and the project needs an operator-controlled open-source trust component rather than a new proprietary control-plane dependency. This is a recommendation, not an installation decision. The deployment brief must still define:

- private listener binding and authentication;
- Transit policy allowing only the health/release signer to sign;
- read-only verification access for consumers;
- key version and rotation policy;
- backup/restore of OpenBao state and trust metadata;
- failure behavior when OpenBao or Rekor is unavailable;
- whether the first key is generated inside OpenBao or imported from an approved external source.

No production OpenBao, Vault, KMS, or key material is installed or changed by this design work. Disposable lab key material is explicitly excluded from production state.

## Disposable Cosign/OpenBao compatibility result

The approved disposable lab produced the first real compatibility result:

- OpenBao `2.6.2` Transit Ed25519 key: created in the lab, but Cosign `v3.1.3 sign-blob` failed while constructing the bundle with `message is missing artifact digest`.
- OpenBao `2.6.2` Transit ECDSA P-256 key: Cosign `v3.1.3 sign-blob` succeeded through `openbao://datapulse-cosign`.
- `cosign verify-blob --bundle --key openbao://datapulse-cosign --insecure-ignore-tlog` returned `Verified OK` for the local artifact.
- Rekor tree size remained `0`; no log entry was submitted.

This does not prove production Rekor integration. It does establish the current migration direction: retain Ed25519 for legacy DataPulse envelopes and target ECDSA P-256 for the Cosign/OpenBao bundle path unless a later versioned compatibility test proves Ed25519 support end-to-end.

## Private Rekor write result

The approved disposable fixture submission reached the private Rekor API exactly once:

- tree size before: `0`;
- `POST /api/v1/log/entries`: HTTP `201`;
- resulting log index: `0`;
- inclusion proof: present;
- Rekor `hashedrekord` artifact hash: matched the local fixture SHA-256;
- signature extracted from the stored entry: verified through OpenBao ECDSA P-256 with Cosign;
- tree size after: `1`.

Cosign exited non-zero while constructing its bundle because its immediate inclusion read observed `0 < 1` before Trillian's read path converged. The command was not retried, so no duplicate entry was created and no bundle was emitted. A second lab attempt with Redis-backed search indexing reproduced the same race. The consistency-aware adapter was then implemented and committed as `9d495e3b`; its proof-body follow-up exposed the missing `ETag` contract, which caused Cosign v3.1.3 to pass an empty entry key and panic. This follows the Cosign/sigstore-go v1 client path, which indexes the response payload by the Rekor response `ETag` before converting the entry.[9][10] The ETag fix removed the panic. With a disposable private trusted-root file containing the lab Rekor public key, Cosign v3.1.3 emitted and verified a complete bundle through the adapter. Cosign documents custom trusted roots for private Sigstore components.[6] Production integration must use an operator-distributed private trusted root; a URL-only signing config is insufficient for private Rekor verification. Production remains gated.

## Complete private-lab bundle result

- ETag-preserving adapter response: passed;
- exactly one POST for the successful fixture: passed;
- Cosign bundle media type: `application/vnd.dev.sigstore.bundle.v0.3+json`;
- bundle entry: one `hashedrekord` entry with inclusion proof and inclusion promise;
- private trusted root: contained only the disposable lab Rekor public key;
- `cosign verify-blob --trusted-root ...`: `Verified OK`;
- final disposable lab tree size: `5`;
- no production key, route, service, artifact, or trust root changed.

## Decision recorded

The first migration target is **self-hosted Rekor with Cosign-compatible bundles and an operator-controlled signing key/KMS**. Public Rekor, public Fulcio/OIDC, and public TUF are deferred for this trust layer. The existing DataPulse Ed25519 envelopes remain the compatibility path; the disposable Cosign/OpenBao lab identified **ECDSA P-256** as the working Cosign/KMS algorithm for the new bundle path. This decision applies to the fixture-only design target; it does not authorize production signing, KMS provisioning beyond the disposable lab, Rekor writes, or production cutover.

## Proposed migration shape

### 1. Preserve the DataPulse payload

Keep `datapulse/v1/probe-attestation` as the domain payload during the first migration. Do not make Cosign claims or bundle metadata the only place where DataPulse-specific evidence lives.

The signed artifact should be deterministic and independently reconstructable. The first candidate is the daily chain-head payload or a canonical daily evidence manifest, because signing one daily root avoids creating a separate external-log entry for every dataset while retaining per-dataset receipts locally.

### 2. Add Cosign/Sigstore as a second verification backend

Use Cosign's blob-signing/bundle model for the daily artifact. The bundle should be stored with the dated attestation artifacts and referenced from the daily index. The bundle is the portable verification object: official Sigstore guidance describes it as carrying signature metadata, certificate, timestamp, and transparency-log inclusion proof.[1][2]

During migration, retain the current Ed25519/Git-tag verifier as a compatibility backend. New verification output should identify the backend and level rather than silently changing the meaning of `levels.L1` or `levels.L2`.

### 3. Use Rekor for external transparency evidence

Rekor supplies the append-only transparency-log role and exposes REST/CLI paths for recording, querying, and verifying inclusion proofs.[4] The migration must distinguish:

- cryptographic signature validity;
- certificate/identity policy validity;
- transparency-log inclusion;
- DataPulse chain/domain-payload validity.

A valid Sigstore bundle must not be presented as proof that the upstream dataset is correct. It proves the signed DataPulse observation artifact and its transparency evidence.

### 4. Keep verification portable

Cosign verification supports verifying a blob from the artifact plus its bundle and signer-identity policy.[1][3] The DataPulse verifier should prefer bundle-contained evidence for offline or low-connectivity verification, then optionally query Rekor for fresh inclusion/revocation context.

### 5. Keep migration reversible

For at least one transition window:

- publish both the existing Ed25519 envelope and the Sigstore bundle;
- expose which backend verified the result;
- keep the current `verify_attestation` response fields backward-compatible;
- add fixtures for old-only, new-only, dual-published, malformed, and mismatched artifacts;
- cut over only after old and new verification agree on the same canonical payload digest.

## Explicit non-goals for this parallel phase

- no key generation or rotation;
- no keyless signing login or OIDC authorization;
- no private-key or KMS configuration;
- no public Rekor writes;
- no self-hosted Rekor deployment yet;
- no replacement of `gen_attestations.py` yet;
- no change to the 10-status taxonomy or trust-score methodology;
- no production service restart;
- no changes to `verify_attestation` until the implementation brief is approved.

## Gates before implementation

1. Phase 1 evidence window reaches at least three daily samples spanning two days. This validates the payload fields and exposes which evidence is actually stable enough to sign.
2. Operator confirms the self-hosted Rekor operating model: storage, backup, availability target, trust-root distribution, access boundary, and upgrade path.
3. Redza gives explicit `Go` for the crypto operation. General implementation approval does not authorize key generation, rotation, signing, or production Rekor writes.
4. A Terra/Sol design review resolves artifact granularity: one daily chain head versus per-dataset bundles.
5. A fixture-only migration test passes before any production signing path is touched.

## Decision

Run this design track in parallel with Phase 1 evidence accumulation. Do not implement the cryptographic cutover yet. The immediate artifact is the self-hosted Rekor operating-model brief plus compatibility contract; production adoption remains gated by the evidence window, infrastructure design review, and explicit crypto approval.

## Sources

[1] https://docs.sigstore.dev/quickstart/quickstart-cosign — Sigstore Cosign quickstart
[2] https://docs.sigstore.dev/cosign/signing/signing_with_blobs — Cosign blob signing
[3] https://docs.sigstore.dev/cosign/verifying/verify — Cosign verification
[4] https://docs.sigstore.dev/logging/overview — Rekor overview
[5] https://docs.sigstore.dev/logging/installation — Rekor installation
[6] https://docs.sigstore.dev/cosign/system_config/custom_components — Cosign custom Sigstore components
[7] https://openbao.org/docs/secrets/transit — OpenBao Transit secrets engine
[8] https://docs.sigstore.dev/cosign/key_management/overview — Cosign KMS provider support
[9] https://raw.githubusercontent.com/sigstore/rekor/v1.5.3/pkg/tle/tle.go — Rekor v1.5.3 TransparencyLogEntry conversion
[10] https://raw.githubusercontent.com/sigstore/sigstore-go/v1.2.2/pkg/sign/transparency.go — sigstore-go v1.2.2 Rekor v1 client
[11] https://raw.githubusercontent.com/sigstore/sigstore-go/v1.2.2/pkg/sign/signer.go — sigstore-go v1.2.2 bundle signing
