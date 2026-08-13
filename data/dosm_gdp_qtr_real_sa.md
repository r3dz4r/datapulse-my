---
dataset_id: dosm_gdp_qtr_real_sa
last_checked: 2026-08-13T02:46:04Z
status: aging
freshness_delta: 224 days
next_expected_update: quarterly
record_count: 45
date_range: 2015-01-01 to 2026-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Quarterly dates use the first day of each quarter.", "The series column currently contains only abs.", "Recent observations may be revised."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: DOSM via OpenDOSM
---

# OpenDOSM Quarterly Real GDP (Seasonally Adjusted)

## Status

**Status:** Aging

**Freshness:** 224 days

HTTP 200

## Last checked

2026-08-13 at 02:46:04 UTC.

## File size

The checked resource is 1,098 bytes.

## Provenance

Department of Statistics Malaysia publishes this dataset through OpenDOSM as direct CSV and
Parquet downloads:

- `https://storage.dosm.gov.my/gdp/gdp_qtr_real_sa.csv`
- `https://storage.dosm.gov.my/gdp/gdp_qtr_real_sa.parquet`

Catalogue description: [seasonally adjusted quarterly GDP at constant 2015 prices](https://open.dosm.gov.my/data-catalogue/gdp_qtr_real_sa).

## Coverage

The dataset covers Malaysia (national) from 2015-01-01 through 2026-01-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `series` | string | Series type selecting absolute values or a growth-rate transformation. |
| `date` | date | Observation date in YYYY-MM-DD format. |
| `value` | number | Observed value; units depend on the dataset and series. |

## Known quirks

- Quarterly dates use the first day of each quarter.
- The series column currently contains only abs.
- Recent observations may be revised.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.dosm.gov.my/gdp/gdp_qtr_real_sa.csv" \
  -o /tmp/gdp_qtr_real_sa.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence, as stated on the
official catalogue page.

Attribution: DOSM via OpenDOSM.

## Sample

- [samples/dosm_gdp_qtr_real_sa.csv](../samples/dosm_gdp_qtr_real_sa.csv)
- [samples/dosm_gdp_qtr_real_sa.json](../samples/dosm_gdp_qtr_real_sa.json)
