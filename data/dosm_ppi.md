---
dataset_id: dosm_ppi
last_checked: 2026-08-05T14:31:11Z
status: fresh
freshness_delta: 8 days
next_expected_update: monthly
record_count: 581
date_range: 2010-01-01 to 2026-06-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Monthly dates use the first day of the month.", "Absolute index values and percentage growth rates share rows selected by series.", "The seasonally adjusted field is not populated for every row.", "The latest three months may be revised."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: DOSM via OpenDOSM
---

# OpenDOSM Monthly Producer Price Index

## Status

**Status:** Fresh

**Freshness:** 8 days

HTTP 200

## Last checked

2026-08-05 at 14:31:11 UTC.

## File size

The checked resource is 16,784 bytes.

## Provenance

Department of Statistics Malaysia publishes this dataset through OpenDOSM as direct CSV and
Parquet downloads:

- `https://storage.dosm.gov.my/ppi/ppi.csv`
- `https://storage.dosm.gov.my/ppi/ppi.parquet`

Catalogue description: [the monthly headline producer price index with seasonal-adjustment fields](https://open.dosm.gov.my/data-catalogue/ppi).

## Coverage

The dataset covers Malaysia (national) from 2010-01-01 through 2026-06-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `series` | string | Series type selecting absolute values or a growth-rate transformation. |
| `date` | date | Observation date in YYYY-MM-DD format. |
| `index` | number | Index level or growth value selected by series. |
| `index_sa` | number | Seasonally adjusted index value, where available. |

## Known quirks

- Monthly dates use the first day of the month.
- Absolute index values and percentage growth rates share rows selected by series.
- The seasonally adjusted field is not populated for every row.
- The latest three months may be revised.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.dosm.gov.my/ppi/ppi.csv" \
  -o /tmp/ppi.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence, as stated on the
official catalogue page.

Attribution: DOSM via OpenDOSM.

## Sample

- [samples/dosm_ppi.csv](../samples/dosm_ppi.csv)
- [samples/dosm_ppi.json](../samples/dosm_ppi.json)
