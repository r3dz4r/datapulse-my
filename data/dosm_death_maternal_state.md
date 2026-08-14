---
dataset_id: dosm_death_maternal_state
last_checked: 2026-08-14T04:59:27Z
status: aging
freshness_delta: 956 days
next_expected_update: annual
record_count: 390
date_range: 2000-01-01 to 2024-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Annual dates use 1 January.", "The file has no Malaysia aggregate.", "W.P. Putrajaya observations begin in 2010.", "Small absolute counts can produce volatile maternal mortality ratios."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: DOSM via OpenDOSM
---

# OpenDOSM Annual Maternal Deaths by State

## Status

**Status:** Aging

**Freshness:** 956 days

HTTP 200

## Last checked

2026-08-14 at 04:59:27 UTC.

## File size

The checked resource is 10,884 bytes.

## Provenance

The Department of Statistics Malaysia publishes this dataset through OpenDOSM
as direct CSV and Parquet downloads:

- `https://storage.dosm.gov.my/demography/death_maternal_state.csv`
- `https://storage.dosm.gov.my/demography/death_maternal_state.parquet`

## Coverage

The dataset covers annual maternal deaths for 16 Malaysian state-level areas
from 2000 through 2024; W.P. Putrajaya begins in 2010.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `state` | string | Malaysian state or federal territory. |
| `date` | date | Annual observation date in YYYY-MM-DD format. |
| `abs` | integer | Registered maternal deaths. |
| `rate` | number | Source-reported maternal mortality ratio. |

## Known quirks

- Annual dates use 1 January.
- There is no Malaysia aggregate row.
- W.P. Putrajaya has 15 observations beginning in 2010; the other areas have
  25 observations beginning in 2000.
- Small state-level death counts can yield large year-to-year changes in the
  maternal mortality ratio.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.dosm.gov.my/demography/death_maternal_state.csv" \
  -o /tmp/death_maternal_state.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: DOSM via OpenDOSM.

## Sample

- [samples/dosm_death_maternal_state.csv](../samples/dosm_death_maternal_state.csv)
- [samples/dosm_death_maternal_state.json](../samples/dosm_death_maternal_state.json)
