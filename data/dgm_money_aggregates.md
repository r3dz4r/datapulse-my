---
dataset_id: dgm_money_aggregates
last_checked: 2026-08-07T07:25:52Z
status: stale
freshness_delta: 187 days
next_expected_update: overdue
record_count: 1896
date_range: 2013-01-01 to 2026-02-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Monthly dates use 1 January.", "Values are reported in RM millions.", "Aggregate M1, M2, and M3 rows coexist with component rows.", "Measure codes require the official money-supply definitions."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: Bank Negara Malaysia via data.gov.my
---

# data.gov.my Monthly Money Aggregates

## Status

**Status:** Stale

**Freshness:** 187 days

HTTP 200

## Last checked

2026-08-07 at 07:25:52 UTC.

## File size

The checked resource is 75,535 bytes.

## Provenance

Bank Negara Malaysia publishes this dataset through data.gov.my as direct CSV
and Parquet downloads:

- `https://storage.data.gov.my/finsector/money_aggregates.csv`
- `https://storage.data.gov.my/finsector/money_aggregates.parquet`

## Coverage

The dataset covers Malaysia's monetary aggregates from 2013-01-01 through
2026-02-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `date` | date | Monthly observation date in YYYY-MM-DD format. |
| `measure` | string | Money aggregate or component code. |
| `value` | number | Reported value in RM millions. |

## Known quirks

- Monthly dates use the first day of the month.
- Aggregate M1, M2, and M3 series coexist with their components; summing all
  rows will double count money supply.
- Measure codes such as `m1_total` and `m2_deposit_fixed` require the official
  money-supply definitions.
- Values are reported in RM millions and retain source precision.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.data.gov.my/finsector/money_aggregates.csv" \
  -o /tmp/money_aggregates.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: Bank Negara Malaysia via data.gov.my.

## Sample

- [samples/dgm_money_aggregates.csv](../samples/dgm_money_aggregates.csv)
- [samples/dgm_money_aggregates.json](../samples/dgm_money_aggregates.json)
