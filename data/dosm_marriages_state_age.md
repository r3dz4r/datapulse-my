---
dataset_id: dosm_marriages_state_age
last_checked: 2026-08-16T02:09:20Z
status: stale
freshness_delta: 1688 days
next_expected_update: overdue
record_count: 2304
date_range: 2017-01-01 to 2022-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Annual dates use 1 January.", "All-age aggregates coexist with detailed age bands and must not be summed together.", "Twenty-seven rate values are blank in the source.", "The latest observation is 2022 despite an annual cadence."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: DOSM via OpenDOSM
---

# OpenDOSM Annual Marriages by State, Age, and Sex

## Status

**Status:** Stale

**Freshness:** 1688 days

HTTP 200

## Last checked

2026-08-16 at 02:09:20 UTC.

## File size

The checked resource is 95,399 bytes.

## Provenance

The Department of Statistics Malaysia publishes this dataset through OpenDOSM as direct CSV and Parquet downloads:

- `https://storage.dosm.gov.my/demography/marriages_state_age.csv`
- `https://storage.dosm.gov.my/demography/marriages_state_age.parquet`

## Coverage

The dataset covers 16 Malaysian state-level areas, disaggregated by age and sex from 2017-01-01 through 2022-01-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `state` | string | Malaysian state or federal territory. |
| `date` | date | Observation date in YYYY-MM-DD format. |
| `sex` | string | Source-reported sex category. |
| `age` | string | Age band or aggregate category. |
| `abs` | number | Absolute event count reported by the source. |
| `rate` | number | Source-reported rate for the observation dimensions. |

## Known quirks

- Annual dates use 1 January.
- All-age aggregates coexist with detailed age bands and must not be summed together.
- Twenty-seven rate values are blank in the source.
- The latest observation is 2022 despite an annual cadence.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.dosm.gov.my/demography/marriages_state_age.csv" \
  -o /tmp/marriages_state_age.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: DOSM via OpenDOSM.

## Sample

- [samples/dosm_marriages_state_age.csv](../samples/dosm_marriages_state_age.csv)
- [samples/dosm_marriages_state_age.json](../samples/dosm_marriages_state_age.json)
