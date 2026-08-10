---
dataset_id: dgm_usage_metrics_openapi_cumul
last_checked: 2026-08-09T08:37:11Z
last_checked: 2026-08-09T08:37:11Z
status: unknown-freshness
freshness_delta: unknown
next_expected_update: daily
record_count: 30
schema_version: unknown
schema_drift: none
known_quirks: ["Official catalogue caveat: Although the OpenAPI was live from 13 Sep 2023, this dataset only includes API hits from 15 Dec 2023 onwards due to lack of disaggregated usage data prior to that date."]
breaking_changes: []
licence: Open Government Licence (Malaysia)
attribution: National Digital Department and Ministry of Digital via data.gov.my
---

# Cumulative OpenAPI Hits by Endpoint

## Status

**Status:** Unknown freshness

**Freshness:** unknown

HTTP 200

## Last checked

2026-08-09 at 08:37:11 UTC.

## File size

The checked resource is 2,579 bytes.

## Provenance

National Digital Department and Ministry of Digital publishes this dataset through data.gov.my (OpenAPI).

- Source: https://api.data.gov.my/data-catalogue?id=usage_metrics_openapi_cumul
- [Official catalogue metadata](https://data.gov.my/data-catalogue/usage_metrics_openapi_cumul)

## Coverage

Malaysia.

## Schema

Refer to the [official catalogue field definitions](https://data.gov.my/data-catalogue/usage_metrics_openapi_cumul) before analysis. The machine-readable envelope records fields observed from the source.

## Known quirks

- Official catalogue caveat: Although the OpenAPI was live from 13 Sep 2023, this dataset only includes API hits from 15 Dec 2023 onwards due to lack of disaggregated usage data prior to that date.

## Breaking changes

None observed.

## Reproducibility

    curl -sS --max-time 30 "https://api.data.gov.my/data-catalogue?id=usage_metrics_openapi_cumul" | head

## Licence

Licensed under Open Government Licence (Malaysia).
Attribution: National Digital Department and Ministry of Digital via data.gov.my.
