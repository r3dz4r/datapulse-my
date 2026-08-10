---
dataset_id: dgm_payments_instruments
last_checked: 2026-08-09T08:37:11Z
status: stale
freshness_delta: 189 days
next_expected_update: overdue
record_count: 688
date_range: 2019-01-01 to 2026-02-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Monthly dates use 1 January.", "Instrument codes separate face-to-face and online activity.", "Value and volume use different units.", "The earliest charge-card rows contain null value and volume fields."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: Bank Negara Malaysia via data.gov.my
---

# data.gov.my Monthly Payment Instruments

## Status

**Status:** Stale

**Freshness:** 189 days

HTTP 200

## Last checked

2026-08-09 at 08:37:11 UTC.

## File size

The checked resource is 32,818 bytes.

## Provenance

Bank Negara Malaysia publishes this dataset through data.gov.my as direct CSV
and Parquet downloads:

- `https://storage.data.gov.my/finsector/payments/instruments.csv`
- `https://storage.data.gov.my/finsector/payments/instruments.parquet`

## Coverage

The dataset covers eight payment-instrument series in Malaysia from 2019-01-01
through 2026-02-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `date` | date | Monthly observation date in YYYY-MM-DD format. |
| `instrument` | string | Payment instrument and channel code. |
| `value` | number or null | Total transaction value in ringgit. |
| `volume` | number or null | Number of transactions. |

## Known quirks

- Monthly dates use the first day of the month.
- Instrument codes distinguish face-to-face (`f2f`) and online activity.
- The first 18 `charge_f2f` observations have blank value and volume fields.
- `value` is monetary while `volume` is a transaction count.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.data.gov.my/finsector/payments/instruments.csv" \
  -o /tmp/payments_instruments.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: Bank Negara Malaysia via data.gov.my.

## Sample

- [samples/dgm_payments_instruments.csv](../samples/dgm_payments_instruments.csv)
- [samples/dgm_payments_instruments.json](../samples/dgm_payments_instruments.json)
