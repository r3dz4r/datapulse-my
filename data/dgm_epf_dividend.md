---
dataset_id: dgm_epf_dividend
last_checked: 2026-08-02T17:18:27Z
status: current
freshness_delta: 155 days since file update
next_expected_update: annual
record_count: 74
date_range: 1952-01-01 to 2025-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Annual dates use 1 January.", "Dividend values are percentages.", "Shariah dividend values begin only in 2017.", "Earlier Shariah values are blank rather than zero."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: Employees Provident Fund via data.gov.my
---

# data.gov.my Annual EPF Dividend Rates

## Provenance

The Employees Provident Fund publishes this dataset through data.gov.my as
direct CSV and Parquet downloads:

- `https://storage.data.gov.my/welfare/epf_dividend.csv`
- `https://storage.data.gov.my/welfare/epf_dividend.parquet`

## Status

**Status:** Current

**Freshness:** File last updated 2026-02-28; observations extend through 2025

**Refresh frequency:** Annual

The CSV endpoint returned HTTP 200 and its expected 1,259-byte file. It
contains 74 data rows.

## Last checked

2026-08-02 by direct HTTP HEAD request and CSV download.

## Coverage

The dataset covers annual EPF conventional dividend rates from 1952 through
2025 and Shariah dividend rates from 2017 through 2025.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `date` | date | Annual observation date in YYYY-MM-DD format. |
| `conventional` | number | Conventional account dividend rate in percent. |
| `shariah` | number or null | Shariah account dividend rate in percent. |

## Known quirks

- Annual dates use 1 January.
- Dividend values are percentages, not proportions.
- Shariah dividend rates begin in 2017.
- The 65 earlier Shariah cells are blank and must not be interpreted as zero.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.data.gov.my/welfare/epf_dividend.csv" \
  -o /tmp/epf_dividend.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: Employees Provident Fund via data.gov.my.

## Sample

- [samples/dgm_epf_dividend.csv](../samples/dgm_epf_dividend.csv)
- [samples/dgm_epf_dividend.json](../samples/dgm_epf_dividend.json)
