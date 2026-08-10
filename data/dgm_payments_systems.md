---
dataset_id: dgm_payments_systems
last_checked: 2026-08-10T04:08:14Z
status: stale
freshness_delta: 190 days
next_expected_update: overdue
record_count: 516
date_range: 2019-01-01 to 2026-02-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Monthly dates use 1 January.", "System codes require the official payment-system lookup.", "Value and volume use different units.", "The file contains one row per month and system."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: Bank Negara Malaysia via data.gov.my
---

# data.gov.my Monthly Payment Systems

## Status

**Status:** Stale

**Freshness:** 190 days

HTTP 200

## Last checked

2026-08-10 at 04:08:14 UTC.

## File size

The checked resource is 23,190 bytes.

## Provenance

Bank Negara Malaysia publishes this dataset through data.gov.my as direct CSV
and Parquet downloads:

- `https://storage.data.gov.my/finsector/payments/systems.csv`
- `https://storage.data.gov.my/finsector/payments/systems.parquet`

## Coverage

The dataset covers six Malaysian payment systems from 2019-01-01 through
2026-02-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `date` | date | Monthly observation date in YYYY-MM-DD format. |
| `system` | string | Payment-system code. |
| `value` | number | Total transaction value in ringgit. |
| `volume` | number | Number of transactions. |

## Known quirks

- Monthly dates use the first day of the month.
- Codes include `dd`, `fpx`, `ibg`, `jompay`, `rentas`, and `rpp`.
- `value` is monetary while `volume` is a transaction count.
- Floating-point volume values should be interpreted as counts as published.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.data.gov.my/finsector/payments/systems.csv" \
  -o /tmp/payments_systems.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: Bank Negara Malaysia via data.gov.my.

## Sample

- [samples/dgm_payments_systems.csv](../samples/dgm_payments_systems.csv)
- [samples/dgm_payments_systems.json](../samples/dgm_payments_systems.json)
