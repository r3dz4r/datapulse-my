# MCP deployment

## Endpoint status

<!-- BEGIN mcp-tools -->
The stable public endpoint is live at `https://mcp.data-pulse.my/mcp`. It has
been verified end to end: `tools/list` returns 16 tools over the 389-dataset
catalogue.

The current read-only contract is `search_datasets`, `get_dataset`, `find_stale`, `find_anomalies`, `find_deteriorating`, `find_recovering`, `find_unreliable`, `find_schema_drift`, `check_reconciliation`, `get_provenance`, `get_evidence`, `verify_evidence`, `trust_verdict`, `verify_attestation`, `find_by_licence`, `usage_summary`; it also publishes the concrete resources
<!-- END mcp-tools -->

The durable services currently terminate at nginx on
`https://127.0.0.1:8443/mcp`. The MCP process itself is reachable only from the
VPS at `http://127.0.0.1:8788/mcp`.

Connect from Claude Desktop with:

```json
{
  "mcpServers": {
    "datapulse-my": {
      "transport": "streamable-http",
      "url": "https://mcp.data-pulse.my/mcp"
    }
  }
}
```

## Services

The MCP server runs as the enabled user service `datapulse-mcp.service`.
User lingering is enabled, so it survives logout and starts during boot.

```bash
systemctl --user status datapulse-mcp.service
systemctl --user restart datapulse-mcp.service
journalctl --user -u datapulse-mcp.service -n 100 --no-pager
```

The deployed application and virtual environment live under
`/home/redza/.local/share/datapulse-mcp`. The source service unit is
`deploy/systemd/datapulse-mcp.service`.

nginx runs as the system service `nginx.service`. Its DataPulse configuration
is installed at `/etc/nginx/sites-available/datapulse-mcp` and
`/etc/nginx/sites-enabled/datapulse-mcp`; the source is
`deploy/nginx/datapulse-mcp.conf`.

```bash
systemctl is-active nginx
sudo systemctl restart nginx
```

nginx listens only on `127.0.0.1:8443`, rejects unapproved non-empty Origin
headers, limits each client IP to an average of 60 requests per minute with a
20-request burst, and returns HTTP 429 when the burst is exhausted. The current
origin certificate protects the loopback hop between the tunnel and nginx;
public TLS terminates at the Cloudflare edge.

## Verification

FastMCP requires an initialized MCP session. A bare `tools/list` request returns
HTTP 400 by design. This protocol-valid check lists the tools through nginx:

```bash
verify_dir=$(mktemp -d /tmp/datapulse-mcp-verify.XXXXXX)
endpoint=https://mcp.data-pulse.my/mcp

curl -sS -D "$verify_dir/headers" -o "$verify_dir/initialize" \
  "$endpoint" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"verify","version":"0"}},"id":1}'

session_id=$(awk 'tolower($1)=="mcp-session-id:" {gsub("\\r", "", $2); print $2}' \
  "$verify_dir/headers")

curl -sS "$endpoint" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H "Mcp-Session-Id: $session_id" \
  -d '{"jsonrpc":"2.0","method":"notifications/initialized"}' >/dev/null

curl -sS "$endpoint" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H "Mcp-Session-Id: $session_id" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":2}' \
  | sed -n 's/^data: //p' \
  | jq '.result.tools | length'
```

The expected output is `15`.

`verify_evidence` serializes outbound checks behind one process-local lock and
caches results for 10 minutes. It refuses browser-dependent datasets and unsafe
URLs; results are ephemeral and do not update health artifacts.

## Live verification

Run before merging any change that touches the manifest, probe policy, or MCP
source. The live `datapulse://index` resource is the catalogue returned by the
MCP server, so its array length must equal the current manifest length.

```bash
verify_dir=$(mktemp -d /tmp/datapulse-mcp-live.XXXXXX)
endpoint=https://mcp.data-pulse.my/mcp

curl -sS -D "$verify_dir/headers" -o "$verify_dir/initialize" \
  "$endpoint" \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"live-count-gate","version":"1"}}}'

session_id=$(awk 'tolower($1)=="mcp-session-id:" {gsub("\\r", "", $2); print $2}' \
  "$verify_dir/headers")

curl -sS "$endpoint" \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Content-Type: application/json' \
  -H "Mcp-Session-Id: $session_id" \
  -d '{"jsonrpc":"2.0","method":"notifications/initialized"}' >/dev/null

live_count=$(curl -sS "$endpoint" \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Content-Type: application/json' \
  -H "Mcp-Session-Id: $session_id" \
  -d '{"jsonrpc":"2.0","id":2,"method":"resources/read","params":{"uri":"datapulse://index"}}' \
  | sed -n 's/^data: //p' \
  | jq -r '.result.contents[0].text | fromjson | length')
head_count=$(jq '.datasets | length' datapulse.json)

printf 'live=%s head=%s\n' "$live_count" "$head_count"
test "$live_count" -eq "$head_count"
```

The expected count at this revision is `335`. If the assertion fails, do not
merge: the MCP server is stale and the manifest-count claim is false.

## Source-to-deployment sync

Each release-build invocation stamps the current commit SHA into the
MCP source so the deployed service can introspect its source-of-truth:

- `mcp/server.py` exposes `SOURCE_COMMIT_SHA` and `SOURCE_COMMIT_DATE` module
  constants, returned in the JSON-RPC `initialize` response's
  `serverInfo.source_commit_sha` and `serverInfo.source_commit_date` fields.
- `mcp.json` discovery doc has `server.source_commit_sha` and
  `server.source_commit_date` fields, kept in sync by the same bump.
- `scripts/bump_mcp_source_version.py` is the first step of the
  `release-build` profile; it reads `git rev-parse HEAD` and stamps both
  files.
- `scripts/verify_mcp_deployment.py` compares the deployed service's
  `source_commit_sha` to the current repo HEAD. Exit 0 if they match,
  exit 1 on mismatch, exit 2 if the endpoint is unreachable.

The five-minute health pipeline deploys MCP source automatically. It archives
`origin/main` into a frozen `/tmp/datapulse-run.*` directory, probes and
validates that snapshot, publishes any changed health artifacts, and then runs
the non-fatal `mcp-sync` stage with the frozen
`$run_dir/mcp/server.py`. The live working tree is never used as the MCP deploy
source.

`scripts/sync_mcp_deployment.sh` performs the deployment transaction:

1. Compare SHA-256 hashes of the frozen source and
   `/home/redza/.local/share/datapulse-mcp/server.py`.
2. If either the source or source-marker systemd configuration differs, create
   a timestamped `.bak`, copy through a same-directory temporary file, and
   atomically replace the deployed copy.
3. Install `99-source-marker.conf`, whose `UnsetEnvironment=` removes legacy
   `DATAPULSE_MCP_SOURCE_SHA` and `DATAPULSE_MCP_SOURCE_DATE` overrides. The
   marker embedded by `release-build` is authoritative.
4. Export `XDG_RUNTIME_DIR=/run/user/$(id -u)`, reload the user manager when its
   drop-in changed, and restart `datapulse-mcp.service`.
5. Use `curl` against `http://127.0.0.1:8788/mcp` to initialize an MCP session,
   confirm the live source SHA, list the tools, and assert that every tool has
   the complete read-only annotations. A failed restart or verification rolls
   back the deployed copy and drop-in, then returns non-zero.

The explicit runtime directory is required for the system-service context. A
process with the health unit's stripped environment cannot connect to the user
bus (`systemctl --user` reports `Failed to connect to bus: No medium found`).
With `XDG_RUNTIME_DIR=/run/user/1001`, the same command reaches the lingering
user manager and restarts the service. The sync script derives `1001` with
`id -u`; it does not hard-code the UID.

The pipeline records `mcp-sync` telemetry as `success` with result
`no-change` or `deployed`. A sync error is recorded as `fail` with
`non_fatal=true`, logged with the `datapulse-mcp:` prefix, and does not stop the
health cycle or publication.

To run the normal sync or the independent read-only HEAD check:

```bash
scripts/sync_mcp_deployment.sh --source mcp/server.py
python3 scripts/verify_mcp_deployment.py
```

The Python check is read-only and uses the JSON-RPC handshake already
documented above. MCP deployment no longer requires a manual `cp` followed by
`systemctl --user restart`.

### Manual idempotency and change verification

Run the production source twice. The first invocation deploys only if needed;
the second must log `datapulse-mcp: no change` and leave the service PID
unchanged:

```bash
scripts/sync_mcp_deployment.sh --source mcp/server.py
pid_before=$(systemctl --user show datapulse-mcp.service -p MainPID --value)
scripts/sync_mcp_deployment.sh --source mcp/server.py
pid_after=$(systemctl --user show datapulse-mcp.service -p MainPID --value)
test "$pid_before" = "$pid_after"
```

For a reversible change-deploy test, make a temporary source whose embedded
marker is a known 40-character value, deploy it, and read the marker back from
the live endpoint. The sync command does the endpoint check with `curl` and
logs the verified marker; the Python one-liner below independently reads the
same live handshake. Always restore the production source afterward:

```bash
test_dir=$(mktemp -d /tmp/datapulse-mcp-marker-test.XXXXXX)
test_sha=eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee
cp mcp/server.py "$test_dir/server.py"
current_sha=$(sed -n -E \
  's/^SOURCE_COMMIT_SHA = os.getenv\("DATAPULSE_MCP_SOURCE_SHA", "([^"]+)"\)$/\1/p' \
  "$test_dir/server.py")
test -n "$current_sha"
sed -i "s/$current_sha/$test_sha/" "$test_dir/server.py"
scripts/sync_mcp_deployment.sh --source "$test_dir/server.py"
python3 -c 'from scripts.verify_mcp_deployment import deployed_source_sha; print(deployed_source_sha("http://127.0.0.1:8788/mcp"))'
scripts/sync_mcp_deployment.sh --source mcp/server.py
```

## Named Cloudflare Tunnel

Cloudflared 2026.7.3 is installed. The named tunnel routes
`mcp.data-pulse.my` to the localhost nginx TLS listener, and the ingress returns
404 for every other route. The repository template is
`deploy/cloudflared/config.yml.example`; the deployed configuration lives at
`/home/redza/.cloudflared/config.yml`.

## Limitations

- The service is single-region on one VPS.
- There is intentionally no authentication: all advertised tools are read-only over
  already-public data and have no write side effects or PII access.
- Origin validation and rate limiting are enforced by nginx, so bypassing nginx
  is unsupported.
