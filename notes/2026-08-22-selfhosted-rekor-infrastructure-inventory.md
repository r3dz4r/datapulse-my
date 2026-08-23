# Self-hosted Rekor/OpenBao infrastructure inventory — 2026-08-22

Status: read-only design review; no infrastructure changes performed.

## Host capacity

- Host: Ubuntu Linux 6.8.0-138-generic, x86_64.
- CPUs: 6.
- Memory: 11 GiB total, approximately 5.1 GiB available at probe time.
- Root filesystem: 96 GiB total, 61 GiB used, 36 GiB available (64%).
- Tailnet IPv4: `100.74.84.121`.

This is enough capacity for a bounded private proof-of-concept only after resource limits and backup capacity are defined. It is not evidence of production-grade HA capacity.

## Existing services and occupied boundaries

No `rekor`, `trillian`, `bao`, `vault`, or `cosign` binary/service/container is installed.

Occupied or active service boundaries observed:

- Honcho PostgreSQL: `127.0.0.1:5432`.
- Malaysia data engine PostgreSQL: `0.0.0.0:54329`.
- Existing services/listeners: `100.74.84.121:3000`, `100.74.84.121:3002`, `127.0.0.1:8000`, `100.74.84.121:8000`, `127.0.0.1:8787`, `127.0.0.1:8788`, `127.0.0.1:8791`, `0.0.0.0:8080`, `0.0.0.0:9102`, and HTTPS/SSH listeners.
- Docker already hosts multiple PostgreSQL, Redis, MinIO, ClickHouse, Firecrawl, Buzz, Camofox, and data-engine workloads.

Do not reuse an existing database, Docker network, volume, service account, or listener without a separate review. Do not select a port from assumption; choose one after the deployment topology and private binding are approved.

## Recommended first topology

- Separate Docker Compose project or dedicated systemd-managed stack.
- Rekor API bound to loopback or tailnet only.
- Dedicated Rekor/Trillian MySQL-compatible database.
- Dedicated persistent volumes for database data, Trillian tree/shard state, Rekor configuration/state, OpenBao state, and backups.
- Redis omitted from the first proof unless retrieval/search performance requires it.
- No Cloudflare route, public DNS, public MCP hostname reuse, or public ingestion endpoint.
- OpenBao Transit private listener with TLS, audit logging, short-lived workload credential, signer-only policy, and read-only verifier policy.

## Operational constraints

- The health pipeline was actively running during this inventory; do not install or restart services during a health cycle.
- The 36 GiB free-disk figure must be rechecked immediately before deployment and paired with explicit backup-retention sizing.
- A restore test must precede the first production Rekor write.
- Merkle tree identity, Trillian shard state, OpenBao key versions, and trust-root material are durable security state and require backup/rollback procedures.
- Infrastructure freeze remains active outside this explicit self-hosted Rekor request.

## Next gate

Before any installation:

1. Approve the private binding and dedicated-stack topology.
2. Select the exact port, container names, storage roots, resource limits, and backup destination from a deployment brief.
3. Approve whether the first proof uses OpenBao-generated Ed25519 material or an imported approved key. This is a separate crypto approval.
4. Run a non-production restored-stack test.
5. Only then consider production signing or Rekor writes.
