---
dataset_id: dosm_lfs_qtr
last_checked: 2026-08-14T04:59:27Z
status: stale
freshness_delta: 409 days
next_expected_update: overdue
record_count: 63
date_range: 2010-01-01 to 2025-07-01
schema_version: 1.0
schema_drift: none
known_quirks: ["quarterly dates use the first day of each quarter", "levels and rates share each row"]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: DOSM via OpenDOSM
---

# OpenDOSM Quarterly Labour Force Statistics

## Status

**Status:** Stale

**Freshness:** 409 days

HTTP 200

## Last checked

2026-08-14 at 04:59:27 UTC.

## File size

The checked resource is 3,470 bytes.

## Provenance

DOSM publishes this national dataset through OpenDOSM as direct CSV and
Parquet downloads:

- `https://storage.dosm.gov.my/labour/lfs_qtr.csv`
- `https://storage.dosm.gov.my/labour/lfs_qtr.parquet`

## Coverage

The dataset contains national quarterly labour-force observations for
Malaysia from 2010 Q1 through 2025 Q3. It has no subnational geographic field.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `date` | date | Quarter start date in `YYYY-MM-DD` format. |
| `lf` | number | Labour force level. |
| `lf_employed` | number | Employed labour force level. |
| `lf_unemployed` | number | Unemployed labour force level. |
| `lf_outside` | number | Population outside the labour force. |
| `p_rate` | number | Labour force participation rate. |
| `ep_ratio` | number | Employment-to-population ratio. |
| `u_rate` | number | Unemployment rate. |

## Known quirks

- Quarterly dates use the first day of January, April, July, or October.
- Labour-force levels and rates are stored together; consumers must retain
  their distinct units when reshaping the data.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.dosm.gov.my/labour/lfs_qtr.csv" \
  -o /tmp/lfs_qtr.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: DOSM via OpenDOSM.

## Sample

- [samples/dosm_lfs_qtr.csv](../samples/dosm_lfs_qtr.csv)
- [samples/dosm_lfs_qtr.json](../samples/dosm_lfs_qtr.json)
