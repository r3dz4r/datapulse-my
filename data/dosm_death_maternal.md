---
dataset_id: dosm_death_maternal
last_checked: 2026-08-14T04:59:27Z
status: aging
freshness_delta: 956 days
next_expected_update: annual
record_count: 79
date_range: 1946-01-01 to 2024-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Annual dates use 1 January.", "Absolute maternal-death counts are blank from 1946 through 1999; rates remain available.", "Small absolute counts can produce volatile maternal mortality ratios."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: DOSM via OpenDOSM
---

# OpenDOSM Annual Maternal Deaths, Malaysia

## Status

**Status:** Aging

**Freshness:** 956 days

HTTP 200

## Last checked

2026-08-14 at 04:59:27 UTC.

## File size

The checked resource is 1,508 bytes.

## Provenance

The Department of Statistics Malaysia publishes this dataset through OpenDOSM as direct CSV and Parquet downloads:

- `https://storage.dosm.gov.my/demography/death_maternal.csv`
- `https://storage.dosm.gov.my/demography/death_maternal.parquet`

## Coverage

The dataset covers Malaysia at national level from 1946-01-01 through 2024-01-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `date` | date | Observation date in YYYY-MM-DD format. |
| `abs` | number | Absolute event count reported by the source. |
| `rate` | number | Source-reported rate for the observation dimensions. |

## Known quirks

- Annual dates use 1 January.
- Absolute maternal-death counts are blank from 1946 through 1999; rates remain available.
- Small absolute counts can produce volatile maternal mortality ratios.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.dosm.gov.my/demography/death_maternal.csv" \
  -o /tmp/death_maternal.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: DOSM via OpenDOSM.

## Sample

- [samples/dosm_death_maternal.csv](../samples/dosm_death_maternal.csv)
- [samples/dosm_death_maternal.json](../samples/dosm_death_maternal.json)
