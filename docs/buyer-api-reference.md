# Buyer API reference

The buyer API is separate from the public, unauthenticated MCP endpoint. It is
available through the private Tailscale frontend at `/api/v1/` and serves the
same published health artifacts with authenticated operational policy.

## Authentication and limits

Pass a currently active token on every request:

```sh
curl -H "X-API-Key: $DATAPULSE_API_KEY" https://api.datapulse-my.my/api/v1/health
```

Keys are issued by `python3 scripts/api_keys.py add --label acme-prod --scope datasets.read,deltas.read`.
Only SHA-256 hashes are persisted. The default limit is 100 requests per key per
60-second window (configured by `DATAPULSE_API_RATE_LIMIT`, capped at 1000).
`429` responses include `Retry-After` and `error.retry_after_s`.

All errors have this stable envelope:

```json
{"error":{"code":"unauthorized","message":"A valid X-API-Key is required"}}
```

Possible status codes are `401` (missing/invalid key), `404` (unknown resource),
`429` (rate limited), and `503` (a local generated artifact is unavailable).

## Endpoints

| Endpoint | Description |
| --- | --- |
| `GET /api/v1/health` | Service status and source health-cycle timestamp. |
| `GET /api/v1/datasets?limit=50&cursor=0` | Paginated rows from `health/latest.json`. |
| `GET /api/v1/datasets/{id}` | One current health row. |
| `GET /api/v1/datasets/{id}/history?days=30&limit=50&cursor=0` | Paginated history rows in the requested trailing window. |
| `GET /api/v1/deltas?from=YYYY-MM-DD&to=YYYY-MM-DD&limit=50&cursor=0` | Paginated available delta cycles. |
| `GET /api/v1/deltas/{cycle}` | Full delta artifact, for example `2026-08-12T19:00`. |
| `GET /api/v1/snapshot` | Current `catalog-snapshot.json`. |

List responses use `{"data": [...], "pagination": {"limit": 50,
"next_cursor": "50", "total": 375}}`; `next_cursor` is `null` at the end.
All successful calls, failed authentication attempts, and rate-limit responses
are append-only audit records with key label/hash, client IP, user agent, path,
status and latency.
