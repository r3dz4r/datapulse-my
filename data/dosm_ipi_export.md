---
dataset_id: dosm_ipi_export
last_checked: 2026-08-02T16:47:48Z
status: current
freshness_delta: 13 days since file update
next_expected_update: monthly
record_count: 5174
date_range: 2015-01-01 to 2026-05-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Monthly dates use the first day of the month.", "MSIC division codes must remain strings.", "Absolute index values and percentage growth rates share the index column.", "Seasonally adjusted data is not provided."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: DOSM via OpenDOSM
---

# OpenDOSM IPI for Export-Oriented Divisions

## Provenance

Department of Statistics Malaysia publishes this dataset through OpenDOSM as direct CSV and
Parquet downloads:

- `https://storage.dosm.gov.my/ipi/ipi_export.csv`
- `https://storage.dosm.gov.my/ipi/ipi_export.parquet`

Catalogue description: [monthly industrial production for export-oriented MSIC divisions](https://open.dosm.gov.my/data-catalogue/ipi_export).

## Status

**Status:** Current

**Freshness:** File last updated 2026-07-20; observations end on 2026-05-01

**Refresh frequency:** Monthly

The CSV endpoint returned HTTP 200 and its expected 155,817-byte file. It
contains 5,174 data rows.

## Last checked

2026-08-02 by direct HTTP HEAD request and CSV download.

## Coverage

The dataset covers Malaysia (national) from 2015-01-01 through 2026-05-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `series` | string | Series type selecting absolute values or a growth-rate transformation. |
| `date` | date | Observation date in YYYY-MM-DD format. |
| `division` | string | CPI or MSIC division code, or overall aggregate. |
| `index` | number | Index level or growth value selected by series. |

## Known quirks

- Monthly dates use the first day of the month.
- MSIC division codes must remain strings.
- Absolute index values and percentage growth rates share the index column.
- Seasonally adjusted data is not provided.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.dosm.gov.my/ipi/ipi_export.csv" \
  -o /tmp/ipi_export.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence, as stated on the
official catalogue page.

Attribution: DOSM via OpenDOSM.

## Sample

- [samples/dosm_ipi_export.csv](../samples/dosm_ipi_export.csv)
- [samples/dosm_ipi_export.json](../samples/dosm_ipi_export.json)
