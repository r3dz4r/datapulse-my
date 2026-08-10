---
dataset_id: dgm_vehicle_registrations_type_fuel
last_checked: 2026-08-09T08:37:11Z
status: fresh
freshness_delta: 0 days
next_expected_update: monthly
record_count: 10801
date_range: 2000-01-01 to 2026-06-01
schema_version: 1.0
schema_drift: none
known_quirks: ["Monthly dates use 1 January.", "All-types and all-fuels aggregates coexist with detailed rows.", "Not every vehicle-type and fuel combination is present in every month.", "Green diesel is a separate fuel code."]
breaking_changes: []
licence: Creative Commons Attribution 4.0
attribution: Road Transport Department Malaysia via data.gov.my
---

# data.gov.my Monthly Vehicle Registrations by Type and Fuel

## Status

**Status:** Fresh

**Freshness:** 0 days

HTTP 200

## Last checked

2026-08-09 at 08:37:11 UTC.

## File size

The checked resource is 325,446 bytes.

## Provenance

The Road Transport Department Malaysia publishes this dataset through
data.gov.my as direct CSV and Parquet downloads:

- `https://storage.data.gov.my/transportation/registrations_type_fuel.csv`
- `https://storage.data.gov.my/transportation/registrations_type_fuel.parquet`

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
