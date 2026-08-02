---
dataset_id: dgm_money_aggregates
last_checked: 2026-08-02T17:18:27Z
status: stale
freshness_delta: 119 days since file update
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

## Provenance

Bank Negara Malaysia publishes this dataset through data.gov.my as direct CSV
and Parquet downloads:

- `https://storage.data.gov.my/finsector/money_aggregates.csv`
- `https://storage.data.gov.my/finsector/money_aggregates.parquet`

## Status

**Status:** Stale

**Freshness:** File last updated 2026-04-05; observations end on 2026-02-01

**Refresh frequency:** Monthly

The CSV endpoint returned HTTP 200 and its expected 75,535-byte file. It
contains 1,896 data rows.

## Last checked

2026-08-02 by direct HTTP HEAD request and CSV download.

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
