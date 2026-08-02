---
dataset_id: dosm_population_parlimen
last_checked: 2026-08-02T19:11:50Z
status: current
freshness_delta: 28 days since file update
next_expected_update: annual
record_count: 5550
date_range: 2020-01-01 to 2024-01-01
schema_version: 1.0
schema_drift: citizenship categories move from ethnicity in 2020 to age from 2021
known_quirks: ["Annual dates use 1 January.", "Overall and detailed dimension rows coexist and must not be summed together.", "Citizenship appears in `ethnicity` in 2020 but in `age` from 2021 onward.", "Population values are reported in thousands."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: DOSM via OpenDOSM
---

# OpenDOSM Annual Population by Parliamentary Constituency

## Provenance

The Department of Statistics Malaysia publishes this dataset through OpenDOSM as direct CSV and Parquet downloads:

- `https://storage.dosm.gov.my/population/population_parlimen.csv`
- `https://storage.dosm.gov.my/population/population_parlimen.parquet`

## Status

**Status:** Current

**Freshness:** File last updated 2026-07-05; observations extend through 2024-01-01

**Refresh frequency:** Annual

The CSV endpoint returned HTTP 200 and its expected 346,540-byte file. It contains 5,550 data rows.

## Last checked

2026-08-02 by direct HTTP HEAD request and CSV download.

## Coverage

The dataset covers 222 parliamentary constituencies across 16 state-level areas from 2020-01-01 through 2024-01-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `date` | date | Observation date in YYYY-MM-DD format. |
| `state` | string | Malaysian state or federal territory. |
| `parlimen` | string | Parliamentary constituency code and name. |
| `sex` | string | Source-reported sex category. |
| `age` | string | Age band or aggregate category. |
| `ethnicity` | string | Ethnicity or citizenship dimension category. |
| `population` | number | Population in thousands of people. |

## Known quirks

- Annual dates use 1 January.
- Overall and detailed dimension rows coexist and must not be summed together.
- Citizenship appears in `ethnicity` in 2020 but in `age` from 2021 onward.
- Population values are reported in thousands.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.dosm.gov.my/population/population_parlimen.csv" \
  -o /tmp/population_parlimen.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: DOSM via OpenDOSM.

## Sample

- [samples/dosm_population_parlimen.csv](../samples/dosm_population_parlimen.csv)
- [samples/dosm_population_parlimen.json](../samples/dosm_population_parlimen.json)
