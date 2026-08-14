---
dataset_id: dosm_cpi_state
last_checked: 2026-08-14T04:59:27Z
status: aging
freshness_delta: 74 days
next_expected_update: monthly
record_count: 44352
date_range: 2010-01-01 to 2026-06-01
schema_version: 1.0
schema_drift: none
known_quirks: ["division uses overall or two-digit codes 01-13", "dates use the first day of each month"]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: DOSM via OpenDOSM
---

# OpenDOSM Monthly CPI by State and Division

## Status

**Status:** Aging

**Freshness:** 74 days

HTTP 200

## Last checked

2026-08-14 at 04:59:27 UTC.

## File size

The checked resource is 1,328,705 bytes.

## Provenance

DOSM publishes this dataset through OpenDOSM as direct CSV and Parquet
downloads:

- `https://storage.dosm.gov.my/cpi/cpi_2d_state.csv`
- `https://storage.dosm.gov.my/cpi/cpi_2d_state.parquet`

These files use the `storage.dosm.gov.my` subdomain, which differs from the
`storage.data.gov.my` host used by the crime district dataset.

## Coverage

The dataset contains monthly observations from 2010-01-01 through 2026-06-01,
covering 16 years of data. It covers 16 state-level areas: 13 states (Johor,
Kedah, Kelantan, Melaka, Negeri Sembilan, Pahang, Perak, Perlis, Pulau Pinang,
Sabah, Sarawak, Selangor, and Terengganu) and three federal territories (W.P.
Kuala Lumpur, W.P. Labuan, and W.P. Putrajaya).

Each area has observations for 14 divisions: `overall` plus the 13 main CPI
groups coded `01` through `13`.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `state` | string | One of 16 state or federal-territory labels. |
| `date` | date | Monthly observation date in `YYYY-MM-DD` format. |
| `division` | string | `overall` or a two-digit CPI main-group code from `01` to `13`. |
| `index` | number | Consumer Price Index value for the area, month, and division. |

## Division codes

- `overall` = Aggregate across all divisions
- `01` = Food and non-alcoholic beverages
- `02` = Alcoholic beverages and tobacco
- `03` = Clothing and footwear
- `04` = Housing, water, electricity, gas and other fuels
- `05` = Furnishings, household equipment and routine household maintenance
- `06` = Health
- `07` = Transport
- `08` = Information and communication
- `09` = Recreation, sport and culture
- `10` = Education services
- `11` = Restaurants and accommodation services
- `12` = Insurance and financial services
- `13` = Personal care, social protection, and miscellaneous goods and services

## Known quirks

- Monthly dates use the first day of each month.
- Division codes must remain strings so leading zeroes are preserved.
- Aggregate `overall` rows coexist with division-specific rows.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.dosm.gov.my/cpi/cpi_2d_state.csv" \
  -o /tmp/cpi.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: DOSM via OpenDOSM.

## Sample

- [samples/dosm_cpi_state.csv](../samples/dosm_cpi_state.csv)
- [samples/dosm_cpi_state.json](../samples/dosm_cpi_state.json)
