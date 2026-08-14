---
dataset_id: population_malaysia
last_checked: 2026-08-14T04:59:27Z
status: fresh
freshness_delta: 225 days
next_expected_update: annual
record_count: 17814
date_range: 1970-01-01 to 2026-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Annual dates use 1 January.", "Overall and detailed dimension rows coexist and must not be summed together.", "Age and ethnicity category sets vary across the historical series.", "Population values are reported in thousands."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: DOSM via OpenDOSM
---

# OpenDOSM Annual Population, Malaysia

## Status

**Status:** Fresh

**Freshness:** 225 days

HTTP 200

## Last checked

2026-08-14 at 04:59:27 UTC.

## File size

The checked resource is 677,857 bytes.

## Provenance

The Department of Statistics Malaysia publishes this dataset through OpenDOSM as direct CSV and Parquet downloads:

- `https://storage.dosm.gov.my/population/population_malaysia.csv`
- `https://storage.dosm.gov.my/population/population_malaysia.parquet`

## Coverage

The dataset covers Malaysia at national level, disaggregated by sex, age, and ethnicity from 1970-01-01 through 2026-01-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `date` | date | Observation date in YYYY-MM-DD format. |
| `sex` | string | Source-reported sex category. |
| `age` | string | Age band or aggregate category. |
| `ethnicity` | string | Ethnicity or citizenship dimension category. |
| `population` | number | Population in thousands of people. |

## Known quirks

- Annual dates use 1 January.
- Overall and detailed dimension rows coexist and must not be summed together.
- Age and ethnicity category sets vary across the historical series.
- Population values are reported in thousands.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.dosm.gov.my/population/population_malaysia.csv" \
  -o /tmp/population_malaysia.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: DOSM via OpenDOSM.

## Sample

- [samples/dosm_population_malaysia.csv](../samples/dosm_population_malaysia.csv)
- [samples/dosm_population_malaysia.json](../samples/dosm_population_malaysia.json)
