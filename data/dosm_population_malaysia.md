---
dataset_id: dosm_population_malaysia
last_checked: 2026-08-02T19:11:50Z
status: current
freshness_delta: 2 days since file update
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

## Provenance

The Department of Statistics Malaysia publishes this dataset through OpenDOSM as direct CSV and Parquet downloads:

- `https://storage.dosm.gov.my/population/population_malaysia.csv`
- `https://storage.dosm.gov.my/population/population_malaysia.parquet`

## Status

**Status:** Current

**Freshness:** File last updated 2026-07-31; observations extend through 2026-01-01

**Refresh frequency:** Annual

The CSV endpoint returned HTTP 200 and its expected 677,857-byte file. It contains 17,814 data rows.

## Last checked

2026-08-02 by direct HTTP HEAD request and CSV download.

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
