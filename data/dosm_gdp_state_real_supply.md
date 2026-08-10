---
dataset_id: dosm_gdp_state_real_supply
last_checked: 2026-08-09T08:37:11Z
status: aging
freshness_delta: 585 days
next_expected_update: annual
record_count: 2163
date_range: 2015-01-01 to 2025-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Supra is a supra-state aggregate, not a state", "there is no Malaysia geographic label", "p0 includes p1 through p6"]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: DOSM via OpenDOSM
---

# OpenDOSM Annual Real GDP by State and Sector

## Status

**Status:** Aging

**Freshness:** 585 days

HTTP 200

## Last checked

2026-08-09 at 08:37:11 UTC.

## File size

The checked resource is 79,740 bytes.

## Provenance

DOSM publishes this dataset through OpenDOSM as direct CSV and Parquet
downloads:

- `https://storage.dosm.gov.my/gdp/gdp_state_real_supply.csv`
- `https://storage.dosm.gov.my/gdp/gdp_state_real_supply.parquet`

Both files use the `storage.dosm.gov.my` subdomain.

## Coverage

The dataset contains 11 years of annual observations from 2015-01-01 through
2025-01-01. It has 17 geographic labels: 13 states, three federal territories
(W.P. Kuala Lumpur, W.P. Labuan, and W.P. Putrajaya), and `Supra`.

## Geographic labels

`Supra` is a supra-state aggregate label, not a state. There is no `Malaysia`
label in this dataset.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `series` | string | `abs` or `growth_yoy`. |
| `date` | date | Annual observation date in `YYYY-MM-DD` format. |
| `state` | string | One of 17 geographic labels, including the `Supra` aggregate. |
| `sector` | string | Sector code `p0` through `p6`. |
| `value` | number | GDP value in the unit defined by `series`. |

## Sector codes

- `p0` = Overall GDP
- `p1` = Agriculture
- `p2` = Mining and quarrying
- `p3` = Manufacturing
- `p4` = Construction
- `p5` = Services
- `p6` = Taxes less subsidies on products

Overall GDP (`p0`) equals the sum of `p1` through `p6`.

## Series types

- `abs` = RM million at constant 2015 prices
- `growth_yoy` = year-on-year growth %

## Known quirks

- Annual dates use the first day of the year.
- `Supra` must be treated as a supra-state aggregate, not as a state.
- There is no `Malaysia` geographic label.
- Aggregate `p0` rows coexist with the component-sector `p1` through `p6` rows.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.dosm.gov.my/gdp/gdp_state_real_supply.csv" \
  -o /tmp/gdp_state_real_supply.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: DOSM via OpenDOSM.

## Sample

- [samples/dosm_gdp_state_real_supply.csv](../samples/dosm_gdp_state_real_supply.csv)
- [samples/dosm_gdp_state_real_supply.json](../samples/dosm_gdp_state_real_supply.json)
