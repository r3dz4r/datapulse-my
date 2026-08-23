# Production OpenBao signer and private trusted-root design — 2026-08-22

Status: design only; no production provisioning, key generation, signing, Rekor write, service restart, or port change performed.

## Decision

Use a production OpenBao Transit boundary as the operator-controlled signing service for the new Cosign path. Keep the existing Ed25519/Git-tag path as compatibility until a measured dual-publish window completes.

Recommended signing algorithm for the Cosign path: ECDSA P-256. It passed the real disposable OpenBao/Cosign/Rekor integration test; Ed25519 remains the legacy DataPulse envelope algorithm.

## Current host constraints

The read-only inventory at design time shows:

- 6 CPUs;
- 11 GiB RAM;
- 27 GiB free disk;
- occupied database ports `127.0.0.1:5432` and `0.0.0.0:54329`;
- disposable lab ports `127.0.0.1:9300` and `127.0.0.1:9820`;
- no production OpenBao or Rekor service exists;
- no public route is approved.

The disposable lab ports and volumes must not be promoted to production by assumption.

## Production topology

```text
DataPulse health/release signer
  ├── private authenticated request
  ▼
OpenBao Transit — private TLS listener
  ├── AppRole authentication
  ├── signer-only ACL
  ├── audited requests/responses
  └── dedicated persistent storage + encrypted backup

Cosign bundle
  ├── ECDSA P-256 public verification material
  ├── private Rekor URL/log identity
  └── private trusted-root reference/fingerprint

private Rekor adapter
  └── self-hosted Rekor → Trillian → dedicated MySQL-compatible storage
```

Do not reuse Honcho PostgreSQL, NPRA PostgreSQL, existing Redis, the disposable lab database, or an existing listener. Select production ports only after a fresh pre-deployment inventory and explicit approval.

## Authentication recommendation

Use AppRole for the non-Kubernetes health signer. OpenBao documents AppRole as a machine/application authentication method with role constraints, SecretID TTLs, usage limits, CIDR restrictions, and response-wrapped SecretID delivery.[12]

Recommended shape:

- fixed RoleID stored as non-secret deployment metadata;
- SecretID delivered through a response-wrapped, short-lived bootstrap path;
- SecretID TTL and use limit bounded to the signer bootstrap/renewal procedure;
- token TTL short and renewable only within an explicit maximum;
- token bound to the local signer identity/CIDR where practical;
- no root token, shared operator token, long-lived static token, or token in source/image/logs;
- credential delivery through a protected runtime credential mechanism, not a repository file.

The exact credential-delivery mechanism remains an implementation decision and must be tested without printing the RoleID/SecretID/token.

## ACL boundary

Create three separate policy classes:

### `datapulse-daily-signer`

Allow only:

- sign using the named Transit key `datapulse-cosign`;
- read the minimum public/key-version metadata required by Cosign;
- authenticate and renew its own short-lived token if required.

Deny explicitly:

- key creation, rotation, deletion, export, backup, restore, import;
- arbitrary Transit paths;
- policy/auth/audit administration;
- raw storage access;
- Rekor administration.

OpenBao policies are the authorization layer between authenticated machines and paths; deny must win over broader capabilities.[14]

### `datapulse-verifier`

Allow only:

- read public/key-version metadata;
- verify operations if the selected verifier requires OpenBao online verification.

No sign, key administration, export, policy, auth, or audit access.

### `datapulse-break-glass`

Operator-only administration, audited and time-bounded. Do not attach it to the health service.

OpenBao Transit supports signing/verification, ECDSA P-256, key versioning, and ACL-restricted operations; it does not store the submitted plaintext data.[7]

## TLS and listener boundary

Production OpenBao must use TLS and bind privately. The approved default is loopback-only if the signer and OpenBao share the host; otherwise use a Tailscale-only listener with an operator-approved certificate and explicit client access boundary.

Do not expose OpenBao through Cloudflare, public DNS, the public MCP hostname, or an unauthenticated listener.

The production TLS certificate, SANs, renewal path, and trust distribution require a separate read-only inventory and approval. No certificate generation or installation is authorized by this design.

## Audit boundary

Enable audit logging before signer activation. OpenBao audit devices record API requests and responses; sensitive strings are generally HMAC-obfuscated by default.[13]

Recommended minimum:

1. local append-only audit sink on dedicated storage;
2. independent second sink or controlled remote collector;
3. retention and backup policy separate from the Rekor database;
4. no `log_raw` mode for routine operation;
5. alert on audit sink failure, because OpenBao can block requests when no audit device can record them.

The second sink implementation is not selected yet; it must not be invented during deployment.

## Transit key policy

Production key name: reserved namespace only; do not create it yet.

Required key properties after explicit approval:

- ECDSA P-256;
- non-exportable where supported;
- deletion disabled unless break-glass procedure explicitly permits it;
- key version recorded with every bundle;
- old versions retained for verification during the evidence retention window;
- rotation tested in a restored lab before production rotation;
- no key generation/import/rotation during this design stage.

OpenBao documentation notes that Transit can generate and manage keys internally and supports key import for external/HSM cases; internal generation is the preferred security posture unless an approved HSM/KMS requirement supersedes it.[7]

## Private trusted root

Initial production approach: manually assembled Cosign trusted-root JSON containing only the private Rekor log public key and URL, versioned and distributed as operator-controlled verification material. Cosign supports `cosign trusted-root create` and `--trusted-root` for custom components.[6]

Required properties:

- no private key or SecretID in the trusted root;
- include Rekor base URL, public key, hash algorithm, log ID, validity start, and origin metadata;
- record a SHA-256 fingerprint of the trusted-root file;
- retain the exact trusted-root version used for every verification result;
- distribute it through a protected versioned configuration path;
- verify bundle log identity against the trusted root before accepting inclusion;
- fail closed on unknown log identity or changed public key.

TUF distribution is deferred until the operator is willing to operate a separate trust-root update service. Manual trusted-root distribution is acceptable for the first controlled migration window but is not a substitute for a long-term update process.

## Fresh artifact and dual-publish boundary

The current health service cannot generate a fresh Ed25519 chain head because the existing private-key path is GitHub Actions-only. Do not copy that key to the VPS.

Before dual-publish implementation:

1. define the canonical daily artifact produced in the frozen health cycle;
2. migrate or explicitly replace the existing Ed25519 signer boundary;
3. make both legacy and Cosign paths reference the same digest;
4. publish the legacy envelope and Cosign bundle additively;
5. retain backend-specific verification fields;
6. fail the new path closed without invalidating a valid legacy result.

## Backup and recovery gates

Before any production signing or Rekor write:

- back up OpenBao persistent state and configuration;
- back up Rekor/Trillian database and Merkle state;
- encrypt backups under an operator-approved backup key;
- restore into isolated volumes, never live volumes;
- verify the trusted-root fingerprint, key metadata, Rekor log identity, and an existing bundle after restore;
- document recovery order and rollback point.

## Explicit approval gates

1. Infrastructure gate: approve production topology, listener, ports, volumes, storage, TLS, audit sinks, backup paths, and resource limits.
2. Key-material gate: approve OpenBao provisioning, Transit policy, auth method, and key generation/import.
3. Signing gate: approve the first non-production signer invocation using the production-shaped auth path.
4. Rekor write gate: approve the first production/private production-log submission.
5. Cutover gate: approve consumer preference for the new Sigstore backend after dual-publish evidence and rollback rehearsal.

Until those gates are separately approved, no production mutation is authorized.

## Sources

[6] https://docs.sigstore.dev/cosign/system_config/custom_components — Cosign custom components and trusted roots
[7] https://openbao.org/docs/secrets/transit — OpenBao Transit 2.6.x
[12] https://openbao.org/docs/auth/approle — OpenBao AppRole authentication
[13] https://openbao.org/docs/audit — OpenBao audit devices
[14] https://openbao.org/docs/concepts/policies — OpenBao ACL policies
