---
dataset_id: dosm_fertility
last_checked: 2026-08-07T07:25:52Z
status: fresh
freshness_delta: 30 days
next_expected_update: annual
record_count: 536
date_range: 1958-01-01 to 2024-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Annual dates use 1 January.", "Age-specific fertility-rate rows coexist with a `tfr` total-fertility-rate row.", "The `tfr` row has a different interpretation and unit from age-specific rates."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: DOSM via OpenDOSM
---

# OpenDOSM Annual Fertility

## Status

**Status:** Fresh

**Freshness:** 30 days

HTTP 200

## Last checked

2026-08-07 at 07:25:52 UTC.

## File size

The checked resource is 11,860 bytes.

## Provenance

The Department of Statistics Malaysia publishes this dataset through OpenDOSM as direct CSV and Parquet downloads:

- `https://storage.dosm.gov.my/demography/fertility.csv`
- `https://storage.dosm.gov.my/demography/fertility.parquet`

## Coverage

The dataset covers Malaysia at national level from 1958-01-01 through 2024-01-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `date` | date | Observation date in YYYY-MM-DD format. |
| `age_group` | string | Female age band, or `tfr` for total fertility rate. |
| `fertility_rate` | number | Age-specific fertility rate, or total fertility rate for `tfr` rows. |

## Known quirks

- Annual dates use 1 January.
- Age-specific fertility-rate rows coexist with a `tfr` total-fertility-rate row.
- The `tfr` row has a different interpretation and unit from age-specific rates.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.dosm.gov.my/demography/fertility.csv" \
  -o /tmp/fertility.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: DOSM via OpenDOSM.

## Sample

- [samples/dosm_fertility.csv](../samples/dosm_fertility.csv)
- [samples/dosm_fertility.json](../samples/dosm_fertility.json)
