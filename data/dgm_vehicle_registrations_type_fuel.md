---
dataset_id: dgm_vehicle_registrations_type_fuel
last_checked: 2026-08-02T17:18:27Z
status: current
freshness_delta: 23 days since file update
next_expected_update: monthly
record_count: 10763
date_range: 2000-01-01 to 2026-06-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Monthly dates use 1 January.", "All-types and all-fuels aggregates coexist with detailed rows.", "Not every vehicle-type and fuel combination is present in every month.", "Green diesel is a separate fuel code."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: Road Transport Department Malaysia via data.gov.my
---

# data.gov.my Monthly Vehicle Registrations by Type and Fuel

## Provenance

The Road Transport Department Malaysia publishes this dataset through
data.gov.my as direct CSV and Parquet downloads:

- `https://storage.data.gov.my/transportation/registrations_type_fuel.csv`
- `https://storage.data.gov.my/transportation/registrations_type_fuel.parquet`

## Status

**Status:** Current

**Freshness:** File last updated 2026-07-10; observations extend through 2026-06-01

**Refresh frequency:** Monthly

The CSV endpoint returned HTTP 200 and its expected 324,291-byte file. It
contains 10,763 data rows.

## Last checked

2026-08-02 by direct HTTP HEAD request and CSV download.

## Coverage

The dataset covers monthly Malaysian vehicle registrations from 2000-01-01
through 2026-06-01 across seven vehicle-type and seven fuel codes.

## Schema

| Field | Type | Description |
| --- | --- | --- |
| `date` | date | Monthly observation date in YYYY-MM-DD format. |
| `type` | string | Vehicle-type code. |
| `fuel` | string | Fuel-type code. |
| `registrations` | integer | Number of newly registered vehicles. |

## Known quirks

- Monthly dates use the first day of the month.
- `all_types` and `all_fuels` aggregates coexist with detailed rows and can
  cause double counting.
- Not every type/fuel combination appears in every month.
- `greendiesel` is distinct from the `diesel` code.

## Breaking changes

None observed.

## Reproducibility

```sh
curl -sS --max-time 30 \
  "https://storage.data.gov.my/transportation/registrations_type_fuel.csv" \
  -o /tmp/registrations_type_fuel.csv
```

## Licence

Licensed under the Creative Commons Attribution 4.0 licence.

Attribution: Road Transport Department Malaysia via data.gov.my.

## Sample

- [samples/dgm_vehicle_registrations_type_fuel.csv](../samples/dgm_vehicle_registrations_type_fuel.csv)
- [samples/dgm_vehicle_registrations_type_fuel.json](../samples/dgm_vehicle_registrations_type_fuel.json)
