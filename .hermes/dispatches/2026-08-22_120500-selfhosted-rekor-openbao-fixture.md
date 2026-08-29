Workdir: /home/redza/datapulse-my
Goal: Define and validate the national-data trust-boundary migration to self-hosted Rekor plus operator-controlled OpenBao Transit signing, without touching production infrastructure or cryptographic material.
Failure mode: A rushed Sigstore migration could externalize the signing boundary, expose national-data trust metadata, reuse an existing database/port unsafely, or break verification of the current Ed25519/Git-tag attestation chain.
Acceptance test: A reviewed deployment brief and deterministic fixture contract cover self-hosted Rekor dependencies, OpenBao Transit permissions, Cosign bundle mapping, dual-verification compatibility, rollback, backups, and failure behavior; fixture tests pass without contacting Rekor or generating keys; no production files, services, containers, ports, credentials, or generated artifacts change.
Recommended execution model: terra

Implementation authority: You are the designated Codex implementer for this dispatch. The repository rule requiring Hermes to dispatch Codex has already been fulfilled; it does not prohibit you from editing the explicitly scoped test/brief paths below. Do not call codex-run, codex-run-bg, delegate_task, or any other agent recursively.

## Context

Read first:

- `notes/2026-08-22-sigstore-rekor-migration-design.md`
- `scripts/gen_attestations.py`
- `mcp/server.py` around `verify_attestation`
- `mcp/tests/test_server.py` attestation fixtures
- `docs/operations.md`

Locked decision:

- self-hosted Rekor;
- Cosign-compatible bundles;
- operator-controlled signing key/KMS;
- OpenBao Transit is the recommended KMS provider;
- public Rekor, public Fulcio/OIDC/TUF are deferred.

## Scope

Allowed changes:

- add or update an internal migration brief under `notes/` or `.hermes/dispatches/`;
- add deterministic fixture-only tests under `scripts/tests/` or `mcp/tests/`;
- add test fixtures under an existing test-fixture directory.

Do not change:

- `mcp/server.py` production verification behavior;
- `scripts/gen_attestations.py` production signing behavior;
- dependency pins or install packages;
- Docker, systemd, Cloudflare, firewall, ports, volumes, databases, OpenBao, Rekor, Trillian, or Redis;
- private/public keys, KMS tokens, OIDC credentials, or secrets;
- generated health/attestation artifacts;
- public docs or deployment workflows;
- commits, pushes, service restarts, or network writes.

## Required fixture contract

Create deterministic fixtures representing:

1. current DataPulse Ed25519 envelope with chain link and Git-tag compatibility;
2. Cosign-compatible bundle metadata for the same canonical daily artifact digest;
3. dual-published artifact where both verification paths refer to the same digest;
4. digest mismatch;
5. malformed or incomplete bundle;
6. missing Rekor inclusion evidence;
7. unavailable verifier/backend, which must fail closed without deleting or invalidating the existing Ed25519 result.

The fixture tests must prove the migration contract, not pretend to perform cryptography. If the real Cosign CLI or Sigstore library is absent, do not install it and do not invent an API; test the normalized bundle/identity/digest contract and stop clearly at the real-verifier boundary.

## Deployment brief content

The internal brief must explicitly specify:

- Rekor server + Trillian + dedicated MySQL-compatible database;
- Redis as optional retrieval/search infrastructure;
- tailnet/private binding only for the first deployment;
- dedicated volumes and backup/restore test;
- Merkle tree/shard persistence and upgrade procedure;
- OpenBao Transit listener/auth/policy model;
- signer-only versus read-only verifier permissions;
- key version/rotation policy, without performing rotation;
- Cosign `openbao://` integration boundary;
- dual-publish transition and rollback to Ed25519/Git-tag verification;
- fail-closed behavior when OpenBao/Rekor is unavailable;
- explicit future gates for key generation, KMS provisioning, signing, and Rekor writes.

## Verification

Run the relevant existing test suites plus the new fixture tests. At minimum:

```bash
python3 -m pytest mcp/tests/test_server.py scripts/tests/test_attestations.py -q
python3 -m pytest scripts/tests/ -q
python3 -m py_compile scripts/gen_attestations.py scripts/check_heartbeat.py
git diff --check
```

Use a deterministic temporary fixture directory. Confirm no network writes, no production telemetry writes, no generated artifact changes, and no secret material. Return exact changed files and `Pushed: NO`.
