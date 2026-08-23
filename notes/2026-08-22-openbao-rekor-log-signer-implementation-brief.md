# Verified implementation brief: Rekor v1.5.4 OpenBao Transit log signer

**Date:** 2026-08-22  
**Decision status:** design approved for a future implementation only; production use remains blocked by the five gates below  
**Target:** a maintained fork of Rekor v1.5.4 at `a36bd716fd0d81c314092718f37b53dc26b2af38`  
**DataPulse repository impact:** this brief is the only change. Every proposed Go path below belongs to that future Rekor fork, not to `datapulse-my`.

## Executive decision

Implement a dedicated, narrow OpenBao Transit signer in a maintained Rekor v1.5.4 fork. It must implement Rekor's existing `signature.Signer` boundary, pin one exact OpenBao key version and immutable P-256 public key at startup, hash each raw Rekor message exactly once with SHA-256, request a prehashed ASN.1 ECDSA signature from Transit, validate the returned version and encoding, and locally verify every signature before returning it.

This changes signer construction only. It must not change Rekor's entry schema, SET payload, checkpoint/note format, Merkle tree, Trillian API, Rekor HTTP API, bundle schema, or verification rules.

Do **not** use the existing bare `openbao://` path in production. The transitive sigstore provider recognizes that scheme, but Rekor v1.5.4 neither advertises it nor supplies a key-version RPC option. More critically, that provider can pin a signing version internally while `fetchPublicKey` still selects `latest_version`; after rotation or cache refresh, the public identity can change or cease to match the signing key. This is evidence of protocol compatibility, not an explicit Rekor v1.5.4 OpenBao support promise.

No production action is authorized by this document. In particular: do not create, import, rotate, delete, back up, restore, or configure a key; do not authenticate to OpenBao; do not call Transit sign or verify; do not submit a Rekor entry; do not alter Docker, systemd, TLS, firewall, or service configuration; and do not restart, commit, or push anything.

The disposable-lab result that Cosign/OpenBao artifact signing and private trusted-root bundle verification passed is a separate, already-tested boundary. It does not prove that a generic signer is durable for Rekor: this brief covers only the Rekor log signer, whose SET and checkpoint signatures share one stable log identity.

## The eight audit questions

### 1. Does Rekor v1.5.4 already support `openbao://`?

**Transitively, but not as a safe or explicit production contract.** Rekor's flag help lists `hashivault://` and omits `openbao://`. `pkg/signer/signer.go` blank-imports the sigstore HashiVault provider, tests the configured prefix against `kms.SupportedProviders()`, then calls `kms.Get(ctx, signer, crypto.SHA256)`. In pinned sigstore v1.10.9, the provider registers both `hashivault://` and `openbao://`, accepts `BAO_ADDR` and `BAO_TOKEN` after Vault-named fallbacks, and uses the Transit key-read and sign endpoints.

That makes `openbao://name` discoverable at runtime through transitive registration. It does **not** establish a Rekor v1.5.4 OpenBao support promise, expose strict OpenBao configuration, pin identity, or solve token lifecycle.

### 2. Why is the existing provider a production no-go?

The provider has a `keyVersion` field and can send a signing version, but its `fetchPublicKey` reads `latest_version` and selects `keys[latest_version]`. The public key is cached for 300 seconds. Rekor calls `kms.Get` with no key-version RPC option, so a bare Rekor configuration selects version zero/latest for signing anyway. Consequences include:

- a silent public-key and `LogID` change after a cache refresh;
- signing with one version while advertising or locally using another public key if a version is added or an option is introduced incompletely;
- restart identity depending on mutable OpenBao metadata;
- old SETs/checkpoints and bundles becoming unverifiable if trusted material is replaced instead of overlapped;
- an initialization-only token that cannot follow an operational credential lifecycle without restarting.

Therefore **bare `openbao://` and `hashivault://` are both no-go configurations for this production log**. A URL scheme is not an identity policy.

### 3. What exact bytes does Rekor sign?

One signer covers two distinct byte domains:

1. **SignedEntryTimestamp (SET):** `models.LogEntryAnon.MarshalBinary()` output is transformed by the JSON Canonicalization Scheme implementation (RFC 8785/JCS), and the resulting bytes are passed directly to `SignMessage`. The object contains `body`, `integratedTime`, `logID`, and `logIndex`; its `verification` field is populated only after signing.
2. **Checkpoint note:** Rekor builds the exact unsigned note text:

   ```text
   <hostname> - <treeID>\n
   <decimal tree size>\n
   <standard-base64 root hash>\n
   ```

   Those exact bytes, including each LF and the final LF, are passed to `SignMessage`. The signed-note envelope later adds a blank line and a signature line. The note signature identity/name is `<hostname>`; the note key hint is the first four bytes, big-endian, of `SHA256(PKIX DER public key)`.

The implementation must not specialize for checkpoints: doing so would leave SET generation on a different or broken signer path.

### 4. What is the exact hash/signature encoding contract?

`SignMessage(message io.Reader, opts ...signature.SignOption) ([]byte, error)` must consume the raw reader to EOF, compute `digest = SHA256(raw_message)` exactly once locally, and send:

```http
POST /v1/<mount>/sign/<key-name>/sha2-256
Content-Type: application/json
X-Vault-Token: <short-lived token loaded from the credential file>
```

```json
{
  "input": "<standard-base64 of the 32 binary digest bytes>",
  "prehashed": true,
  "key_version": 1,
  "marshaling_algorithm": "asn1"
}
```

`1` is illustrative only; production must configure a positive exact integer and never default to `0`/latest. For ECDSA, omit `signature_algorithm`; OpenBao documents and implements it as RSA-only. Do not hex-encode the digest and do not send the raw message with `prehashed=true`. Either mistake changes the signed bytes; sending the local digest with `prehashed=false` double-hashes it.

For the selected ECDSA P-256 key, require a successful response whose `data.signature` is exactly `vault:vN:<standard-base64 DER ASN.1 ECDSA signature>` and whose `data.key_version` equals the configured `N`. Parse the prefix strictly, reject extra/missing components or a different version, decode with standard base64, reject invalid/trailing ASN.1, and call `ecdsa.VerifyASN1(pinnedPublicKey, digest, signatureDER)`. Return only the raw DER signature bytes after local verification succeeds. Any HTTP, TLS, auth, JSON, version, decoding, parsing, or verification error fails closed.

### 5. How is stable Rekor identity derived and restored?

At signer initialization, Rekor calls `PublicKey`, marshals it as PKIX DER and PEM, and derives:

```text
LogID = lowercase_hex(SHA256(PKIX_DER(public_key)))
```

`PemPubKey` is served by `/api/v1/log/publicKey`, optionally selected by decimal tree ID. The signed-note hint uses the first four bytes of that same digest, but it is not the full Rekor `LogID`.

The OpenBao log-signing public key and the Trillian tree ID are separate identity inputs. On every restart, all of the following must be explicitly restored and compared to a sealed deployment manifest before Rekor may accept writes:

- OpenBao address/TLS identity, Transit mount, key name, and exact positive key version;
- exact-version public-key PEM and its canonical PKIX DER SHA-256/`LogID`;
- explicitly configured non-zero Trillian `tlog_id` (otherwise `NewAPI(0)` attempts to create and initialize a new tree);
- shard configuration mapping each tree ID to its signer identity and immutable historical public key;
- public Rekor hostname, because checkpoint origin is `<hostname> - <treeID>` and note signature name is `<hostname>`.

A latest-version change alone must not alter runtime identity: the signer selects `keys[configuredVersion]`, snapshots it, and never refreshes it to latest. A missing or different exact-version key is a startup failure, not a cue to select another version.

### 6. What is the exact OpenBao read/sign contract?

Startup performs only an authenticated metadata read:

```http
GET /v1/<mount>/keys/<key-name>
```

Require `data.type == "ecdsa-p256"`, `data.derived == false`, `data.exportable == false`, `data.deletion_allowed == false`, a disabled/zero `data.auto_rotate_period`, signing support, and an entry at `data.keys[decimal configured version]`. For that exact entry require PEM `public_key` and curve `name == "P-256"` (Go's `elliptic.P256().Params().Name`). Parse PEM as an `*ecdsa.PublicKey`, require `Curve == elliptic.P256()`, marshal it back to PKIX DER, and compare its digest with the deployment manifest.

OpenBao's pinned source returns `latest_version` and the complete asymmetric `keys` map, with each version containing `name` and `public_key`; for ECDSA the public key is PEM. The sign path accepts the hash algorithm in the URL, decodes `input` using standard base64, skips hashing when `prehashed=true`, signs the selected version, ASN.1-marshals ECDSA by default/explicit request, and returns `signature` plus the actual `key_version`. OpenBao formats signatures using `vault:v{{version}}:`.

The dedicated signer needs only metadata read and sign capabilities for this one mount/key. It must not expose CreateKey, rotate, import, export, backup, restore, delete, configuration-update, or Transit verify behavior.

### 7. Which implementation option is bounded and supportable?

| Option | Identity safety | Change/risk | Decision |
|---|---|---|---|
| Small maintained Rekor v1.5.4 fork patch | Can pin exact version, key, tree, and hostname at Rekor's existing signer boundary; covers SET and checkpoint | Small fork maintenance burden; must carry tests across security updates | **Recommend now** |
| Upstreamable strict sigstore provider enhancement | Could benefit all consumers and remove later fork code | Provider API and Rekor still need explicit configuration plumbing; review/release timing is outside this deployment | Follow-on after the fork proves the contract |
| Existing bare `openbao://`/`hashivault://` | Mutable latest-version public key and initialization-only token; Rekor supplies no key-version option | Minimal code, unacceptable identity ambiguity | **No-go** |
| Generic signing sidecar | Could isolate credentials | Adds a new protocol/process and, unless separately authenticated, an unauthenticated signing boundary; still must define exact bytes/version/identity and availability semantics | **Reject** |
| Rekor v2/Tessera migration | Modernizes the log architecture | Different migration, data, API, bundle, and operational problem; does not safely patch the current Rekor v1 log | Defer as a separately designed migration |

Use `github.com/hashicorp/vault/api v1.23.0`, already present indirectly in Rekor's module graph, and promote it to a direct dependency. It supplies established address, TLS, request, error, and JSON handling without adding an OpenBao server dependency or crypto library. Rekor-owned code must still strictly validate all OpenBao response fields and must not reuse the existing provider's latest-version cache.

A narrow `net/http` client is the alternative. It offers complete control over per-request token headers and a smaller conceptual surface, but duplicates TLS configuration, error decoding, request construction, and response handling already supplied by the pinned API client. Choose `vault/api` subject to the credential-reload/race tests in Gate 1. If its client cannot safely support atomic per-request token reload without shared-header races, stop and either instantiate immutable request clients from a token supplier or switch to the narrow `net/http` design; do not fall back to an initialization-only token.

### 8. Can it be deployed and rolled back without changing identity?

Yes, but only after all five gates pass. Restore immutable identity before process activation, prove it offline/fixture-only, then activate the signer while Rekor writes remain disabled. Rollback is safe only (a) before any new Rekor write, or (b) by reverting to a binary that implements the **same** SHA-256/P-256/DER signer contract against the same OpenBao mount, key name, exact version, public key, hostname, shard map, and Trillian tree ID.

Rollback must never delete or rotate the key, delete or recreate the tree, change `tlog_id`, select latest, swap the public key, rewrite shard history, or change hostname/origin. If a post-write rollback binary cannot use the same signer contract, stop writes and preserve state for recovery; do not attempt an identity swap.

## Verified call-path trace

```text
root.go flags/Viper
  -> pkg/api/api.go NewAPI: construct SigningConfig
    -> pkg/sharding/ranges.go NewLogRanges/initializeRange
      -> pkg/signer/signer.go explicit OpenBao dispatch
        -> pkg/signer/openbao.go: metadata GET, exact-version P-256 snapshot
      -> PublicKey() -> PKIX DER + PEM -> LogID
      -> tree ID remains the separately configured Trillian identity

entry response path
  -> entries.go signEntry
  -> JCS(LogEntryAnon) exact bytes
  -> OpenBao SignMessage -> SET DER bytes
  -> LogEntryAnon.Verification.SignedEntryTimestamp

checkpoint path
  -> CreateAndSignCheckpoint(hostname, treeID, size, root)
  -> exact note bytes -> same OpenBao SignMessage
  -> signed-note envelope -> InclusionProof.Checkpoint / log-info checkpoint

public-key path
  -> /api/v1/log/publicKey?treeID=<decimal>
  -> shard range's snapshotted exact-version PEM

consumer path
  -> Rekor response/bundle carries body, integrated time, log index, LogID,
     SET and inclusion proof/checkpoint
  -> Cosign v3.1.3 offline verification selects trusted Rekor material by LogID,
     verifies SET/inclusion material, and must continue verifying old fixtures
```

No checkpoint, Merkle, API-model, generated OpenAPI, or protobuf bundle code should change. If implementation appears to require such a change, return to design review.

## Future fork patch surface

### `cmd/rekor-server/app/root.go`

Add a mutually exclusive explicit OpenBao signer mode and flags/config keys for:

- address (HTTPS required outside fixture tests);
- TLS CA path and optional TLS server name where deployment PKI requires them;
- Transit mount;
- key name/reference;
- exact positive key version;
- token credential-file path;
- bounded request timeout.

Never accept a token value in a flag, Viper config value, URI, command line, environment dump, error, metric label, or log. Reject partial OpenBao configuration, key version zero, a simultaneous generic signer, empty hostname, zero tree ID in activation mode, non-HTTPS production addresses, and unknown fields. Help text must state that bare `openbao://` is not the strict mode.

### `pkg/api/api.go`

Map only the non-secret flags into an extended `signer.SigningConfig`. Preserve the explicit tree ID. Ensure errors are returned before any tree creation or entry-write capability is enabled. A production activation wrapper must never invoke `NewAPI(0)`.

### `pkg/signer/signer.go`

Extend `SigningConfig` with a typed/nested OpenBao configuration rather than encoding security policy into a URI. Dispatch explicit OpenBao mode before generic KMS/file fallback. Keep the return type `signature.Signer`. Validate mutual exclusion and make `IsUnset` account for the new mode. Avoid changing generic providers for inactive shards unless their configuration explicitly selects the strict mode.

### `pkg/signer/openbao.go`

Add a dedicated unexported or narrowly exported signer with:

- immutable fields for mount, key name, positive version, snapshotted `*ecdsa.PublicKey`, canonical PEM/DER digest, and bounded HTTP client;
- a credential supplier that reads a short-lived token from the operator-approved credential file, trims only the file's terminal whitespace contract, rejects empty/oversized/unsafe-permission inputs as specified by operations, never logs it, and reloads it without a process restart;
- startup metadata load and strict `ecdsa-p256`, non-derived, non-exportable, deletion-disabled, no-auto-rotation, exact-version checks;
- `PublicKey(opts ...signature.PublicKeyOption) (crypto.PublicKey, error)` returning a defensive copy of the immutable snapshot and never consulting latest again;
- `SignMessage(io.Reader, ...signature.SignOption) ([]byte, error)` reading the raw bytes, SHA-256 hashing once, signing with `prehashed=true`, strictly checking prefix/body/returned version, parsing exact DER, locally calling `ecdsa.VerifyASN1`, and failing closed;
- context propagation from `options.WithContext`, a maximum reader/request size appropriate to SET/checkpoint payloads, timeouts, cancellation, and no automatic retry of signing requests unless an idempotency analysis later proves it safe. ECDSA signatures are nondeterministic; transparent retry can hide ambiguous remote execution even though an additional signature does not append a log entry.

Do not add key creation, import, rotate, export, delete, backup, restore, remote verify, latest-key refresh, or fallback-to-file behavior.

### Tests and fixtures

- `pkg/signer/openbao_test.go`
- `pkg/signer/testdata/openbao/` containing static test-only P-256 public keys, DER signatures, request/response JSON, and malformed variants
- `cmd/rekor-server/app/root_test.go` and/or focused `pkg/api` configuration tests
- `pkg/sharding/ranges_test.go`
- existing `pkg/util/checkpoint_test.go`, extended only for format regression if necessary
- a committed test-only Rekor response/bundle fixture plus Cosign v3.1.3 offline acceptance invocation in the future fork's CI harness

Use an `httptest` TLS server and static fixtures only. Test keys and signatures are non-production fixtures committed for deterministic tests; tests must not generate, import, or discover production material and must never require a live OpenBao, network service, production credential, or Rekor submission.

### `go.mod` and `go.sum`

Promote `github.com/hashicorp/vault/api v1.23.0` from indirect to direct if the selected implementation imports it. Expect `go.sum` to remain consistent after the future fork's normal module tooling. Add no OpenBao server dependency and no new cryptography library; use Go's `crypto/ecdsa`, `crypto/elliptic`, `crypto/sha256`, `crypto/x509`, `encoding/asn1`, `encoding/base64`, and `encoding/pem`.

## Fixture-only verification matrix

### Positive cases

- Metadata for exact version `N`, `ecdsa-p256`, `P-256`, and expected PEM initializes successfully even when `latest_version > N`.
- `PublicKey` stays byte-for-byte stable across repeated calls and a simulated latest-version metadata change.
- SET fixture: captured JCS bytes are hashed once; the recorded request contains standard-base64 binary SHA-256, `prehashed=true`, exact `key_version`, `marshaling_algorithm=asn1`, and no `signature_algorithm`; returned DER verifies locally.
- Checkpoint fixture: exact `hostname + " - " + decimal treeID + LF + decimal size + LF + standard-base64 root + LF` bytes take the same signing path and verify.
- Restart fixture: identical config/metadata produces identical PEM, PKIX DER digest, `LogID`, signed-note hint, tree mapping, and origin.
- Isolated backup/restore simulation: restore fixture metadata and tree snapshot into an isolated test namespace, in the prescribed order, and prove the identity tuple and old fixtures are unchanged. This is fixture simulation only—not an OpenBao backup/restore call.
- Cosign v3.1.3 offline verification accepts a static old bundle and a static new-signer bundle using trusted material that contains the applicable log identity; no network access.
- Credential file token replacement is observed without restart, old token bytes are not retained/logged, concurrent sign operations are race-clean, and cancellation/timeouts propagate.

### Negative/fail-closed cases

- OpenBao unavailable, timeout, cancellation, DNS/connection failure, or non-2xx response.
- TLS unknown CA, hostname mismatch, expired certificate, and plaintext HTTP in production mode.
- Missing, unreadable, empty, oversized, badly permissioned, expired, or unauthorized token; 401/403; token changes mid-request.
- Malformed/truncated/oversized JSON; missing `data`, `signature`, `key_version`, `keys`, exact version, `public_key`, or `name`; wrong JSON types.
- Wrong key type, non-signing key, derived/exportable/deletion-enabled/auto-rotating policy, wrong curve, malformed PEM, or public-key digest differing from deployment manifest.
- Configured version zero/negative, exact version absent, response version differs, prefix is missing/malformed or names another version, and latest version changes before/after cache-equivalent intervals.
- Standard-base64 errors, URL-safe-base64 substitution, hex digest input, raw-message/prehashed mismatch, and explicit double-hash fixture mismatch.
- Invalid DER, trailing DER bytes, out-of-range/zero ECDSA integers, and a syntactically valid signature that fails local verification.
- Wrong SET canonical bytes or changed `LogEntryAnon`; checkpoint missing final LF, CRLF substitution, altered root-base64, hostname/origin change, or tree ID change.
- Restart with a new/missing tree ID, wrong shard mapping, new public key, new hostname, or unavailable exact-version metadata.
- Isolated restore with key/tree order reversed, restored key identity mismatch, stale tree snapshot, or a tree head that does not match the expected checkpoint.
- Old-bundle Cosign verification fails when the trusted-root validity window/log identity is omitted; the test must then pass with correct overlapping trusted material.

Tests should also run `go test -race` on the signer/config packages and a dependency/vulnerability scan already accepted by the future fork. No test may weaken a preflight gate or make a live endpoint optional fallback.

## Key, log identity, sharding, and rotation policy

The future production key is a dedicated Rekor log key. It must **not** reuse `datapulse-cosign` or any artifact/certificate/attestation key. No production key material is created by this brief.

Required eventual key properties:

- ECDSA P-256;
- non-derived;
- non-exportable and plaintext backup disabled;
- deletion disabled;
- automatic rotation disabled;
- exact positive version pinned in Rekor and in the deployment identity manifest;
- old version retained and readable/verifiable for the lifetime of its log evidence.

The immutable identity manifest should record at least: Rekor fork commit/image digest, OpenBao cluster/namespace identifier, address trust anchor, Transit mount, key name, exact version, exact public-key PEM, PKIX DER SHA-256/`LogID`, note hint, Trillian tree ID, shard boundary/length if inactive, Rekor hostname/origin, trusted-root validity interval, and backup/tree snapshot identifiers. Store no token or SecretID in it.

Rotation is never an in-place silent rollover. A planned rotation creates a new dedicated key/version identity and a new Rekor shard/log identity with an explicit tree/shard mapping. Freeze and retain the old shard/key, publish trusted material containing old and new Rekor log public keys with overlapping validity sufficient for old evidence, validate Cosign against both, then direct new writes to the new active identity. The exact choice between a new key name and a retained old version is an operator design decision, but a new externally visible `LogID` and planned shard boundary are mandatory.

## Authentication lifecycle

Assumption, not a verified production fact: Rekor receives a short-lived, narrowly scoped token through an operator-approved credential broker/agent or an exact AppRole workflow. The signer receives only a token credential-file path. It must never embed or persist a SecretID, place a token in flags/config/URI/logs, or acquire broader OpenBao capabilities.

The current pinned provider reads and sets the token only during initialization. That is insufficient. Before implementation can pass Gate 1, operators and implementers must select and document one exact lifecycle:

- broker/agent atomically renews or replaces the credential file before expiry and the signer safely reloads it per request or via an audited watcher; or
- a precisely specified AppRole login component obtains and renews a token without embedding SecretID in Rekor, with response wrapping/file handoff, expiry, revocation, and restart behavior defined.

Unknown and deliberately unresolved here: broker product, AppRole role/policy names, SecretID delivery channel, token TTL/periodicity, renewal owner, file path/owner/mode, namespace headers, HA address behavior, and failure grace period. These require an operator-approved threat model and fixture tests. There is no authorization to inspect or change production authentication.

## Restore order, restart criteria, and rollback

### Isolated restore rehearsal order

1. Keep all Rekor writes disabled and isolate the rehearsal from production endpoints.
2. Restore OpenBao storage/key metadata using the operator-approved platform procedure; do not enable signing traffic.
3. Read fixture/exported metadata only and compare mount, key name, exact version, P-256 public key, and `LogID` to the sealed identity manifest.
4. Restore Trillian database/tree state and confirm the explicit tree ID, tree head/size/root, and shard mapping.
5. Restore the fixed Rekor hostname/origin and strict signer configuration.
6. Start the candidate binary in no-write/readiness mode; require exact identity checks, public-key endpoint match, and checkpoint/SET fixture verification.
7. Run old/new Cosign offline fixtures with overlapping trusted material.
8. Destroy or quarantine the isolated rehearsal according to the operator runbook. This document does not authorize a real restore.

### Restart acceptance criteria

A restart is acceptable only if, before readiness for writes, it proves the same key version/public key/`LogID`, same explicit tree ID and shard map, same hostname/origin, reachable authenticated Transit metadata/signing service, working token reload/renewal, and successful local signature self-check. Any mismatch leaves the service unready and writes disabled. Do not create a tree or choose latest as recovery behavior.

### Rollback criteria

- **Before first write:** stop the candidate and restore the prior binary/config without touching key/tree state.
- **After any candidate write:** only revert to a binary verified to use the identical signer contract and identity tuple. Retain the candidate's entries, tree, key version, and trusted material.
- If identity or tree consistency cannot be proven, freeze writes, retain all evidence, and escalate. Never repair by deleting a tree/key, rotating, changing hostname, editing bundles, or substituting a public key.

## Resource and operational impact

- **Latency:** each SET and each newly generated checkpoint causes a remote Transit sign request. A normal entry response can therefore require two ECDSA Transit operations in addition to the metadata read at startup. Periodic checkpoint publication also signs. Capacity planning must derive actual request rates from staging metrics; no production QPS is verified here.
- **Availability:** OpenBao, TLS, network, token supply, and exact key version become synchronous signing dependencies. The design fails closed; it must not fall back to memory/file/latest or return an unsigned/unchecked response.
- **Load:** SHA-256, ASN.1 parsing, and local P-256 verification are small CPU costs, but remote round-trip latency and OpenBao concurrency dominate. Bound connection pools, timeouts, request/response sizes, and concurrent operations after staging measurements.
- **Observability:** record operation class (`metadata`/`sign`), outcome, status class, latency, timeout/auth/version/local-verify failures, and readiness—never token, SecretID, input/digest, signature, public key in routine logs, or full OpenBao response. Public key and `LogID` may appear only in deliberate identity audit output.
- **Credential operations:** renewal/reload must not require a Rekor restart and must fail closed on expiry or bad replacement. Alert before expiry and on repeated 401/403 without logging credentials.
- **Maintenance:** carry a small fork patch over Rekor v1.5.4 security updates until an upstream solution or separately approved Rekor v2/Tessera migration replaces it. Pin build source and dependency checksums.
- **Backups:** exact-version OpenBao state and Trillian state have a coupled recovery objective even though they are separate systems. Backup/restore procedures, retention, RPO/RTO, quorum behavior, and disaster credentials are currently unverified.

## Five explicit gates

### Gate 1 — implementation gate

**Owner:** future fork maintainers and security reviewer.  
**Pass requires:** the exact patch surface above; strict config/startup validation; immutable exact-version public key; once-only SHA-256 and local ECDSA verification; safe short-lived-token reload/renewal design; no secret logging; fixture-only positive/negative matrix; `go test -race`; dependency review; and independent code review. `vault/api` token handling must be proven race-safe or replaced with the narrow-client design.  
**Blocks:** merge/build promotion.  
**Rollback:** source-only revert; no external state exists.

### Gate 2 — key generation/import gate

**Owner:** operator plus security/key custodians.  
**Pass requires:** explicit approval of create-versus-import; dedicated non-reused key; P-256/non-derived/non-exportable/no-auto-rotation/deletion-disabled policy; exact version and public identity recorded; scoped read/sign policy; tested backup/restore procedure; and dual control/audit evidence.  
**Blocks:** any production key creation or import.  
**Current status:** **blocked/out of scope and unverified**. This document creates or imports nothing.

### Gate 3 — production signer activation gate

**Owner:** operator/SRE/security.  
**Pass requires:** pinned fork image digest; approved TLS trust and credential lifecycle; explicit non-zero existing Trillian tree ID; exact signer/shard/hostname identity manifest; isolated restore rehearsal; capacity/alerting/readiness validation; public-key and `LogID` match; and writes held disabled.  
**Blocks:** configuring or starting the candidate against production OpenBao/Rekor state.  
**Rollback:** revert binary/config while preserving the same key/tree identity; no writes have occurred.

### Gate 4 — first Rekor write gate

**Owner:** operator with a second reviewer.  
**Pass requires:** Gate 3 evidence, a successful no-write canary signature/self-check using the approved mechanism, SET and checkpoint fixture verification, token rollover observation, backup timestamps within policy, exact public-key endpoint result, unchanged tree head before enablement, and a written rollback decision point.  
**Blocks:** the first entry submission or any action that advances the tree.  
**Rollback:** before write only; once a write occurs use the post-write same-identity rule.

### Gate 5 — cutover/rotation gate

**Owner:** operator, security, SRE, and trust-root publisher.  
**Pass requires:** defined shard boundary/new identity, old shard/key retention, new tree mapping, old/new trusted-root validity overlap, Cosign v3.1.3 offline verification of old and new bundle fixtures, client distribution/rollback plan, monitoring window, and evidence that no in-place silent version rollover occurs.  
**Blocks:** declaring production cutover complete, retiring old trusted material, or any future rotation.  
**Rollback:** route new writes only according to the pre-approved shard plan; never swap identity inside an existing shard.

## Pinned evidence and sources

All source claims were checked against the prepared read-only checkouts at the exact commits below. GitHub links are immutable commit-pinned blobs. The OpenBao web API page is official but rolling; where it and code differ, the v2.6.2 source commit is authoritative for this design.

| Project/version | Exact source | Evidence used |
|---|---|---|
| Rekor v1.5.4, `a36bd716fd0d81c314092718f37b53dc26b2af38` | [`cmd/rekor-server/app/root.go`](https://github.com/sigstore/rekor/blob/a36bd716fd0d81c314092718f37b53dc26b2af38/cmd/rekor-server/app/root.go) | signer help, hostname, tree-ID and signer flags |
| Rekor v1.5.4 | [`pkg/signer/signer.go`](https://github.com/sigstore/rekor/blob/a36bd716fd0d81c314092718f37b53dc26b2af38/pkg/signer/signer.go) | blank import, provider dispatch, `kms.Get(..., crypto.SHA256)` |
| Rekor v1.5.4 | [`pkg/api/api.go`](https://github.com/sigstore/rekor/blob/a36bd716fd0d81c314092718f37b53dc26b2af38/pkg/api/api.go) | flag-to-`SigningConfig`; zero tree ID creates a tree |
| Rekor v1.5.4 | [`pkg/sharding/ranges.go`](https://github.com/sigstore/rekor/blob/a36bd716fd0d81c314092718f37b53dc26b2af38/pkg/sharding/ranges.go) | signer initialization, PEM, PKIX DER SHA-256 `LogID`, tree-key mapping |
| Rekor v1.5.4 | [`pkg/api/entries.go`](https://github.com/sigstore/rekor/blob/a36bd716fd0d81c314092718f37b53dc26b2af38/pkg/api/entries.go) | JCS SET bytes, same signer for SET/checkpoint, response/bundle fields |
| Rekor v1.5.4 | [`pkg/util/checkpoint.go`](https://github.com/sigstore/rekor/blob/a36bd716fd0d81c314092718f37b53dc26b2af38/pkg/util/checkpoint.go) and [`pkg/util/signed_note.go`](https://github.com/sigstore/rekor/blob/a36bd716fd0d81c314092718f37b53dc26b2af38/pkg/util/signed_note.go) | exact note bytes, origin/name, same signer, four-byte key hint |
| Rekor v1.5.4 | [`pkg/api/public_key.go`](https://github.com/sigstore/rekor/blob/a36bd716fd0d81c314092718f37b53dc26b2af38/pkg/api/public_key.go) | public-key endpoint delegates by tree ID |
| Rekor v1.5.4 | [`go.mod`](https://github.com/sigstore/rekor/blob/a36bd716fd0d81c314092718f37b53dc26b2af38/go.mod) | sigstore/hashivault v1.10.9 and Vault API v1.23.0 indirect dependency |
| sigstore v1.10.9, `ee9fe03b11a63574abdfbee85dd776ad28106e69` | [`pkg/signature/signer.go`](https://github.com/sigstore/sigstore/blob/ee9fe03b11a63574abdfbee85dd776ad28106e69/pkg/signature/signer.go) | `signature.Signer` interface |
| sigstore v1.10.9 | [`pkg/signature/kms/hashivault/client.go`](https://github.com/sigstore/sigstore/blob/ee9fe03b11a63574abdfbee85dd776ad28106e69/pkg/signature/kms/hashivault/client.go) | dual schemes, BAO fallbacks, 300-second latest public-key cache, Transit request and prefix decode |
| sigstore v1.10.9 | [`pkg/signature/kms/hashivault/signer.go`](https://github.com/sigstore/sigstore/blob/ee9fe03b11a63574abdfbee85dd776ad28106e69/pkg/signature/kms/hashivault/signer.go) | initialization-only auth/options, digest behavior and version support |
| OpenBao v2.6.2, `dd9c19c37a878cf4a81b18efb8d6f0599c7da923` | [`builtin/logical/transit/path_sign_verify.go`](https://github.com/openbao/openbao/blob/dd9c19c37a878cf4a81b18efb8d6f0599c7da923/builtin/logical/transit/path_sign_verify.go) | sign route, input decoding, `prehashed`, version, ASN.1, response fields |
| OpenBao v2.6.2 | [`builtin/logical/transit/path_keys.go`](https://github.com/openbao/openbao/blob/dd9c19c37a878cf4a81b18efb8d6f0599c7da923/builtin/logical/transit/path_keys.go) | metadata, latest version, per-version public key and curve name |
| OpenBao v2.6.2 | [`sdk/helper/keysutil/policy.go`](https://github.com/openbao/openbao/blob/dd9c19c37a878cf4a81b18efb8d6f0599c7da923/sdk/helper/keysutil/policy.go) | `vault:vN:` template, version selection, P-256 ECDSA and ASN.1 encoding |
| OpenBao official API docs | [Transit secrets engine API](https://openbao.org/docs/next/api/secret/transit/) | official public contract for read-key and sign-data endpoints; rolling documentation |
| Cosign v3.1.3, `11926fa5bbbbde47e88fc006b625a17769b743b2` | [`pkg/cosign/tlog.go`](https://github.com/sigstore/cosign/blob/11926fa5bbbbde47e88fc006b625a17769b743b2/pkg/cosign/tlog.go) | bundle fields, inclusion proof, LogID decoding and trusted-material SET verification |
| Cosign v3.1.3 | [`pkg/cosign/verify.go`](https://github.com/sigstore/cosign/blob/11926fa5bbbbde47e88fc006b625a17769b743b2/pkg/cosign/verify.go) and [`test/e2e_test.go`](https://github.com/sigstore/cosign/blob/11926fa5bbbbde47e88fc006b625a17769b743b2/test/e2e_test.go) | offline bundle verification and trusted-root acceptance patterns |

## Explicit unknowns and required operator decisions

- The actual production key does not exist by virtue of this brief; create versus import, custody, naming, version number, and backup mechanism are unverified and blocked at Gate 2.
- The production Trillian tree ID, current tree state, shard config, Rekor hostname, and desired trust-root validity windows were not inspected.
- The exact OpenBao address, namespace, mount, CA, TLS server name, HA topology, policy paths, audit devices, and disaster-recovery topology were not inspected.
- The authentication broker/AppRole flow, SecretID delivery, token TTL/renewability, renewal owner, credential file semantics, and revocation behavior remain unverified. This is a mandatory Gate 1 and Gate 3 decision.
- `vault/api` concurrent token replacement safety for the chosen implementation pattern must be proved under the race detector; it is not assumed.
- Actual latency, Transit QPS, timeout budget, checkpoint publication rate, availability objective, RPO/RTO, and alert thresholds need staging measurements.
- Exact Cosign trusted-root generation/distribution commands and bundle media types for this deployment need a separate fixture-backed runbook; this brief verifies the compatibility boundary, not production distribution.
- Rekor v1.5.4's future security-support lifetime and the schedule for a Rekor v2/Tessera migration are organizational decisions.

## Evidence statement

This audit read only the four prepared official source checkouts, the official public OpenBao Transit API documentation, and repository status. It did not authenticate to production, call Transit sign/verify, create/import/rotate/delete/backup/restore a key, submit a Rekor entry, change OpenBao/Rekor/systemd/Docker/firewall state, restart a service, edit code/generated artifacts/public docs, commit, or push. Pre-existing untracked work was preserved.

**Pushed: NO**
