# Buyer API reference

The buyer API is separate from the public, unauthenticated MCP endpoint. It is
available at <!-- BEGIN buyer-api-host -->
`https://api.data-pulse.my/api/v1/`
<!-- END buyer-api-host --> and serves the
same published health artifacts with authenticated operational policy.

## Authentication and limits

Pass a currently active token on every request:

<!-- BEGIN buyer-api-quickstart -->
```sh
curl -H "X-API-Key: $DATAPULSE_API_KEY" https://api.data-pulse.my/api/v1/health
```
<!-- END buyer-api-quickstart -->

Keys are issued by `python3 scripts/api_keys.py add --label acme-prod --scope datasets.read,deltas.read`.
Only SHA-256 hashes are persisted. Free API keys are limited to 100 requests per
key in each 60-second window (configured by `DATAPULSE_API_RATE_LIMIT`, capped at 1000).
`429` responses include `Retry-After` and `error.retry_after_s`.

<!-- BEGIN buyer-api-limits -->
List endpoints default `limit` to 50 and cap it at 1000. `cursor` defaults to `0`; dataset history `days` defaults to 30 and caps at 3650.
<!-- END buyer-api-limits -->

All errors have this stable envelope:

```json
{"error":{"code":"unauthorized","message":"A valid X-API-Key is required"}}
```

Possible status codes are `401` (missing/invalid key), `404` (unknown resource),
`429` (rate limited), and `503` (a local generated artifact is unavailable).

## Endpoints

<!-- BEGIN buyer-api-endpoints -->
| Endpoint | Description |
| --- | --- |
| `GET /api/v1/health` | health route. |
| `GET /api/v1/datasets?limit=…&cursor=…` | datasets route. |
| `GET /api/v1/datasets/{id}` | datasets route. |
| `GET /api/v1/datasets/{id}/history?days=…&limit=…&cursor=…` | dataset history route. |
| `GET /api/v1/deltas?from=…&to=…&limit=…&cursor=…` | deltas route. |
| `GET /api/v1/deltas/{cycle}` | deltas route. |
| `GET /api/v1/snapshot` | snapshot route. |
<!-- END buyer-api-endpoints -->

<!-- BEGIN buyer-api-pagination -->
List responses use `{"data": [...], "pagination": {"limit": 50, "next_cursor": "50", "total": 418}}`; `next_cursor` is `null` at the end.
<!-- END buyer-api-pagination -->
All successful calls, failed authentication attempts, and rate-limit responses
are append-only audit records with key label/hash, client IP, user agent, path,
status and latency.

## Commercial NPRA access

DataPulse does not operate commercial NPRA access, payments, entitlements, or
buyer-proxy routes. That commercial control plane belongs to Malaysia Data
Engine. This API remains a read-only interface to DataPulse public dataset,
health, history, delta, and snapshot artifacts.
