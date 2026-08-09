---
dataset_id: dgm_registrations_type_fuel
last_checked: 2026-08-09T05:30:41Z
last_checked: 2026-08-09T05:30:41Z
status: unknown-freshness
freshness_delta: unknown
next_expected_update: monthly
record_count: 10763
schema_version: unknown
schema_drift: none
known_quirks: ["Official catalogue caveat: This dataset captures the registration of vehicles, not their sale, import, or any other transaction. Therefore, if a vehicle is not registered for use on the road, it will not be counted in this dataset (e.g. vehicles purchased purely for private display). Furthermore, users should note that the dataset includes rows for 'all_types' and 'all_fuels' to facilitate top-level comparisons; these should not be double-counted with the breakdown rows."]
breaking_changes: []
licence: Open Government Licence (Malaysia)
attribution: Road Transport Department Malaysia and Ministry of Transport via data.gov.my
---

# Monthly Vehicle Registrations by Vehicle and Fuel Type

## Status

**Status:** Unknown freshness

**Freshness:** unknown

HTTP 200

## Last checked

2026-08-09 at 05:30:41 UTC.

## File size

The checked resource is 894,701 bytes.

## Provenance

Road Transport Department Malaysia and Ministry of Transport publishes this dataset through data.gov.my (OpenAPI).

- Source: https://api.data.gov.my/data-catalogue?id=registrations_type_fuel
- [Official catalogue metadata](https://data.gov.my/data-catalogue/registrations_type_fuel)

## Coverage

Malaysia.

## Schema

Refer to the [official catalogue field definitions](https://data.gov.my/data-catalogue/registrations_type_fuel) before analysis. The machine-readable envelope records fields observed from the source.

## Known quirks

- Official catalogue caveat: This dataset captures the registration of vehicles, not their sale, import, or any other transaction. Therefore, if a vehicle is not registered for use on the road, it will not be counted in this dataset (e.g. vehicles purchased purely for private display). Furthermore, users should note that the dataset includes rows for 'all_types' and 'all_fuels' to facilitate top-level comparisons; these should not be double-counted with the breakdown rows.

## Breaking changes

None observed.

## Reproducibility

    curl -sS --max-time 30 "https://api.data.gov.my/data-catalogue?id=registrations_type_fuel" | head

## Licence

Licensed under Open Government Licence (Malaysia).
Attribution: Road Transport Department Malaysia and Ministry of Transport via data.gov.my.
