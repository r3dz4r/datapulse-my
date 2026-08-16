---
dataset_id: dgm_almanak_astronomi
last_checked: 2026-08-16T02:09:20Z
status: fresh
freshness_delta: 1 days
next_expected_update: daily
record_count: 538
schema_version: unknown
schema_drift: none
known_quirks: ["Official catalogue caveat: The primary caveats for this data are that while the celestial timings are scientifically precise, actual visibility is heavily dependent on Malaysia’s unpredictable tropical weather, cloud cover, and significant light pollution in urban areas which can obscure faint phenomena like meteor showers. Additionally, because the calculations are localized specifically to Kuala Lumpur's coordinates, residents in Sabah and Sarawak may experience slight timing variations, and the dataset itself contains technical formatting inconsistencies such as unquoted commas that may require data cleaning for accurate digital processing."]
breaking_changes: []
licence: Open Government Licence (Malaysia)
attribution: Malaysian Meteorological Department via data.gov.my
---

# Astronomy Almanac

## Status

**Status:** Fresh

**Freshness:** 1 days

HTTP 200

## Last checked

2026-08-16 at 02:09:20 UTC.

## File size

The checked resource is 116,726 bytes.

## Provenance

Malaysian Meteorological Department publishes this dataset through data.gov.my (OpenAPI).

- Source: https://api.data.gov.my/data-catalogue?id=almanak_astronomi
- [Official catalogue metadata](https://data.gov.my/data-catalogue/almanak_astronomi)

## Coverage

Malaysia.

## Schema

Refer to the [official catalogue field definitions](https://data.gov.my/data-catalogue/almanak_astronomi) before analysis. The machine-readable envelope records fields observed from the source.

## Known quirks

- Official catalogue caveat: The primary caveats for this data are that while the celestial timings are scientifically precise, actual visibility is heavily dependent on Malaysia’s unpredictable tropical weather, cloud cover, and significant light pollution in urban areas which can obscure faint phenomena like meteor showers. Additionally, because the calculations are localized specifically to Kuala Lumpur's coordinates, residents in Sabah and Sarawak may experience slight timing variations, and the dataset itself contains technical formatting inconsistencies such as unquoted commas that may require data cleaning for accurate digital processing.

## Breaking changes

None observed.

## Reproducibility

    curl -sS --max-time 30 "https://api.data.gov.my/data-catalogue?id=almanak_astronomi" | head

## Licence

Licensed under Open Government Licence (Malaysia).
Attribution: Malaysian Meteorological Department via data.gov.my.
