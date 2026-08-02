# MCP deployment

## Endpoint status

The intended stable endpoint is `https://mcp.datapulse-my.my/mcp`. It is not
active yet because this VPS has no Cloudflare named-tunnel credentials and the
hostname has no configured DNS zone.

The public path was nevertheless verified end to end on 2026-08-03 through the
temporary Quick Tunnel URL
`https://howto-edgar-registrar-tel.trycloudflare.com/mcp`: `tools/list` returned
5 tools and `search_datasets` with `{"query":"labour"}` returned 4 matches.
That random hostname is verification evidence, not a service address: Quick
Tunnels have no uptime guarantee, change hostname when restarted, and are not
configured to survive a reboot.

The durable services currently terminate at nginx on
`https://127.0.0.1:8443/mcp`. The MCP process itself is reachable only from the
VPS at `http://127.0.0.1:8788/mcp`.

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
origin certificate is a local bootstrap certificate. Replace it with a
Cloudflare Origin CA certificate when the named tunnel and hostname are
provisioned.

## Verification

FastMCP requires an initialized MCP session. A bare `tools/list` request returns
HTTP 400 by design. This protocol-valid check lists the tools through nginx:

```bash
verify_dir=$(mktemp -d /tmp/datapulse-mcp-verify.XXXXXX)
endpoint=https://127.0.0.1:8443/mcp

curl -ksS -D "$verify_dir/headers" -o "$verify_dir/initialize" \
  "$endpoint" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"verify","version":"0"}},"id":1}'

session_id=$(awk 'tolower($1)=="mcp-session-id:" {gsub("\\r", "", $2); print $2}' \
  "$verify_dir/headers")

curl -ksS "$endpoint" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H "Mcp-Session-Id: $session_id" \
  -d '{"jsonrpc":"2.0","method":"notifications/initialized"}' >/dev/null

curl -ksS "$endpoint" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H "Mcp-Session-Id: $session_id" \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":2}' \
  | sed -n 's/^data: //p' \
  | jq '.result.tools | length'
```

The expected output is `5`. For the eventual public hostname, set `endpoint`
to `https://mcp.datapulse-my.my/mcp` and remove curl's `-k` option.

## Named Cloudflare Tunnel

Cloudflared 2026.7.3 is installed. Once the Cloudflare zone and named-tunnel
credentials exist, copy `deploy/cloudflared/config.yml.example` to
`/home/redza/.cloudflared/config.yml`, replace the tunnel UUID placeholders,
route `mcp.datapulse-my.my` to that tunnel, validate the ingress rules, and
install the cloudflared service. The ingress sends only that hostname to the
localhost nginx TLS listener and returns 404 for every other route.

## Limitations

- No stable public hostname is active until the named Cloudflare Tunnel and DNS
  route are provisioned.
- The service is single-region on one VPS.
- There is intentionally no authentication: all five tools are read-only over
  already-public data and have no write side effects or PII access.
- Origin validation and rate limiting are enforced by nginx, so bypassing nginx
  is unsupported.
