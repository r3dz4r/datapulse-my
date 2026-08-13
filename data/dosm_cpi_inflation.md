---
dataset_id: dosm_cpi_inflation
last_checked: 2026-08-11T14:21:08Z
status: aging
freshness_delta: 71 days
next_expected_update: monthly
record_count: 7798
date_range: 1980-02-01 to 2026-06-01
schema_version: 1.0
schema_drift: none
known_quirks: ["monthly dates use the first day of the month", "division codes must remain strings", "early observations contain unavailable inflation values"]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: DOSM via OpenDOSM
---

# OpenDOSM Monthly CPI Inflation by Division

## Status

**Status:** Aging

**Freshness:** 71 days

HTTP 200

## Last checked

2026-08-11 at 14:21:08 UTC.

## File size

The checked resource is 167,359 bytes.

## Provenance

DOSM publishes this national dataset through OpenDOSM as direct CSV and
Parquet downloads:

- `https://storage.dosm.gov.my/cpi/cpi_2d_inflation.csv`
- `https://storage.dosm.gov.my/cpi/cpi_2d_inflation.parquet`

## Coverage

The dataset contains national monthly CPI inflation observations for Malaysia
from February 1980 through June 2026. It has no subnational geographic field.
Rows cover `overall` and 13 two-digit CPI divisions.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `date` | date | Month start date in `YYYY-MM-DD` format. |
| `division` | string | `overall` or CPI division code `01` through `13`. |
| `inflation_yoy` | number | Year-on-year inflation rate; nullable. |
| `inflation_mom` | number | Month-on-month inflation rate; nullable. |

## Known quirks

- Monthly dates use the first day of each month.
- Division codes must remain strings so leading zeroes are preserved.
- Historical coverage differs by measure and division: `inflation_yoy` has
  1,618 blank cells and `inflation_mom` has 1,464 blank cells.
- Aggregate `overall` rows coexist with division-specific rows.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.dosm.gov.my/cpi/cpi_2d_inflation.csv" \
  -o /tmp/cpi_2d_inflation.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: DOSM via OpenDOSM.

## Sample

- [samples/dosm_cpi_inflation.csv](../samples/dosm_cpi_inflation.csv)
- [samples/dosm_cpi_inflation.json](../samples/dosm_cpi_inflation.json)
