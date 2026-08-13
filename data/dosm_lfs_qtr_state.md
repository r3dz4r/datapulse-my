---
dataset_id: dosm_lfs_qtr_state
last_checked: 2026-08-11T14:21:08Z
status: stale
freshness_delta: 406 days
next_expected_update: overdue
record_count: 560
date_range: 2017-01-01 to 2025-07-01
schema_version: 1.0
schema_drift: none
known_quirks: ["quarterly dates use the first day of each quarter", "covers 16 state-level areas", "does not include ep_ratio"]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: DOSM via OpenDOSM
---

# OpenDOSM Quarterly Labour Force Statistics by State

## Status

**Status:** Stale

**Freshness:** 406 days

HTTP 200

## Last checked

2026-08-11 at 14:21:08 UTC.

## File size

The checked resource is 29,704 bytes.

## Provenance

DOSM publishes this dataset through OpenDOSM as direct CSV and Parquet
downloads:

- `https://storage.dosm.gov.my/labour/lfs_qtr_state.csv`
- `https://storage.dosm.gov.my/labour/lfs_qtr_state.parquet`

## Coverage

The dataset contains quarterly observations from 2017 Q1 through 2025 Q3 for
16 state-level areas: 13 states and W.P. Kuala Lumpur, W.P. Labuan, and W.P.
Putrajaya. There is no Malaysia aggregate row.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `date` | date | Quarter start date in `YYYY-MM-DD` format. |
| `state` | string | One of 16 state or federal-territory labels. |
| `lf` | number | Labour force level. |
| `lf_employed` | number | Employed labour force level. |
| `lf_unemployed` | number | Unemployed labour force level. |
| `lf_outside` | number | Population outside the labour force. |
| `p_rate` | number | Labour force participation rate. |
| `u_rate` | number | Unemployment rate. |

## Known quirks

- Quarterly dates use the first day of January, April, July, or October.
- Unlike the national quarterly file, this state file has no `ep_ratio`
  column.
- Labour-force levels and rates are stored together in each row.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.dosm.gov.my/labour/lfs_qtr_state.csv" \
  -o /tmp/lfs_qtr_state.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: DOSM via OpenDOSM.

## Sample

- [samples/dosm_lfs_qtr_state.csv](../samples/dosm_lfs_qtr_state.csv)
- [samples/dosm_lfs_qtr_state.json](../samples/dosm_lfs_qtr_state.json)
