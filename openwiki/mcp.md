# MCP Server & Deployment

DataPulse MY exposes a **read-only Model Context Protocol (MCP) server** that lets
AI agents (Claude Desktop, Cursor, etc.) query the 122-dataset catalogue natively
without scraping or API-key setup. It is the programmatic counterpart to the
human-facing [`llms.txt`](../llms.txt) discovery index and the dashboard at
`https://r3dz4r.github.io/datapulse-my/`.

The server does not store data. At runtime it fetches the published
`datapulse.json` and `health/latest.json` from the GitHub Pages site (the same
artifacts the weekly health-check workflow produces) and serves derived views.
It never performs writes.

## Tools

Five read-only tools, implemented in [`mcp/server.py`](../mcp/server.py):

| Tool | Parameters | Returns |
| --- | --- | --- |
| `search_datasets` | `query` (required), `licence` (optional), `source` (optional), `limit` 1–50 (default 10) | Ranked list of `{id, title, source, licence, status, score}`. Title-weighted scoring: exact match +100, substring +15, term counts ×5. |
| `get_dataset` | `dataset_id` | Full manifest entry merged with the live health record, plus `last_verified` and `schema_version`. |
| `find_stale` | `max_age_hours` ≥0 (default 24) | Datasets whose status ≠ `healthy`, or missing from the health snapshot, or where the snapshot itself is older than `max_age_hours`. |
| `get_provenance` | `dataset_ids` (list, 1–50) | Citation-ready metadata: steward, source, licence (+URL), url, access_method, last_verified, schema_version. |
| `find_by_licence` | `licence` (accepts aliases such as `cc by 4.0`, `ogl`) | `{licence, count, datasets[]}` for the canonical licence. |

The manifest has no `description` field, so `search_datasets` scores titles only
until descriptions are published.

## Resources

Three resources are exposed:

- `datapulse://index` — lightweight JSON array of all 122 datasets:
  `{id, status, title, source, licence}`.
- `datapulse://licences` — JSON object mapping licence name → dataset count.
- `datapulse://{dataset_id}` — full manifest entry for one dataset (on-demand).

## Running locally

`mcp/README.md` recommends Python 3.11+ and `uv`:

```sh
uv run --with fastmcp,httpx python mcp/server.py
```

The default endpoint is `http://127.0.0.1:8788/mcp`. Configuration via
environment variables (see `mcp/.env.example`):

- `DATA_BASE` — base URL for published JSON (default
  `https://r3dz4r.github.io/datapulse-my`).
- `MCP_HOST` — bind host (default `127.0.0.1`).
- `MCP_PORT` — bind port (default `8788`).

Runtime dependencies are minimal: `fastmcp` and `httpx` (see
`mcp/requirements.txt`). The server uses `httpx.AsyncClient` with
`asyncio.gather` to fetch the manifest and health snapshot in parallel and
imposes a 30-second request timeout.

## Tests

[`mcp/tests/test_server.py`](../mcp/tests/test_server.py) uses FastMCP's
in-memory `Client` against the live published site. Cases cover ranked search
with filters, exact-vs-partial title scoring, manifest+health merge, and
`find_stale` matching live data. Run with:

```sh
uv run --with fastmcp,httpx pytest mcp/tests/ -v
```

Tests require network access to the published DataPulse MY site.

## Production deployment

The public MCP endpoint is `https://mcp.data-pulse.my/mcp`. The request path is
documented in [`docs/mcp-deploy.md`](../docs/mcp-deploy.md):

```
Cloudflare edge → cloudflared tunnel → nginx (127.0.0.1:8443, TLS)
  → MCP server (127.0.0.1:8788)
```

Components in `deploy/`:

- **`deploy/systemd/datapulse-mcp.service`** — systemd **user** service running
  `mcp/server.py` from a venv. Hardened with `NoNewPrivileges`,
  `ProtectSystem=strict`, `PrivateTmp`. User lingering is enabled so the service
  survives logout and starts at boot. Restart on failure with 5s backoff.
- **`deploy/nginx/datapulse-mcp.conf`** — nginx reverse proxy terminating TLS on
  loopback `127.0.0.1:8443` and proxying `/mcp` to the MCP server. Security
  controls: origin allowlist (only `datapulse.my`, `www.datapulse.my`,
  `r3dz4r.github.io`, or empty Origin — others get 403), rate limiting (1 req/s,
  burst 20, excess 429), `client_max_body_size 256k`, `proxy_read_timeout 3600s`
  for long-lived MCP sessions. Trusts the `CF-Connecting-IP` header from
  Cloudflare.
- **`deploy/cloudflared/config.yml.example`** — Cloudflare Tunnel template
  routing the public hostname to the local nginx TLS listener. Contains
  placeholder values (`REPLACE_WITH_TUNNEL_UUID`) that must be filled at deploy
  time.

### Verifying the live endpoint

`docs/mcp-deploy.md` includes a protocol-valid curl sequence for listing tools
through nginx. A bare `tools/list` returns HTTP 400 by design — FastMCP requires
an initialized session first (initialize → `notifications/initialized` →
`tools/list`). The expected tool count is 5.

Operational commands:

- Service: `systemctl --user status|restart datapulse-mcp`,
  `journalctl --user -u datapulse-mcp`.
- nginx: `systemctl is-active nginx`, `sudo systemctl restart nginx`.
- cloudflared version referenced in the runbook: `2026.7.3`.
