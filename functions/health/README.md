# DataPulse health-index Pages Function

Route: `/health/index.json`

The Pages Function reads `health-index.json` from the `DATAPULSE_HEALTH_INDEX` KV binding. A populated value is returned byte-for-byte with HTTP 200, `Content-Type: application/json`, and `Cache-Control: public, max-age=60`.

If the binding is missing, the key is absent or empty, or KV read fails, it logs a server-side reason and returns HTTP 503 with `Content-Type: application/json`, `Cache-Control: no-store`, and `{"error":"health index unavailable"}`. It does not use a fallback data source.

Run the offline local test harness with:

```bash
node --test functions/health/index.json.test.js
```
