---
dataset_id: dosm_hh_expenditure_parlimen
last_checked: 2026-08-11T14:21:08Z
status: fresh
freshness_delta: 953 days
next_expected_update: biennial to triennial (survey years)
record_count: 666
date_range: 2019-01-01 to 2024-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Only the 2019, 2022, and 2024 survey years are present.", "Constituency labels include their official P-number prefix.", "Expenditure values are source-reported nominal mean monthly ringgit amounts."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: DOSM via OpenDOSM
---

# OpenDOSM Household Expenditure by Parliamentary Constituency

## Status

**Status:** Fresh

**Freshness:** 953 days

HTTP 200

## Last checked

2026-08-11 at 14:21:08 UTC.

## File size

The checked resource is 26,828 bytes.

## Provenance

The Department of Statistics Malaysia publishes this dataset through OpenDOSM as direct CSV and Parquet downloads:

- `https://storage.dosm.gov.my/hies/hh_expenditure_parlimen.csv`
- `https://storage.dosm.gov.my/hies/hh_expenditure_parlimen.parquet`

## Coverage

The dataset covers 222 parliamentary constituencies across 16 state-level areas from 2019-01-01 through 2024-01-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `date` | date | Observation date in YYYY-MM-DD format. |
| `state` | string | Malaysian state or federal territory. |
| `parlimen` | string | Parliamentary constituency code and name. |
| `expenditure` | integer | Mean monthly household consumption expenditure in Malaysian ringgit. |

## Known quirks

- Only the 2019, 2022, and 2024 survey years are present.
- Constituency labels include their official P-number prefix.
- Expenditure values are source-reported nominal mean monthly ringgit amounts.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.dosm.gov.my/hies/hh_expenditure_parlimen.csv" \
  -o /tmp/hh_expenditure_parlimen.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: DOSM via OpenDOSM.

## Sample

- [samples/dosm_hh_expenditure_parlimen.csv](../samples/dosm_hh_expenditure_parlimen.csv)
- [samples/dosm_hh_expenditure_parlimen.json](../samples/dosm_hh_expenditure_parlimen.json)
