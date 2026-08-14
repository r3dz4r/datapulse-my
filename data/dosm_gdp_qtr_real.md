---
dataset_id: dosm_gdp_qtr_real
last_checked: 2026-08-14T04:59:27Z
status: aging
freshness_delta: 225 days
next_expected_update: quarterly
record_count: 130
date_range: 2015-01-01 to 2026-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["quarterly dates use the first day of each quarter", "series mixes absolute values with growth rates"]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: DOSM via OpenDOSM
---

# OpenDOSM Quarterly Real GDP

## Status

**Status:** Aging

**Freshness:** 225 days

HTTP 200

## Last checked

2026-08-14 at 04:59:27 UTC.

## File size

The checked resource is 3,374 bytes.

## Provenance

DOSM publishes this national dataset through OpenDOSM as direct CSV and
Parquet downloads:

- `https://storage.dosm.gov.my/gdp/gdp_qtr_real.csv`
- `https://storage.dosm.gov.my/gdp/gdp_qtr_real.parquet`

## Coverage

The dataset contains national quarterly observations for Malaysia from
2015 Q1 through 2026 Q1. It does not contain a geographic field or
subnational rows.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `series` | string | `abs`, `growth_yoy`, or `growth_qoq`. |
| `date` | date | Quarter start date in `YYYY-MM-DD` format. |
| `value` | number | GDP value in the unit defined by `series`. |

## Known quirks

- Quarterly dates use the first day of January, April, July, or October.
- Absolute GDP values and percentage growth rates share the `value` column;
  consumers must use `series` to interpret them.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.dosm.gov.my/gdp/gdp_qtr_real.csv" \
  -o /tmp/gdp_qtr_real.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: DOSM via OpenDOSM.

## Sample

- [samples/dosm_gdp_qtr_real.csv](../samples/dosm_gdp_qtr_real.csv)
- [samples/dosm_gdp_qtr_real.json](../samples/dosm_gdp_qtr_real.json)
