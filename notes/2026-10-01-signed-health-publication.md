# 2026-10-01 staged signed health publication

This slice is exercised only with disposable in-memory Ed25519 keys, mock KV and
mock same-deployment assets. It is source implementation, not runtime adoption,
a public coverage claim, or an upstream-truth assessment. No production endpoint,
service, registry, credential, workflow or deployment configuration was used or
changed. No generators run and no generated output is introduced.

## Frozen protocol v1

Covered signed subject: `health/latest.json`, with claim scope
`exact-health-snapshot`. Designated staged GET surfaces:

- `/health/verified/latest.json`
- `/health/verified/<publication-sha256>.json`

The existing `/health/latest.json`, dashboard, MCP answers, other health files,
HTTP errors and response headers are excluded from signature coverage. A derived
answer needs its own verifiable derivation or signature in a later integration.

The caller reads the snapshot once and passes immutable Python `bytes` to
`build_package`. All original bytes and fields, including heartbeat and unknown
extensions, survive unchanged. There is no observation-receipt normalization or
projection. The existing canonical convention (UTF-8, sorted JSON keys, compact
separators, no ASCII escaping) creates the binding and package. Consumers verify
carried binding bytes directly; JavaScript never reserializes JSON to verify a
signature. Duplicate property names, including escaped aliases, are rejected at
every parsed JSON layer. JSON must be UTF-8 and contain finite numbers. Nesting
is limited to 64. Protocol integer fields must actually be JSON integers.

Immutable object bytes have exactly this layout (illustrative placeholders):

```json
{"schema":"datapulse/v1/signed-health-package","version":1,"health_base64":"<exact health bytes>","binding_base64":"<exact binding bytes>","signature_base64":"<64-byte Ed25519 signature>"}
```

`binding_base64` decodes to an object with exactly these authenticated fields:

```json
{
  "schema": "datapulse/v1/signed-health-binding",
  "version": 1,
  "subject": "health/latest.json",
  "health_sha256": "<64 lowercase hex characters>",
  "health_bytes": 123,
  "observed_at": "<health.checked_at, verbatim>",
  "assembled_at": "<assembly clock>",
  "signed_at": "<signing clock>",
  "source_commit": "<40 lowercase hex characters>",
  "key_id": "ed25519-<first 16 hex characters of SHA256(raw public key)>",
  "signer_public_key_sha256": "<SHA256(raw public key)>",
  "algorithm": "Ed25519",
  "key_purpose": "attestation-chain-signing",
  "policy": "health-observation-36h-v1",
  "claim_scope": "exact-health-snapshot",
  "source_truth_verified": false
}
```

Signature input is the ASCII domain `datapulse/v1/signed-health-binding`, one
NUL byte, then the exact decoded binding bytes. Signer injection is a callable
`signer(input_bytes) -> signature_bytes`; no key file, signer socket or network
is opened by this module. Signer output must be 64 bytes and pass verification
against the separately trusted registry before publication. The source commit
is an authenticated signer assertion with strict syntax, not an offline proof
that Git contains those bytes. Assembly/signing time is distinct from observation
time. No Rekor witness, cryptographic clock or upstream truth is asserted.

`publication_sha256 = SHA256(complete immutable object bytes)`, including the
signature. It is not a signed circular self-digest. Every base64 field is standard
padded canonical base64, not a URL or an external reference. Digests are lowercase
hexadecimal. Timestamps must be real UTC RFC3339 instants, ending in `Z` or
`+00:00`, with zero to six fractional digits; naive times, other offsets, leap
seconds, impossible dates and trailing whitespace are rejected explicitly.

## Storage, publisher and serving

Storage keys (independent of the explicitly supplied destination):

```text
signed-health/v1/objects/<publication-sha256>.json  # complete immutable object
signed-health/v1/latest.json                      # independently mutable pointer
```

The pointer has exactly two fields:

```json
{"schema":"datapulse/v1/signed-health-pointer","publication_sha256":"<64 lowercase hex characters>"}
```

`publish_package` requires an explicit destination identifier and injected
`PublicationTransport`. It has no production destination default, credential
discovery, network client, retry/cadence mutation or default write invocation.
The existing unsigned publisher stays unchanged and its fixed key set does not
target this prefix. New fixture writes follow this exact order:

1. Verify the complete candidate against trust, policy and consumer clock.
2. GET immutable object key; reject an existing different byte string.
3. If absent, `create(destination, key, exact_package_bytes)`.
4. GET that object again; require byte equality and independently verify again.
5. `put_pointer(destination, latest_key, pointer_bytes)`.

The transport's `create` contract MUST atomically reject different existing
bytes, or run under an externally enforced single-writer serialization mechanism
that supplies this guarantee. Blind KV GET/PUT alone cannot implement this
contract. The in-memory fixture implements conditional creation; a production
adapter is deliberately absent. It must be reviewed before promotion. Existing
identical objects are reused without overwrite. Interrupted/partial object
writes, collisions, invalid signer output and read-back mismatch do not attempt
a pointer write. Fixture pointer-write failure leaves the old pointer intact.
A future remote adapter must report an unknown acknowledgement honestly: a
pointer PUT can succeed remotely before the caller sees a transport error. Even
then only a complete previously verified object may have been advertised; this
slice makes no global transaction or acknowledgement guarantee.

The route uses the existing `DATAPULSE_HEALTH_INDEX` read binding only; no new
configuration dependency or write capability is installed. It reads a pointer
once, then only the object named by that pointer. It never reads unsigned health
bytes as the candidate, combines separately mutable proof/payload fields, or
falls back to unsigned static health. A delayed object can return 503. An old or
reordered pointer can return an older complete verified object within policy.
There is no claim of globally newest state or globally atomic Cloudflare KV.

Successful HTTP body, shared by Python and JavaScript:

```json
{"schema":"datapulse/v1/signed-health-response","publication_sha256":"<SHA256(package bytes)>","package_base64":"<complete immutable object bytes>"}
```

The response carries proof, snapshot, claim and exact package identity. Clients
must independently call `verify_response` (or an equivalent verifier) using
their own trust, clock and floors. HTTP 200 alone is insufficient. The identity
field is checked against the exact carried object, then all binding/digest/key/
signature/policy checks run. An optional `expected_publication` consumer pin
rejects a different complete version. No health/proof stripping occurs.

All route responses use `Cache-Control: no-store`. Unknown paths return 404;
non-GET requests return 405; unsupported or repeated query parameters return
400. Missing/malformed trust, pointer, package or proof, unsafe key identities,
oversized input and unsupported runtime Ed25519 return 503 with
`{"error":"verified_health_unavailable"}`. No crypto check is skipped. A
malformed freshness-floor value also returns 503, without acceptance.

Bounds: package 8 MiB, health bytes 5 MiB, binding 4096 bytes, registry 256 KiB,
pointer 1024 bytes. Registry asset reads are stream-bounded. KV's ArrayBuffer
API allocates the fetched value before this code can check its length; the
application rejects it before JSON/base64/signature processing. Transport-level
resource limits remain an operator concern for an eventual adapter.

## Separate trust and replay policy

Trust is supplied separately to Python, using the existing
`datapulse/v2/probe-key-registry`, version 2. JavaScript obtains the registry
only through `env.ASSETS.fetch` at the fixed same-deployment asset
`/.well-known/datapulse-probe-keys.json`. It does not call public network fetch,
accept a package-provided registry/key/URL, or trust a KV registry. The fixture
supplies that trusted asset explicitly. Registry delivery and signer injection
are independent of untrusted package bytes.

Both verifiers require unique registry key identities, exactly one active
`attestation-chain-signing` key, that key as `current_key_id`, algorithm Ed25519,
matching raw public-key hash/key id, valid key windows at signing AND consumer
time, and no non-null `compromised_at` or `revoked_at`. Revoked, compromised,
superseded, expired, ambiguous, wrong-purpose and wrong-identity keys fail.
Other key purposes confer no signing authority on this protocol. Observation
receipt socket purpose/normalization is not reused for this separate binding.

The named policy `health-observation-36h-v1` accepts an observation at most
129600 seconds old and at most 300 seconds ahead of the consumer clock.
`observed_at <= assembled_at <= signed_at`, with signing at most 300 seconds
in the consumer's future. Both age and key validity are checked on each request;
a new assembly time cannot renew old observation freshness. Boundary values
are inclusive. The handler reads `Date.now()` after asset/storage reads, so a delayed read
cannot reuse request-start freshness (millisecond clock resolution);
signed timestamps retain up to microseconds. Clock correctness is an operational
assumption, not a cryptographic time guarantee.

Optional query `minimum_observed_at=<URL-encoded UTC timestamp>` can only
strengthen handler acceptance. An independent Python consumer supplies
`minimum_observed_at` from retained local state; it does not rely on the server
to remember it. Below-floor observations are rejected even with a valid signature.
Equal observation times do not establish a total publication ordering; use an
expected-publication pin when exact identity is required. The unsigned latest
pointer supplies neither anti-replay authority nor a monotonic version guarantee.
An old authentic snapshot within policy/floor is acceptable with its honest
observation time, never represented as globally newest.

Dynamic age is excluded from the signed claim and response body. The local
verifier reports `age_seconds`, `age_authenticated=false`, the observation and
identity; these are consumer-clock calculations, not new authenticated claims.
No `fresh=true` field is issued. Outside policy there is no acceptable verdict.

There is no application registry/package/verdict cache. Registry assets are read
again for every request, with no-store intent. Revocation is only as current as
the trusted deployment's asset. A still-running old deployment cannot learn a
new revocation without a trusted registry-refresh/deployment mechanism. Offline
consumers also need refreshed trusted registry delivery. No package cache may
reuse an earlier key/freshness verdict. These refresh and rollback limitations
remain production-promotion gates, not solved by this fixture.

## Local evidence

Observed starting HEAD: `10bb7cb4035593d6d0f844720a73177623bf9f59`, the existing
scope-note commit directly above baseline
`eaf56e5fc910ac380b270ff0f655adc9bd0d658e`. Initial tracked tree was clean;
the pre-existing untracked `.venv` is preserved. Initial Control
`bash -c 'test -f scripts/signed_health_publication.py'` exited 1. Initial
quick-test exited 2 with the expected missing-file error. These are artifact
presence floors, not cryptographic evidence.

The new test file collects 121 implementation-sensitive cases. The focused
acceptance selection collects 179 tests, including existing shadow publication,
unsigned publisher and attestation-binding tests. Before the source commit,
the initial 176-case selection passed: `176 passed in 25.04s`; final review added
three Python/JavaScript BOM rejection cases, bringing collection to 179. Fixture repository-contract tests
passed: `12 passed in 0.86s`. Existing unsigned Function/index tests passed all
seven cases when imported explicitly with Node (brackets in the filename require
literal import rather than Node's test-path glob). Final acceptance, quick-test,
repository-contract and whitespace checks are rerun at the committed source
state and their complete outputs and commit SHA accompany the delivery report.
No claim of full scripts/MCP suite success is made.

Behavioral RED proof temporarily replaced the actual Python Ed25519 verification
call with an unconditional successful check. The named test failed because an
altered signature was accepted; there was no syntax or import failure:

```text
$ .venv/bin/python3 -m pytest scripts/tests/test_signed_health_publication.py::test_signature_mutation_rejected -q --tb=short
F                                                                        [100%]
=================================== FAILURES ===================================
_______________________ test_signature_mutation_rejected _______________________
scripts/tests/test_signed_health_publication.py:87: in test_signature_mutation_rejected
    assert_rejected(material, shp.canonical(obj))
scripts/tests/test_signed_health_publication.py:58: in assert_rejected
    with pytest.raises(shp.PublicationError):
         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E   Failed: DID NOT RAISE <class 'scripts.signed_health_publication.PublicationError'>
=========================== short test summary info ============================
FAILED scripts/tests/test_signed_health_publication.py::test_signature_mutation_rejected
1 failed in 0.25s
RED_PROOF_EXIT=1
RESTORED_BYTE_EXACT=true
RESTORED_SOURCE_SHA256=83ff2c019312e22ab767b331a5a29313aadb6ad89e700d04b36afe66865cf20b
```

Source was restored byte-for-byte in a `finally` block. The restored signature
mutation and timestamp-boundary tests passed (`2 passed in 1.49s`), followed by
the complete focused green run. No mutation or private key fixture is committed.
An earlier boundary test incorrectly injected microseconds through JavaScript
`Date.parse`/`Date.now`; it failed with `assert 200 == 503` after the mock clock
rounded the input. The corrected case uses a one-millisecond boundary and passes;
production policy code was not weakened.

The real quick-test emits only a bounded result, no keys, signatures or payloads:

```json
{"age_seconds":60.0,"consumer_verified":true,"fixture_only":true,"handler_status":200,"ok":true,"publisher":"verified_readback_before_pointer","source_truth_verified":false,"writes":2}
```

Behavioral coverage includes exact deterministic construction, payload/claim/
signature mutation, version substitution, borrowed snapshot signature, malformed
and duplicate JSON, type/timestamp attacks, registry identities and key windows,
freshness/floors, interrupted and partial writes, immutable/racing collisions,
read-back mismatch, pointer-before-object, unsigned newer data with old pointer,
signer outage, reordered pointers, unsupported Ed25519 and same-runtime registry
revocation/clock ageing. Packages are created in Python, the actual Pages
`onRequest` runs under Node/WebCrypto with mock KV/assets, and returned object
bytes are checked independently by Python. Quick-test failure is also exercised;
it is not a stub that always reports success.

## Operator integration and rollout gaps

Still open, requiring separately scoped review/authorization:

- Production freeze/signing invocation after final health assembly, with the
  actual existing signing authority, an authorized domain-separated signer
  adapter and separately deployed trusted registry. This slice never contacts
  the observation signer socket or changes key-purpose rules.
- Explicit destination/credential injection and reviewed immutable-create or
  serialized-writer transport, storage retention, write/read-back deadlines,
  acknowledgement ambiguity, and operator-owned concurrency control. No namespace
  or credential is silently selected here.
- Same-deployment registry delivery/refresh, revocation propagation, supported
  Pages Ed25519 runtime verification, deployment routing and trusted asset
  availability; none has been checked on production or preview.
- Production designated-surface inventory, independent consumer adoption, clock
  monitoring and durable anti-replay floors; a server's no-store header alone
  does not protect a consumer from a replay.
- Dashboard/MCP verifiable derivation/signature integration. Their existing
  projection/answers remain unsigned by this slice.
- Monitoring for signer/object/pointer/trust failures, stale verified availability,
  registry expiry and consumer rejection; fail-closed rollback to unavailable or
  a still-acceptable complete older version, never unsigned bytes with borrowed
  proof.
- Full `scripts/tests/` and `mcp/tests/`, independent review and any preview
  remediation gates; deliberately deferred by the dispatch's acceptance scope.
- One-dataset/use-specific assurance with a named suitability policy; no universal
  semantic-truth, completeness or paid-product rail is introduced.
- Push, merge, deployment, workflows/config/secrets, production services and public
  claims require explicit later authorization. This source commit is local only,
  without a deploy trailer, and is not published.
