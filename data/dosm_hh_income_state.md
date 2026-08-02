---
dataset_id: dosm_hh_income_state
last_checked: 2026-08-02T19:11:50Z
status: current
freshness_delta: 27 days since file update
next_expected_update: biennial to triennial (survey years)
record_count: 319
date_range: 1970-01-01 to 2024-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Dates mark survey years and are not a continuous annual series.", "State coverage expands over the historical series.", "Eleven early median-income values are blank in the source.", "Income values are source-reported nominal monthly ringgit amounts."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: DOSM via OpenDOSM
---

# OpenDOSM Household Income by State

## Provenance

The Department of Statistics Malaysia publishes this dataset through OpenDOSM as direct CSV and Parquet downloads:

- `https://storage.dosm.gov.my/hies/hh_income_state.csv`
- `https://storage.dosm.gov.my/hies/hh_income_state.parquet`

## Status

**Status:** Current

**Freshness:** File last updated 2026-07-06; observations extend through 2024-01-01

**Refresh frequency:** Biennial to triennial (survey years)

The CSV endpoint returned HTTP 200 and its expected 10,171-byte file. It contains 319 data rows.

## Last checked

2026-08-02 by direct HTTP HEAD request and CSV download.

## Coverage

The dataset covers 16 Malaysian state-level areas, with historical coverage varying by survey year from 1970-01-01 through 2024-01-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `state` | string | Malaysian state or federal territory. |
| `date` | date | Observation date in YYYY-MM-DD format. |
| `income_mean` | integer | Mean monthly gross household income in Malaysian ringgit. |
| `income_median` | number | Median monthly gross household income in Malaysian ringgit. |

## Known quirks

- Dates mark survey years and are not a continuous annual series.
- State coverage expands over the historical series.
- Eleven early median-income values are blank in the source.
- Income values are source-reported nominal monthly ringgit amounts.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.dosm.gov.my/hies/hh_income_state.csv" \
  -o /tmp/hh_income_state.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: DOSM via OpenDOSM.

## Sample

- [samples/dosm_hh_income_state.csv](../samples/dosm_hh_income_state.csv)
- [samples/dosm_hh_income_state.json](../samples/dosm_hh_income_state.json)
