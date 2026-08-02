---
dataset_id: dosm_gdp_annual_nominal_supply
last_checked: 2026-08-02T16:47:48Z
status: current
freshness_delta: 11 days since file update
next_expected_update: annual
record_count: 147
date_range: 2015-01-01 to 2025-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Annual dates use 1 January.", "Sector p0 is the overall aggregate and coexists with component sectors.", "Absolute values and year-on-year growth rates share the value column.", "Values for 2024 and 2025 may be revised."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: DOSM via OpenDOSM
---

# OpenDOSM Annual Nominal GDP by Supply Sector

## Provenance

Department of Statistics Malaysia publishes this dataset through OpenDOSM as direct CSV and
Parquet downloads:

- `https://storage.dosm.gov.my/gdp/gdp_annual_nominal_supply.csv`
- `https://storage.dosm.gov.my/gdp/gdp_annual_nominal_supply.parquet`

Catalogue description: [annual GDP at current prices for Malaysia's main economic sectors](https://open.dosm.gov.my/data-catalogue/gdp_annual_nominal_supply).

## Status

**Status:** Current

**Freshness:** File last updated 2026-07-22; observations end on 2025-01-01

**Refresh frequency:** Annual

The CSV endpoint returned HTTP 200 and its expected 4,305-byte file. It
contains 147 data rows.

## Last checked

2026-08-02 by direct HTTP HEAD request and CSV download.

## Coverage

The dataset covers Malaysia (national) from 2015-01-01 through 2025-01-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `series` | string | Series type selecting absolute values or a growth-rate transformation. |
| `date` | date | Observation date in YYYY-MM-DD format. |
| `sector` | string | Economic-sector code; p0 is the overall aggregate. |
| `value` | number | Observed value; units depend on the dataset and series. |

## Known quirks

- Annual dates use 1 January.
- Sector p0 is the overall aggregate and coexists with component sectors.
- Absolute values and year-on-year growth rates share the value column.
- Values for 2024 and 2025 may be revised.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.dosm.gov.my/gdp/gdp_annual_nominal_supply.csv" \
  -o /tmp/gdp_annual_nominal_supply.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence, as stated on the
official catalogue page.

Attribution: DOSM via OpenDOSM.

## Sample

- [samples/dosm_gdp_annual_nominal_supply.csv](../samples/dosm_gdp_annual_nominal_supply.csv)
- [samples/dosm_gdp_annual_nominal_supply.json](../samples/dosm_gdp_annual_nominal_supply.json)
