---
dataset_id: population_district
last_checked: 2026-11-05T03:33:57Z
status: fresh
freshness_delta: 310 days
next_expected_update: annual
record_count: 451668
date_range: 2020-01-01 to 2025-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["annual dates use January 1", "overall dimension values coexist with detailed rows"]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: DOSM via OpenDOSM
---

# OpenDOSM Annual Population by Administrative District

## Status

**Status:** Fresh

**Freshness:** 310 days

HTTP 200

## Last checked

2026-11-05 at 03:33:57 UTC.

## File size

The checked resource is 24,637,855 bytes.

## Provenance

DOSM publishes this dataset through OpenDOSM as a direct CSV download:

- `https://storage.dosm.gov.my/population/population_district.csv`

## Coverage

The dataset contains annual population observations for Malaysian
administrative districts, disaggregated by sex, age group, and ethnicity.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `state` | string | State or federal territory. |
| `district` | string | Administrative district. |
| `date` | date | Annual observation date in `YYYY-MM-DD` format. |
| `sex` | string | Sex category. |
| `age` | string | Age group. |
| `ethnicity` | string | Ethnicity group. |
| `population` | number | Reported population value for the dimensions. |

## Known quirks

- Annual dates use January 1 as the reporting date.
- `overall` aggregates coexist with detailed rows; summing without filters can
  double count population.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.dosm.gov.my/population/population_district.csv" \
  -o /tmp/population_district.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: DOSM via OpenDOSM.
