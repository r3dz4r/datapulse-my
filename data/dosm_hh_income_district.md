---
dataset_id: dosm_hh_income_district
last_checked: 2026-08-14T04:59:27Z
status: fresh
freshness_delta: 956 days
next_expected_update: biennial to triennial (survey years)
record_count: 480
date_range: 2019-01-01 to 2024-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Only the 2019, 2022, and 2024 survey years are present.", "District coverage varies across survey years, so the 172 labels do not form a complete panel.", "Income values are source-reported nominal monthly ringgit amounts."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: DOSM via OpenDOSM
---

# OpenDOSM Household Income by District

## Status

**Status:** Fresh

**Freshness:** 956 days

HTTP 200

## Last checked

2026-08-14 at 04:59:27 UTC.

## File size

The checked resource is 18,323 bytes.

## Provenance

The Department of Statistics Malaysia publishes this dataset through OpenDOSM as direct CSV and Parquet downloads:

- `https://storage.dosm.gov.my/hies/hh_income_district.csv`
- `https://storage.dosm.gov.my/hies/hh_income_district.parquet`

## Coverage

The dataset covers 16 state-level areas and 172 district labels across the available survey years from 2019-01-01 through 2024-01-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `state` | string | Malaysian state or federal territory. |
| `district` | string | Administrative district. |
| `date` | date | Observation date in YYYY-MM-DD format. |
| `income_mean` | integer | Mean monthly gross household income in Malaysian ringgit. |
| `income_median` | number | Median monthly gross household income in Malaysian ringgit. |

## Known quirks

- Only the 2019, 2022, and 2024 survey years are present.
- District coverage varies across survey years, so the 172 labels do not form a complete panel.
- Income values are source-reported nominal monthly ringgit amounts.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.dosm.gov.my/hies/hh_income_district.csv" \
  -o /tmp/hh_income_district.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: DOSM via OpenDOSM.

## Sample

- [samples/dosm_hh_income_district.csv](../samples/dosm_hh_income_district.csv)
- [samples/dosm_hh_income_district.json](../samples/dosm_hh_income_district.json)
