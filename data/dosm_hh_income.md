---
dataset_id: dosm_hh_income
last_checked: 2026-08-11T14:21:08Z
status: fresh
freshness_delta: 953 days
next_expected_update: biennial to triennial (survey years)
record_count: 22
date_range: 1970-01-01 to 2024-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Dates mark survey years and are not a continuous annual series.", "Annual dates use 1 January.", "Income values are source-reported nominal monthly ringgit amounts; inflation adjustment is not included."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: DOSM via OpenDOSM
---

# OpenDOSM Household Income, Malaysia

## Status

**Status:** Fresh

**Freshness:** 953 days

HTTP 200

## Last checked

2026-08-11 at 14:21:08 UTC.

## File size

The checked resource is 482 bytes.

## Provenance

The Department of Statistics Malaysia publishes this dataset through OpenDOSM as direct CSV and Parquet downloads:

- `https://storage.dosm.gov.my/hies/hh_income.csv`
- `https://storage.dosm.gov.my/hies/hh_income.parquet`

## Coverage

The dataset covers Malaysia at national level from 1970-01-01 through 2024-01-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `date` | date | Observation date in YYYY-MM-DD format. |
| `income_mean` | integer | Mean monthly gross household income in Malaysian ringgit. |
| `income_median` | number | Median monthly gross household income in Malaysian ringgit. |

## Known quirks

- Dates mark survey years and are not a continuous annual series.
- Annual dates use 1 January.
- Income values are source-reported nominal monthly ringgit amounts; inflation adjustment is not included.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.dosm.gov.my/hies/hh_income.csv" \
  -o /tmp/hh_income.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: DOSM via OpenDOSM.

## Sample

- [samples/dosm_hh_income.csv](../samples/dosm_hh_income.csv)
- [samples/dosm_hh_income.json](../samples/dosm_hh_income.json)
