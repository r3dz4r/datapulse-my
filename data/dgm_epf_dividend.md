---
dataset_id: dgm_epf_dividend
last_checked: 2026-08-07T07:25:52Z
status: fresh
freshness_delta: 159 days
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

## Status

**Status:** Fresh

**Freshness:** 159 days

HTTP 200

## Last checked

2026-08-07 at 07:25:52 UTC.

## File size

The checked resource is 1,259 bytes.

## Provenance

The Employees Provident Fund publishes this dataset through data.gov.my as
direct CSV and Parquet downloads:

- `https://storage.data.gov.my/welfare/epf_dividend.csv`
- `https://storage.data.gov.my/welfare/epf_dividend.parquet`

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
