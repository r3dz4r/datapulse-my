# Buyer API reference

The buyer API is separate from the public, unauthenticated MCP endpoint. It is
available at `https://api.data-pulse.my/api/v1/` and serves the
same published health artifacts with authenticated operational policy.

## Authentication and limits

Pass a currently active token on every request:

```sh
curl -H "X-API-Key: $DATAPULSE_API_KEY" https://api.datapulse-my.my/api/v1/health
```

Keys are issued by `python3 scripts/api_keys.py add --label acme-prod --scope datasets.read,deltas.read`.
Only SHA-256 hashes are persisted. Free API keys are limited to 100 requests per
key in each 60-second window (configured by `DATAPULSE_API_RATE_LIMIT`, capped at 1000).
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

## NPRA Pro

NPRA Pro is USD 25 per month with 100,000 queries for each Paddle billing
period. Its allowance is separate from the free-key 60-second policy. Checkout is sandbox-only and the browser
uses the public Paddle client token and creates a high-entropy nonce at checkout.
That nonce is the short-lived, single-use redemption token: it is sent as Paddle
custom data and submitted to redeem only after checkout completion. The signed
webhook stores only its hash and never returns it. Never put an API key or nonce
in a URL or browser storage.

Customers pay once and keep the checkout tab open while the signed
`transaction.completed` webhook is confirmed. The browser retries confirmation
of that same nonce for up to 15 minutes. If activation remains pending, use
**Retry activation**; it reuses the same redemption nonce and does not open
another checkout. A `201` key is verified through `/keys/me` as `tier: pro`,
`status: active`, with the `npra.read` scope before it becomes active. Never pay
again while activation is pending or has failed: retain your receipt and contact
the operator privately.

| Endpoint | Description |
| --- | --- |
| `POST /api/v1/paddle/webhook` | Paddle-signed lifecycle webhook; no browser provisioning. |
| `POST /api/v1/paddle/redeem` | Exchanges the checkout nonce (the single-use redemption token) for a newly issued key. |
| `GET /api/v1/keys/me` | Pro tier, status, scopes, quota remaining and reset timestamp. |
| `GET /api/v1/npra/health` | NPRA engine health (active Pro, `npra.read`). |
| `GET /api/v1/npra/changes` | NPRA changes (active Pro, `npra.read`). |
| `GET /api/v1/npra/product/{id}` | NPRA product lookup. |
| `GET /api/v1/npra/manufacturer/{id}` | NPRA manufacturer lookup. |
| `GET /api/v1/npra/importer/{id}` | NPRA importer lookup. |

NPRA dispatches are charged atomically. Transport, oversized, malformed or
non-JSON upstream responses, and upstream 5xx failures are refunded. An
upstream 4xx response is returned to the caller and remains billable; a depleted
billing period returns `403` with `quota_exhausted`.
