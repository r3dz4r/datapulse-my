---
dataset_id: dosm_population_state
last_checked: 2026-08-14T04:59:27Z
status: fresh
freshness_delta: 225 days
next_expected_update: annual
record_count: 270063
date_range: 1970-01-01 to 2026-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["annual dates use January 1", "covers 16 state-level areas", "overall dimension values coexist with detailed rows", "age and ethnicity category sets vary across the time series"]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: DOSM via OpenDOSM
---

# OpenDOSM Annual Population by State

## Status

**Status:** Fresh

**Freshness:** 225 days

HTTP 200

## Last checked

2026-08-14 at 04:59:27 UTC.

## File size

The checked resource is 12,568,035 bytes.

## Provenance

DOSM publishes this dataset through OpenDOSM as direct CSV and Parquet
downloads:

- `https://storage.dosm.gov.my/population/population_state.csv`
- `https://storage.dosm.gov.my/population/population_state.parquet`

## Coverage

The dataset contains annual observations from 1970 through 2026 for 16
state-level areas: 13 states and W.P. Kuala Lumpur, W.P. Labuan, and W.P.
Putrajaya. There is no Malaysia aggregate row. Population is disaggregated by
sex, age group, and ethnicity.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `state` | string | One of 16 state or federal-territory labels. |
| `date` | date | Annual observation date in `YYYY-MM-DD` format. |
| `sex` | string | `both`, `female`, or `male`. |
| `age` | string | `overall` or an age-band label. |
| `ethnicity` | string | `overall` or an ethnicity-group label. |
| `population` | number | Reported population value for the dimensions. |

## Known quirks

- Annual dates use January 1 as the reporting date.
- `overall` aggregates coexist with detailed sex, age, and ethnicity rows;
  summing without filters will double count population.
- The full file contains both historical open-ended age bands (`70+`, `80+`)
  and newer detailed bands (`70-74`, `75-79`, `80-84`, `85+`).
- Ethnicity labels include aggregate and component categories whose
  availability varies across the time series.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.dosm.gov.my/population/population_state.csv" \
  -o /tmp/population_state.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: DOSM via OpenDOSM.

## Sample

- [samples/dosm_population_state.csv](../samples/dosm_population_state.csv)
- [samples/dosm_population_state.json](../samples/dosm_population_state.json)
