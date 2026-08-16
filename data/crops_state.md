---
dataset_id: dgm_crops_state
last_checked: 2026-08-16T02:09:20Z
status: stale
freshness_delta: 1688 days
next_expected_update: overdue
record_count: 864
date_range: 2017-01-01 to 2022-01-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Annual dates use 1 January.", "Malaysia aggregate rows coexist with state rows and must not be summed together.", "Planted area is measured in hectares and production in metric tonnes.", "W.P. Putrajaya is absent because it has no commercial agriculture; rounded breakdowns may differ from totals."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: MAFS, Department of Agriculture, and DOSM via data.gov.my
---

# data.gov.my Crop Area and Production by State

## Status

**Status:** Stale

**Freshness:** 1688 days

HTTP 200

## Last checked

2026-08-16 at 02:09:20 UTC.

## File size

The checked resource is 37,398 bytes.

## Provenance

Department of Agriculture Malaysia publishes this dataset through data.gov.my as direct CSV and
Parquet downloads:

- `https://storage.data.gov.my/agriculture/crops_state.csv`
- `https://storage.data.gov.my/agriculture/crops_state.parquet`

Catalogue description: [Production and planted area of crops by state from 2017 to 2022, broken down by crop type.](https://data.gov.my/data-catalogue/crops_state).

## Coverage

The dataset covers Malaysia (national and 15 state-level areas) from 2017-01-01 through 2022-01-01.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `state` | string | One of 16 states, or Malaysia. Note that there is no data for W.P. Putrajaya, due to the lack of commercial agriculture in the state. |
| `date` | date | The date in YYYY-MM-DD format, with MM-DD set to 01-01 as the data is at annual frequency |
| `crop_type` | string | The type of crop in snake case, covering cash crops, industrial crops, coconut, paddy, flowers, herbs, spices, fruits and vegetables |
| `planted_area` | number | The total planted area of the crop in hectares |
| `production` | number | The total production of the crop in metric tonnes |

## Known quirks

- Annual dates use 1 January.
- Malaysia aggregate rows coexist with state rows and must not be summed together.
- Planted area is measured in hectares and production in metric tonnes.
- W.P. Putrajaya is absent because it has no commercial agriculture; rounded breakdowns may differ from totals.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.data.gov.my/agriculture/crops_state.csv" \
  -o /tmp/crops_state.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence, as stated on the
official catalogue page.

Attribution: MAFS, Department of Agriculture, and DOSM via data.gov.my.

## Sample

- [samples/dgm_crops_state.csv](../samples/dgm_crops_state.csv)
- [samples/dgm_crops_state.json](../samples/dgm_crops_state.json)
