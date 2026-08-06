---
dataset_id: dosm_hh_poverty_district
last_checked: 2026-08-05T14:31:11Z
status: fresh
freshness_delta: 30 days
next_expected_update: biennial to triennial (survey years)
record_count: 480
date_range: 2019-01-01 to 2024-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Only the 2019, 2022, and 2024 survey years are present.", "District coverage varies across survey years, so the 172 labels do not form a complete panel.", "The district file provides absolute and relative poverty, but not hardcore poverty.", "Rates are percentages, not proportions."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: DOSM via OpenDOSM
---

# OpenDOSM Poverty by District

## Status

**Status:** Fresh

**Freshness:** 30 days

HTTP 200

## Last checked

2026-08-05 at 14:31:11 UTC.

## File size

The checked resource is 17,906 bytes.

## Provenance

The Department of Statistics Malaysia publishes this dataset through OpenDOSM as direct CSV and Parquet downloads:

- `https://storage.dosm.gov.my/hies/hh_poverty_district.csv`
- `https://storage.dosm.gov.my/hies/hh_poverty_district.parquet`

## Coverage

The dataset covers 16 state-level areas and 172 district labels across the available survey years from 2019-01-01 through 2024-01-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `state` | string | Malaysian state or federal territory. |
| `district` | string | Administrative district. |
| `date` | date | Observation date in YYYY-MM-DD format. |
| `poverty_absolute` | number | Incidence of absolute poverty, in percent. |
| `poverty_relative` | number | Incidence of relative poverty, in percent. |

## Known quirks

- Only the 2019, 2022, and 2024 survey years are present.
- District coverage varies across survey years, so the 172 labels do not form a complete panel.
- The district file provides absolute and relative poverty, but not hardcore poverty.
- Rates are percentages, not proportions.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.dosm.gov.my/hies/hh_poverty_district.csv" \
  -o /tmp/hh_poverty_district.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: DOSM via OpenDOSM.

## Sample

- [samples/dosm_hh_poverty_district.csv](../samples/dosm_hh_poverty_district.csv)
- [samples/dosm_hh_poverty_district.json](../samples/dosm_hh_poverty_district.json)
