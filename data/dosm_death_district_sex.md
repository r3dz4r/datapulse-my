---
dataset_id: dosm_death_district_sex
last_checked: 2026-08-10T10:07:26Z
status: aging
freshness_delta: 952 days
next_expected_update: annual
record_count: 2361
date_range: 2020-01-01 to 2024-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Annual dates use 1 January.", "Both-sex aggregates coexist with male and female rows and must not be summed together.", "The 2020 file has 147 district labels; 2021 onward has 160.", "Absolute counts are stored as decimal-valued numbers in the source."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: DOSM via OpenDOSM
---

# OpenDOSM Annual Deaths by District and Sex

## Status

**Status:** Aging

**Freshness:** 952 days

HTTP 200

## Last checked

2026-08-10 at 10:07:26 UTC.

## File size

The checked resource is 129,831 bytes.

## Provenance

The Department of Statistics Malaysia publishes this dataset through OpenDOSM as direct CSV and Parquet downloads:

- `https://storage.dosm.gov.my/demography/death_district_sex.csv`
- `https://storage.dosm.gov.my/demography/death_district_sex.parquet`

## Coverage

The dataset covers 160 districts across 16 Malaysian state-level areas from 2020-01-01 through 2024-01-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `date` | date | Observation date in YYYY-MM-DD format. |
| `state` | string | Malaysian state or federal territory. |
| `district` | string | Administrative district. |
| `sex` | string | Source-reported sex category. |
| `abs` | number | Absolute event count reported by the source. |
| `rate` | number | Source-reported rate for the observation dimensions. |

## Known quirks

- Annual dates use 1 January.
- Both-sex aggregates coexist with male and female rows and must not be summed together.
- The 2020 file has 147 district labels; 2021 onward has 160.
- Absolute counts are stored as decimal-valued numbers in the source.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.dosm.gov.my/demography/death_district_sex.csv" \
  -o /tmp/death_district_sex.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: DOSM via OpenDOSM.

## Sample

- [samples/dosm_death_district_sex.csv](../samples/dosm_death_district_sex.csv)
- [samples/dosm_death_district_sex.json](../samples/dosm_death_district_sex.json)
