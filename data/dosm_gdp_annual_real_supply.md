---
dataset_id: dosm_gdp_annual_real_supply
last_checked: 2026-08-10T04:08:14Z
status: aging
freshness_delta: 586 days
next_expected_update: annual
record_count: 147
date_range: 2015-01-01 to 2025-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["annual dates use January 1", "p0 is the overall aggregate", "series mixes absolute values with growth rates"]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: DOSM via OpenDOSM
---

# OpenDOSM Annual Real GDP by Supply Sector

## Status

**Status:** Aging

**Freshness:** 586 days

HTTP 200

## Last checked

2026-08-10 at 04:08:14 UTC.

## File size

The checked resource is 4,276 bytes.

## Provenance

DOSM publishes this national dataset through OpenDOSM as direct CSV and
Parquet downloads:

- `https://storage.dosm.gov.my/gdp/gdp_annual_real_supply.csv`
- `https://storage.dosm.gov.my/gdp/gdp_annual_real_supply.parquet`

## Coverage

The dataset contains national annual observations for Malaysia from 2015
through 2025. It has no subnational geographic field. Seven supply-sector
codes cover overall GDP and six components.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `series` | string | `abs` or `growth_yoy`. |
| `date` | date | Annual observation date in `YYYY-MM-DD` format. |
| `sector` | string | Supply-sector code `p0` through `p6`. |
| `value` | number | GDP value in the unit defined by `series`. |

## Sector codes

- `p0` = Overall GDP
- `p1` = Agriculture
- `p2` = Mining and quarrying
- `p3` = Manufacturing
- `p4` = Construction
- `p5` = Services
- `p6` = Taxes less subsidies on products

## Known quirks

- Annual dates use January 1 as the reporting date.
- Aggregate `p0` rows coexist with component-sector rows.
- Absolute values and year-on-year growth rates share the `value` column.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.dosm.gov.my/gdp/gdp_annual_real_supply.csv" \
  -o /tmp/gdp_annual_real_supply.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: DOSM via OpenDOSM.

## Sample

- [samples/dosm_gdp_annual_real_supply.csv](../samples/dosm_gdp_annual_real_supply.csv)
- [samples/dosm_gdp_annual_real_supply.json](../samples/dosm_gdp_annual_real_supply.json)
