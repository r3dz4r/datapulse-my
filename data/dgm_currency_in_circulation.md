---
dataset_id: dgm_currency_in_circulation
last_checked: 2026-08-09T08:37:11Z
status: stale
freshness_delta: 189 days
next_expected_update: overdue
record_count: 5966
date_range: 2000-01-01 to 2026-02-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Monthly dates use 1 January.", "Values are reported in RM millions.", "Total rows coexist with denomination rows.", "Historical and other-denomination codes remain in the schema."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: Bank Negara Malaysia via data.gov.my
---

# data.gov.my Monthly Currency in Circulation

## Status

**Status:** Stale

**Freshness:** 189 days

HTTP 200

## Last checked

2026-08-09 at 08:37:11 UTC.

## File size

The checked resource is 157,801 bytes.

## Provenance

Bank Negara Malaysia publishes this dataset through data.gov.my as direct CSV
and Parquet downloads:

- `https://storage.data.gov.my/finsector/currency_in_circulation.csv`
- `https://storage.data.gov.my/finsector/currency_in_circulation.parquet`

## Coverage

The dataset covers currency in circulation in Malaysia from 2000-01-01 through
2026-02-01, split across 19 total, note, and coin codes.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `date` | date | Monthly observation date in YYYY-MM-DD format. |
| `denomination` | string | Total, banknote, or coin denomination code. |
| `value` | number | Currency in circulation in RM millions. |

## Known quirks

- Monthly dates use the first day of the month.
- `total` rows coexist with denomination rows and must not be summed together.
- Historical denominations and `note_others` or `coin_others` remain present.
- Values are in RM millions and retain source precision.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.data.gov.my/finsector/currency_in_circulation.csv" \
  -o /tmp/currency_in_circulation.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: Bank Negara Malaysia via data.gov.my.

## Sample

- [samples/dgm_currency_in_circulation.csv](../samples/dgm_currency_in_circulation.csv)
- [samples/dgm_currency_in_circulation.json](../samples/dgm_currency_in_circulation.json)
