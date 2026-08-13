---
dataset_id: dosm_hh_poverty_state
last_checked: 2026-08-13T02:46:04Z
status: fresh
freshness_delta: 955 days
next_expected_update: biennial to triennial (survey years)
record_count: 310
date_range: 1970-01-01 to 2024-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Dates mark survey years and are not a continuous annual series.", "State coverage expands over the historical series.", "The source contains blanks in all three poverty measures, concentrated in earlier years.", "Rates are percentages, not proportions."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: DOSM via OpenDOSM
---

# OpenDOSM Poverty by State

## Status

**Status:** Fresh

**Freshness:** 955 days

HTTP 200

## Last checked

2026-08-13 at 02:46:04 UTC.

## File size

The checked resource is 10,041 bytes.

## Provenance

The Department of Statistics Malaysia publishes this dataset through OpenDOSM as direct CSV and Parquet downloads:

- `https://storage.dosm.gov.my/hies/hh_poverty_state.csv`
- `https://storage.dosm.gov.my/hies/hh_poverty_state.parquet`

## Coverage

The dataset covers 16 Malaysian state-level areas, with historical coverage varying by survey year from 1970-01-01 through 2024-01-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `state` | string | Malaysian state or federal territory. |
| `date` | date | Observation date in YYYY-MM-DD format. |
| `poverty_absolute` | number | Incidence of absolute poverty, in percent. |
| `poverty_hardcore` | number | Incidence of hardcore poverty, in percent. |
| `poverty_relative` | number | Incidence of relative poverty, in percent. |

## Known quirks

- Dates mark survey years and are not a continuous annual series.
- State coverage expands over the historical series.
- The source contains blanks in all three poverty measures, concentrated in earlier years.
- Rates are percentages, not proportions.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.dosm.gov.my/hies/hh_poverty_state.csv" \
  -o /tmp/hh_poverty_state.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: DOSM via OpenDOSM.

## Sample

- [samples/dosm_hh_poverty_state.csv](../samples/dosm_hh_poverty_state.csv)
- [samples/dosm_hh_poverty_state.json](../samples/dosm_hh_poverty_state.json)
