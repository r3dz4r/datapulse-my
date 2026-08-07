---
dataset_id: dosm_death_state
last_checked: 2026-08-07T07:25:52Z
status: fresh
freshness_delta: 30 days
next_expected_update: annual
record_count: 390
date_range: 2000-01-01 to 2024-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Annual dates use 1 January.", "The file has no Malaysia aggregate.", "W.P. Putrajaya observations begin in 2010.", "Absolute counts and crude death rates use different units."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: DOSM via OpenDOSM
---

# OpenDOSM Annual Deaths by State

## Status

**Status:** Fresh

**Freshness:** 30 days

HTTP 200

## Last checked

2026-08-07 at 07:25:52 UTC.

## File size

The checked resource is 11,698 bytes.

## Provenance

The Department of Statistics Malaysia publishes this dataset through OpenDOSM
as direct CSV and Parquet downloads:

- `https://storage.dosm.gov.my/demography/death_state.csv`
- `https://storage.dosm.gov.my/demography/death_state.parquet`

## Coverage

The dataset covers annual registered deaths for 16 Malaysian state-level areas
from 2000 through 2024; W.P. Putrajaya begins in 2010.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `state` | string | Malaysian state or federal territory. |
| `date` | date | Annual observation date in YYYY-MM-DD format. |
| `abs` | integer | Registered deaths. |
| `rate` | number | Source-reported crude death rate. |

## Known quirks

- Annual dates use 1 January.
- There is no Malaysia aggregate row.
- W.P. Putrajaya has 15 observations beginning in 2010; the other areas have
  25 observations beginning in 2000.
- `abs` is a count while `rate` is a crude death rate and cannot be summed.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.dosm.gov.my/demography/death_state.csv" \
  -o /tmp/death_state.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: DOSM via OpenDOSM.

## Sample

- [samples/dosm_death_state.csv](../samples/dosm_death_state.csv)
- [samples/dosm_death_state.json](../samples/dosm_death_state.json)
