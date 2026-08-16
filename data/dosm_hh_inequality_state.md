---
dataset_id: dosm_hh_inequality_state
last_checked: 2026-08-16T02:09:20Z
status: fresh
freshness_delta: 958 days
next_expected_update: biennial to triennial (survey years)
record_count: 289
date_range: 1974-01-01 to 2024-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Dates mark survey years and are not a continuous annual series.", "State coverage expands over the historical series.", "The state series begins in 1974, four years later than the national series.", "Gini values are coefficients on a zero-to-one scale."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: DOSM via OpenDOSM
---

# OpenDOSM Income Inequality by State

## Status

**Status:** Fresh

**Freshness:** 958 days

HTTP 200

## Last checked

2026-08-16 at 02:09:20 UTC.

## File size

The checked resource is 7,618 bytes.

## Provenance

The Department of Statistics Malaysia publishes this dataset through OpenDOSM as direct CSV and Parquet downloads:

- `https://storage.dosm.gov.my/hies/hh_inequality_state.csv`
- `https://storage.dosm.gov.my/hies/hh_inequality_state.parquet`

## Coverage

The dataset covers 16 Malaysian state-level areas, with historical coverage varying by survey year from 1974-01-01 through 2024-01-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `state` | string | Malaysian state or federal territory. |
| `date` | date | Observation date in YYYY-MM-DD format. |
| `gini` | number | Gini coefficient reported by the source. |

## Known quirks

- Dates mark survey years and are not a continuous annual series.
- State coverage expands over the historical series.
- The state series begins in 1974, four years later than the national series.
- Gini values are coefficients on a zero-to-one scale.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.dosm.gov.my/hies/hh_inequality_state.csv" \
  -o /tmp/hh_inequality_state.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: DOSM via OpenDOSM.

## Sample

- [samples/dosm_hh_inequality_state.csv](../samples/dosm_hh_inequality_state.csv)
- [samples/dosm_hh_inequality_state.json](../samples/dosm_hh_inequality_state.json)
