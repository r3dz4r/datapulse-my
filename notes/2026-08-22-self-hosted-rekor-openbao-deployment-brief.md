# Deployment brief: self-hosted Rekor and OpenBao Transit

Date: 2026-08-22  
Status: review required — no infrastructure or cryptographic operation authorized

## Decision and boundary

DataPulse MY will, subject to the gates below, add a **self-hosted Rekor**
transparency log for a canonical daily DataPulse artifact. Cosign-compatible
bundles will be a second verification representation. The current
Ed25519-signed probe envelopes, daily chain links, and optional Git-tag replay
remain the authoritative compatibility path throughout the transition.

The signing authority must remain operator controlled. **OpenBao Transit is the
recommended KMS provider.** Public Rekor, public Fulcio/OIDC, and public TUF
remain deferred. This prevents national-data trust metadata and signer-identity
operations from crossing into a public Sigstore control plane.

This brief does not authorize key generation, KMS provisioning, signing, Rekor
writes, networking, or deployment. It must not be interpreted as permission to
reuse an existing database, listener, port, volume, credential, or service.

## Artifact and verification contract

The signed unit is a canonical, deterministic daily DataPulse artifact (initial
candidate: the daily chain-head payload or canonical daily evidence manifest).
Its SHA-256 digest is the identity shared by both paths:

```text
canonical daily artifact digest
  ├── existing Ed25519 envelope → chain link → optional Git-tag anchor
  └── Cosign-compatible bundle → OpenBao signing identity → Rekor inclusion evidence
```

The bundle must carry, in a format accepted by the selected real verifier:

- the exact artifact digest;
- the operator-controlled signing identity and public verification material;
- Rekor log identity, log index, inclusion proof, and signed-entry evidence;
- enough retained trust configuration to identify the self-hosted log and
  verification policy without consulting public Fulcio, OIDC, Rekor, or TUF.

The migration fixtures in `scripts/tests/fixtures/sigstore_rekor_migration/`
are a normalized pre-integration contract, not a substitute for Cosign or
Sigstore verification. They cover legacy chain/Git-tag compatibility, the
shared digest, digest mismatch, malformed metadata, missing inclusion evidence,
and an unavailable Sigstore verifier that fails closed while preserving a valid
legacy result. No fixture contains a key, certificate, token, valid signature,
or live inclusion proof.

Before production code is changed, an implementation must use the real Cosign
CLI/library's documented bundle verifier and prove its exact bundle schema
against a non-production self-hosted environment. Do not invent a local
Cosign/OpenBao/Rekor API to bridge that gap.

## First deployment topology

Deploy a separate private trust-log boundary containing:

- Rekor server;
- Trillian log server and signer;
- a **dedicated** MySQL-compatible database for Rekor/Trillian only;
- optional Redis used only for retrieval/search acceleration, never as the
  source of log truth;
- separate, explicitly named persistent volumes for database data, Trillian
  tree/shard state, Rekor state/configuration, and backups.

The first listener binding is tailnet/private only (loopback or Tailscale after
operator approval). There is no Cloudflare route, public DNS name, public MCP
hostname reuse, or public ingestion endpoint. Discover occupied ports,
container names, service accounts, database names, volume paths, storage
capacity, and resource limits read-only before proposing values. Select a new
approved port only after that inventory; do not assume availability or bind over
an existing service.

Rekor's Merkle tree identity, Trillian shard/tree configuration, and their
backing storage are durable security state. Pin the approved component versions
and migration order in the later implementation dispatch. For every upgrade:

1. take and verify a consistent backup;
2. record current tree IDs, shard configuration, image versions, and schema
   versions;
3. rehearse the upgrade and verifier compatibility using an isolated restored
   copy; and
4. apply only through an approved maintenance procedure with a documented
   rollback point.

Never rebuild, delete, reseed, or silently replace a tree/shard. A changed log
identity is a trust-boundary event requiring operator approval and explicit
consumer communication.

## Backup, restore, and availability requirements

Before the first production Rekor write, perform and record an isolated restore
test of the dedicated MySQL-compatible database and every persistent volume
needed to preserve Rekor/Trillian Merkle state. The restore test must verify:

- the restored log retains its expected log identity, tree/shard state, and
  queryable entries;
- a retained Cosign bundle still verifies against the restored trust material;
- backups are access controlled and encrypted according to an operator-approved
  key-management plan; and
- restoring cannot overwrite the live database or volumes.

Define backup frequency, retention, ownership, alerting, and recovery-time
target before enabling writes. Redis, if deployed, may be rebuilt and is not a
substitute for database or Merkle-state backup.

## OpenBao Transit model

OpenBao is a separate private control plane, not a sidecar credential store.
Its Transit listener must bind privately, use TLS and operator-approved
authentication, and have audit logging enabled. Choose and document an auth
method that issues short-lived, workload-specific credentials; do not use a
shared root token, user token, or a token embedded in source, CI logs, image
layers, or fixtures.

Create distinct policies and identities:

| Identity | Permitted action | Explicitly denied / not granted |
| --- | --- | --- |
| daily release signer | sign only with the named Transit key; read only the minimum key metadata required by the Cosign integration | key export, key administration, key deletion, arbitrary Transit operations |
| verification service / auditor | verify and read the public/key-version metadata needed to identify signatures | sign, key export, rotation, policy administration |
| OpenBao operator break-glass role | operator-approved administration under audited procedure | routine pipeline use |

Use a dedicated Transit key namespace/name for DataPulse daily artifacts. The
future implementation must confirm the precise Cosign `openbao://` URI grammar,
algorithm support, and policy paths from the chosen Cosign/OpenBao versions;
this brief intentionally does not guess them. The integration boundary is:

```text
Cosign signing/verification invocation ↔ openbao:// Transit URI ↔ private OpenBao Transit API
```

Cosign receives only the KMS reference and short-lived authority needed to ask
Transit to sign. It must never receive an exported private key. Rekor receives
only the selected signed artifact/bundle submission permitted by the private
deployment; do not include unnecessary raw national-data payloads, operational
credentials, or user identity metadata.

Adopt a written key-version policy before activation: an active key version is
recorded with each bundle; verify retained bundles against their recorded
versions; rotate only by an explicit operator-approved change; retain older
verification capability for the retention window; and test rollback before
disabling an old version. This design performs no rotation, import, export, or
generation.

## Dual-publish transition and rollback

1. Keep `scripts/gen_attestations.py` and `mcp/server.py` behavior unchanged.
2. In a separately approved implementation, publish the existing dated
   Ed25519 envelope and a Cosign-compatible bundle for the same canonical daily
   digest.
3. Verify each backend independently. A digest mismatch, absent bundle fields,
   missing Rekor inclusion evidence, unknown log identity, or unavailable
   Sigstore verifier is a failed Sigstore result — never a successful result.
4. Preserve the current L1 and optional L2 Git-tag meaning and response shape.
   New Sigstore output must be additive and identify its backend and coverage;
   it must not redefine existing levels.
5. Cut over only after the operator approves a measured transition window in
   which both backends agree on the artifact digest and the legacy path remains
   valid.

Rollback is always available during the transition: stop publishing or
consuming the new bundle path, retain all generated legacy envelopes and chain
indexes, and serve Ed25519/Git-tag verification unchanged. Do not delete Rekor
records, KMS key versions, bundles, legacy keys, or chain artifacts as part of
rollback. A Rekor or OpenBao outage must fail the new path closed, report that
the new backend is unavailable, and leave an already-established Ed25519 result
intact; it must not silently retry into success, downgrade an existing legacy
verification, or manufacture inclusion evidence.

## Explicit future approval gates

The following require separate, literal operator authorization after this brief
is reviewed:

1. **Infrastructure design gate:** approved topology, private binding, port,
   dedicated database, volumes, resource limits, backup plan, and restore test
   plan following read-only host inventory.
2. **Key-material gate:** generate or import a Transit key, create Transit
   policies/auth roles, issue credentials, or distribute public verification
   material.
3. **Integration gate:** install/use the real Cosign integration, add signing
   or verification code, and validate a bundle in an isolated environment.
4. **Write gate:** make the first Rekor submission or production signature.
5. **Cutover gate:** expose or prefer Sigstore verification to consumers after
   dual-publish evidence and rollback rehearsal are accepted.

Until each relevant gate is explicitly approved, the required behavior is no
key generation, no KMS provisioning, no signing, no Rekor writes, and no
production service/container/port/database/volume change.

## Review and acceptance checklist

- [ ] Self-hosted Rekor, Trillian, dedicated MySQL-compatible database, and
  optional Redis are independently scoped.
- [ ] First binding is tailnet/private only; no existing public route, port,
  database, or volume is reused without later explicit approval.
- [ ] Dedicated backup and isolated restore test preserve Merkle tree/shard
  persistence and log identity.
- [ ] OpenBao listener, auth, audited signer-only policy, and read-only
  verifier policy are reviewed.
- [ ] Key-version retention and rotation/rollback policy is approved without
  performing a rotation.
- [ ] Cosign `openbao://` integration is validated against real-version docs in
  a non-production environment.
- [ ] Dual-published paths name the same canonical digest; malformed/missing
  inclusion evidence fails closed.
- [ ] Ed25519/Git-tag verification remains functional and rollbackable.
- [ ] No public Sigstore dependency, secret, generated artifact, or production
  infrastructure mutation is introduced by this design dispatch.
