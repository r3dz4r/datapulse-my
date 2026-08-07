---
dataset_id: dosm_gdp_gni_annual_nominal
last_checked: 2026-08-07T07:25:52Z
status: fresh
freshness_delta: 15 days
next_expected_update: annual
record_count: 157
date_range: 1947-01-01 to 2025-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Annual dates use 1 January.", "The 1954 observation is unavailable.", "Historical geographic scope changes before 1963.", "Absolute values and year-on-year growth rates share the measure columns."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: DOSM via OpenDOSM
---

# OpenDOSM Annual Nominal GDP and GNI

## Status

**Status:** Fresh

**Freshness:** 15 days

HTTP 200

## Last checked

2026-08-07 at 07:25:52 UTC.

## File size

The checked resource is 6,921 bytes.

## Provenance

Department of Statistics Malaysia publishes this dataset through OpenDOSM as direct CSV and
Parquet downloads:

- `https://storage.dosm.gov.my/gdp/gdp_gni_annual_nominal.csv`
- `https://storage.dosm.gov.my/gdp/gdp_gni_annual_nominal.parquet`

Catalogue description: [a long annual series of nominal GDP, GNI, and per-capita values](https://open.dosm.gov.my/data-catalogue/gdp_gni_annual_nominal).

## Coverage

The dataset covers Malaysia (national; historical boundaries vary) from 1947-01-01 through 2025-01-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `series` | string | Series type selecting absolute values or a growth-rate transformation. |
| `date` | date | Observation date in YYYY-MM-DD format. |
| `gdp` | number | Gross domestic product value. |
| `gni` | number | Gross national income value. |
| `gdp_capita` | number | Gross domestic product per capita. |
| `gni_capita` | number | Gross national income per capita. |

## Known quirks

- Annual dates use 1 January.
- The 1954 observation is unavailable.
- Historical geographic scope changes before 1963.
- Absolute values and year-on-year growth rates share the measure columns.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.dosm.gov.my/gdp/gdp_gni_annual_nominal.csv" \
  -o /tmp/gdp_gni_annual_nominal.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence, as stated on the
official catalogue page.

Attribution: DOSM via OpenDOSM.

## Sample

- [samples/dosm_gdp_gni_annual_nominal.csv](../samples/dosm_gdp_gni_annual_nominal.csv)
- [samples/dosm_gdp_gni_annual_nominal.json](../samples/dosm_gdp_gni_annual_nominal.json)
