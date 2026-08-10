---
dataset_id: dgm_water_access
last_checked: 2026-08-10T10:07:26Z
status: stale
freshness_delta: 1682 days
next_expected_update: overdue
record_count: 1035
date_range: 2000-01-01 to 2022-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Annual dates use 1 January.", "Overall, urban, and rural rows coexist and must not be summed together.", "The measure is connected treated-piped-water supply, not all forms of access to public water.", "W.P. Kuala Lumpur and W.P. Putrajaya are included under Selangor."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: SPAN and NRES via data.gov.my
---

# data.gov.my Access to Treated Water by State & Strata

## Status

**Status:** Stale

**Freshness:** 1682 days

HTTP 200

## Last checked

2026-08-10 at 10:07:26 UTC.

## File size

The checked resource is 32,915 bytes.

## Provenance

National Water Services Commission publishes this dataset through data.gov.my as direct CSV and
Parquet downloads:

- `https://storage.data.gov.my/water/water_access.csv`
- `https://storage.data.gov.my/water/water_access.parquet`

Catalogue description: [Annual access of households to treated piped water by state and strata.](https://data.gov.my/data-catalogue/water_access).

## Coverage

The dataset covers Malaysia (national and 14 reported state-level areas) from 2000-01-01 through 2022-01-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `state` | string | One of 16 states, or Malaysia |
| `strata` | string | Either overall ('overall'), urban ('urban') or rural ('rural') |
| `date` | date | The date in YYYY-MM-DD format, with MM-DD set to 01-01 as the data is at annual frequency |
| `proportion` | number | Proportion of households with access to treated piped water, expressed as a percentage |

## Known quirks

- Annual dates use 1 January.
- Overall, urban, and rural rows coexist and must not be summed together.
- The measure is connected treated-piped-water supply, not all forms of access to public water.
- W.P. Kuala Lumpur and W.P. Putrajaya are included under Selangor.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.data.gov.my/water/water_access.csv" \
  -o /tmp/water_access.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence, as stated on the
official catalogue page.

Attribution: SPAN and NRES via data.gov.my.

## Sample

- [samples/dgm_water_access.csv](../samples/dgm_water_access.csv)
- [samples/dgm_water_access.json](../samples/dgm_water_access.json)
