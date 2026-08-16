---
dataset_id: doe_mqims
last_checked: 2026-08-14T08:56:22Z
status: browser-dependent
freshness_delta: 2 days
next_expected_update: 2026-09-01
record_count: null
date_range: latest monthly sampling view
schema_version: 1.0
schema_drift: none
known_quirks: ["JavaScript-rendered and requires Camofox", "manual monthly sampling", "MMWQI cells may be empty in the accessibility tree while asynchronous data loads"]
breaking_changes: []
licence: Open Government Licence (Malaysia)
attribution: DOE Malaysia via MyEQMS
---

# DOE MQIMS Marine Water Quality (Manual)

## Status

**Status:** Browser dependent

**Freshness:** 2 days

Camofox unavailable; browser check required

## Last checked

2026-08-14 at 08:56:22 UTC.

## File size

The health snapshot did not report a file size.

## Coverage

The view covers 368 manual marine monitoring stations across Coastal, Estuary,
and Island categories. It publishes the Manual Marine Water Quality Index
(MMWQI) from monthly manual sampling.

## Classification

| Classification | MMWQI range |
| --- | --- |
| Excellent | 90-100 |
| Good | 80-90 |
| Moderate | 50-80 |
| Poor | 0-50 |

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `NO` | integer | Row number. |
| `STATE` | string | Malaysian state. |
| `LOCATION` | string | Marine monitoring location. |
| `CATEGORY` | string | Coastal, Estuary, or Island. |
| `STATION_ID` | string | DOE manual marine station identifier. |
| `MMWQI_SAMPLING_MONTH` | number or null | MMWQI value for the displayed sampling month. |

## Known quirks

- The table is JavaScript-rendered and collection requires Camofox.
- Measurements come from monthly manual sampling rather than continuous
  sensors.
- MMWQI cells may be empty in the accessibility tree while their asynchronous
  data is loading. Samples preserve an observed empty value rather than
  inventing a measurement.

## Breaking changes

None observed.

## Sample

- [samples/doe_mqims.csv](samples/doe_mqims.csv)
- [samples/doe_mqims.json](samples/doe_mqims.json)

## Reproducibility

Open `https://eqms.doe.gov.my/MQIMS/main` in Camofox, wait 12 seconds for the
table to render, capture the accessibility snapshot, and close the tab.

## Licence

Licensed under the Open Government Licence (Malaysia).

Attribution: DOE Malaysia via MyEQMS.
