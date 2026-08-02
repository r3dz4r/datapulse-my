---
dataset_id: dgm_payments_channels
last_checked: 2026-08-02T17:18:27Z
status: stale
freshness_delta: 119 days since file update
next_expected_update: overdue
record_count: 430
date_range: 2019-01-01 to 2026-02-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Monthly dates use 1 January.", "Channel codes distinguish ATM, internet, and mobile activity.", "Value and volume use different units.", "The file contains one row per month and channel."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: Bank Negara Malaysia via data.gov.my
---

# data.gov.my Monthly Payment Channels

## Provenance

Bank Negara Malaysia publishes this dataset through data.gov.my as direct CSV
and Parquet downloads:

- `https://storage.data.gov.my/finsector/payments/channels.csv`
- `https://storage.data.gov.my/finsector/payments/channels.parquet`

## Status

**Status:** Stale

**Freshness:** File last updated 2026-04-05; observations end on 2026-02-01

**Refresh frequency:** Monthly

The CSV endpoint returned HTTP 200 and its expected 20,990-byte file. It
contains 430 data rows.

## Last checked

2026-08-02 by direct HTTP HEAD request and CSV download.

## Coverage

The dataset covers five ATM, internet-banking, and mobile-banking channels in
Malaysia from 2019-01-01 through 2026-02-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `date` | date | Monthly observation date in YYYY-MM-DD format. |
| `channel` | string | Payment access-channel code. |
| `value` | number | Total transaction value in ringgit. |
| `volume` | number | Number of transactions. |

## Known quirks

- Monthly dates use the first day of the month.
- Channel codes include ATM cash withdrawal, ATM financial transactions,
  corporate and individual internet banking, and mobile banking.
- `value` is monetary while `volume` is a transaction count.
- Values retain the precision published by the source.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.data.gov.my/finsector/payments/channels.csv" \
  -o /tmp/payments_channels.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: Bank Negara Malaysia via data.gov.my.

## Sample

- [samples/dgm_payments_channels.csv](../samples/dgm_payments_channels.csv)
- [samples/dgm_payments_channels.json](../samples/dgm_payments_channels.json)
