# Production OpenBao/Rekor infrastructure gate — 2026-08-22

Status: design approval artifact only. No production infrastructure, key, credential, service, port, volume, firewall, or backup mutation performed.

## Gate result

Read-only inventory completed at 2026-08-22T14:46:15+08:00.

- CPUs: 6
- RAM: 11 GiB
- free disk: 27 GiB
- existing PostgreSQL listeners: `127.0.0.1:5432`, `0.0.0.0:54329`
- disposable lab listeners: `127.0.0.1:9300` Rekor, `127.0.0.1:9820` OpenBao
- existing public/tailnet listeners include 22, 443, 3000, 3002, 8000, 8791, 9102, 9377
- `age`: installed
- `restic`: not installed
- `bao`: not installed
- `/home/redza/backups`: writable by `redza`
- `/home/redza/runtime`: root-owned; not a production data target for an unprivileged setup

The disposable lab must remain separate from production. Its ports, Docker volumes, root token, memory signer, and database are not production assets.

## Provisional production topology

Use a dedicated Docker Compose project or equivalent system-managed boundary with no public route:

```text
127.0.0.1:9830  OpenBao TLS listener
127.0.0.1:9302  private Rekor API
127.0.0.1:9303  consistency adapter

internal-only network:
  Rekor → Trillian log server + signer
  Rekor/Trillian → dedicated MySQL-compatible database
  optional Redis retrieval index
```

These ports are **provisional design values**, not authorization to bind or expose them. Re-run a port check immediately before provisioning and abort on collision.

Why loopback first:

- the initial signer runs on the same VPS;
- bundles carry the evidence needed for offline verification;
- no public ingestion endpoint is required;
- Tailscale exposure can be added later as a separate access-boundary decision.

## Persistent storage boundary

Use named production paths, not disposable Docker volume IDs:

```text
/var/lib/datapulse-openbao/       OpenBao data/config state
/var/lib/datapulse-rekor/mysql/   Rekor/Trillian database state
/var/lib/datapulse-rekor/tree/    Trillian/Merkle state if separately persisted
/var/lib/datapulse-rekor/attestations/  Rekor attestation storage
/home/redza/backups/datapulse-rekor/    encrypted backup artifacts
/home/redza/backups/datapulse-openbao/  encrypted OpenBao backup artifacts
```

Root-owned directory creation and permissions require a separate sudo-authorized operation. Do not create these paths from the unprivileged design session.

Initial capacity policy:

- reserve an explicit disk budget before provisioning;
- retain at least 10 GiB free host headroom;
- measure daily Rekor database/tree growth from the lab-shaped fixture before selecting retention;
- alert before 70% of the approved budget, fail closed before storage exhaustion;
- never prune or delete Merkle state to recover space without an operator-approved retention procedure.

The current 27 GiB free space is enough for a bounded initial stack only if retention and backup budgets are explicitly capped. It is not enough to justify unbounded national-data retention on this host.

## OpenBao production configuration boundary

- TLS listener, private bind only;
- AppRole auth for the health signer;
- response-wrapped, short-lived SecretID delivery;
- signer policy: sign/read only for the named ECDSA P-256 Transit key;
- verifier policy: public metadata/verification only;
- break-glass operator policy: separate and audited;
- no root token in service configuration;
- no private key export;
- audit enabled before signer activation;
- at least two audit destinations or an explicitly approved single-sink exception;
- no routine `log_raw` audit mode.

OpenBao documents AppRole for machine authentication with constrained roles and response wrapping.[12] Transit supports ECDSA P-256 and ACL-controlled signing/verification.[7][14] OpenBao recommends multiple audit devices because audit failure can block requests.[13]

## Backup and restore boundary

Use `age` for encrypted backup artifacts because it is already installed and is the existing operator backup primitive. Do not install `restic` as part of this gate.

Backup set:

- OpenBao persistent data/configuration;
- OpenBao audit logs according to retention policy;
- Rekor/Trillian MySQL-compatible database;
- Trillian Merkle/tree/shard state;
- Rekor configuration and component-version manifest;
- private trusted-root JSON and its fingerprint;
- one retained verified Cosign bundle fixture.

Restore test:

1. restore to isolated paths, never live paths;
2. verify OpenBao health and key metadata without printing secrets;
3. verify Rekor log identity/tree state and retrieve a retained entry;
4. verify the retained bundle with the restored private trusted root;
5. record restore duration and operator steps;
6. destroy only the isolated restore copy after verification, with explicit approval.

No backup or restore command is authorized by this design artifact.

## Trust-root distribution

Initial mode: operator-controlled versioned `trusted-root.json` containing the private Rekor public key, URL, hash algorithm, log ID, validity window, and origin metadata. Cosign supports custom trusted roots with `cosign trusted-root create` and `--trusted-root`.[6]

Store the trust root separately from secrets but protect its integrity:

- version it with the deployment manifest;
- record its SHA-256 fingerprint in the verification policy;
- retain the exact version used by each bundle verifier;
- fail closed on unknown log identity or changed key;
- do not put OpenBao SecretIDs, tokens, private keys, or database credentials in it.

TUF remains deferred until a dedicated trust-root update service is justified.

## Approval gates remaining

This infrastructure gate produces a provisional topology, not deployment authorization. Remaining literal approvals:

1. approve the provisional production ports and loopback binding;
2. approve root-owned path creation and permissions;
3. approve the backup/restore procedure and disk budget;
4. approve TLS certificate issuance/renewal path;
5. approve OpenBao provisioning and AppRole policy configuration;
6. separately authorize production key generation/import;
7. separately authorize the first production signing and Rekor write.

## Sources

[6] https://docs.sigstore.dev/cosign/system_config/custom_components — Cosign custom components and trusted roots
[7] https://openbao.org/docs/secrets/transit — OpenBao Transit
[12] https://openbao.org/docs/auth/approle — OpenBao AppRole
[13] https://openbao.org/docs/audit — OpenBao audit devices
[14] https://openbao.org/docs/concepts/policies — OpenBao ACL policies
