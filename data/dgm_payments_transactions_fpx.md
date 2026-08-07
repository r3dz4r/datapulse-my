---
dataset_id: dgm_payments_transactions_fpx
last_checked: 2026-08-07T07:25:52Z
status: fresh
freshness_delta: 0 days
next_expected_update: daily
record_count: 7206
date_range: 2020-01-01 to 2026-08-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Both-model aggregate rows coexist with B2B and B2C rows.", "Value and volume use different units.", "Three two-day gaps occur in the date series.", "Dates are calendar dates rather than business-day labels."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: Bank Negara Malaysia via data.gov.my
---

# data.gov.my Daily FPX Transactions

## Status

**Status:** Fresh

**Freshness:** 0 days

HTTP 200

## Last checked

2026-08-07 at 07:25:52 UTC.

## File size

The checked resource is 271,677 bytes.

## Provenance

Bank Negara Malaysia publishes this dataset through data.gov.my as direct CSV
and Parquet downloads:

- `https://storage.data.gov.my/finsector/payments/trnsc_daily_fpx.csv`
- `https://storage.data.gov.my/finsector/payments/trnsc_daily_fpx.parquet`

## Coverage

The dataset covers daily Financial Process Exchange (FPX) transaction activity
from 2020-01-01 through 2026-08-01 for B2B, B2C, and combined models.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `date` | date | Daily observation date in YYYY-MM-DD format. |
| `model` | string | `B2B`, `B2C`, or combined (`both`) model. |
| `volume` | integer | Number of FPX transactions. |
| `value` | number | Total FPX transaction value in ringgit. |

## Known quirks

- `both` aggregate rows coexist with B2B and B2C rows and will double count if
  all models are summed.
- `value` is monetary while `volume` is a transaction count.
- The otherwise daily series has two-day jumps ending on 2024-11-25,
  2026-06-04, and 2026-08-01.
- Dates cover calendar days, including weekends.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.data.gov.my/finsector/payments/trnsc_daily_fpx.csv" \
  -o /tmp/trnsc_daily_fpx.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: Bank Negara Malaysia via data.gov.my.

## Sample

- [samples/dgm_payments_transactions_fpx.csv](../samples/dgm_payments_transactions_fpx.csv)
- [samples/dgm_payments_transactions_fpx.json](../samples/dgm_payments_transactions_fpx.json)
