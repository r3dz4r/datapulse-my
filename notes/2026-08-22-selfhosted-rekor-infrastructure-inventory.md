# Self-hosted Rekor/OpenBao infrastructure inventory — 2026-08-22

Status: read-only design review; no infrastructure changes performed.

## Host capacity

- Host: a single-node Ubuntu Linux VPS, x86_64.
- Capacity: low single-digit CPU cores, ~11 GiB RAM, with roughly a third of the root filesystem free at probe time. Exact figures are intentionally omitted — re-measure before deployment.

This is enough capacity for a bounded private proof-of-concept only after resource limits and backup capacity are defined. It is not evidence of production-grade HA capacity.

## Existing services and occupied boundaries

No `rekor`, `trillian`, `bao`, `vault`, or `cosign` binary/service/container is installed.

Occupied or active service boundaries observed (exact ports and bindings intentionally omitted — re-measure before deployment):

- A loopback-bound PostgreSQL for Honcho.
- A PostgreSQL listener for the Malaysia data engine, bound to all interfaces; the firewall posture protecting it is a separate verification item.
- A spread of loopback-, tailnet-, and wildcard-bound service listeners across the Honcho, headroom, Buzz, Camofox, Firecrawl and data-engine stacks, plus the usual HTTPS/SSH listeners.
- Docker already hosts multiple database, object-store, analytics, scraping and application workloads.

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
