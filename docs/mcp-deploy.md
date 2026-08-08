# MCP deployment

## Endpoint status

The stable public endpoint is live at `https://mcp.data-pulse.my/mcp`. It has
been verified end to end: `tools/list` returns 5 tools over the 166-dataset
catalogue.

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

The expected output is `5`.

## Named Cloudflare Tunnel

Cloudflared 2026.7.3 is installed. The named tunnel routes
`mcp.data-pulse.my` to the localhost nginx TLS listener, and the ingress returns
404 for every other route. The repository template is
`deploy/cloudflared/config.yml.example`; the deployed configuration lives at
`/home/redza/.cloudflared/config.yml`.

## Limitations

- The service is single-region on one VPS.
- There is intentionally no authentication: all five tools are read-only over
  already-public data and have no write side effects or PII access.
- Origin validation and rate limiting are enforced by nginx, so bypassing nginx
  is unsupported.
