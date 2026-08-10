---
dataset_id: dgm_births
last_checked: 2026-08-09T08:37:11Z
last_checked: 2026-08-09T08:37:11Z
status: stale
freshness_delta: 1105 days
next_expected_update: daily
record_count: 37833
schema_version: unknown
schema_drift: none
known_quirks: ["Official catalogue caveat: There are several nuances to bear in mind when using this data: 1. The data is derived based on births registerd with JPN. Accordingly, if a birth is not registered with JPN (for instance, if a foreigner chooses to register their child in their home country, or if a resident in a remote area does not register the birth of their child), it will not count in this dataset. 2. This dataset tabulate births for each day of birth, rather than the date of registration with JPN. Therefore, to ensure accuracy, the data is provided with a 1 month lag, since most people do not register their child on the exact day they are born. 3. Data for past dates may be revised in future updates; this represents people registering children outside a 1 month window from their date of birth. However, our update procedure should ensure that there is no significant change to the trend."]
breaking_changes: []
licence: Open Government Licence (Malaysia)
attribution: National Registration Department via data.gov.my
---

# Daily Live Births

## Status

**Status:** Stale

**Freshness:** 1105 days

HTTP 200

## Last checked

2026-08-09 at 08:37:11 UTC.

## File size

The checked resource is 2,289,547 bytes.

## Provenance

National Registration Department publishes this dataset through data.gov.my (OpenAPI).

- Source: https://api.data.gov.my/data-catalogue?id=births
- [Official catalogue metadata](https://data.gov.my/data-catalogue/births)

## Coverage

Malaysia.

## Schema

Refer to the [official catalogue field definitions](https://data.gov.my/data-catalogue/births) before analysis. The machine-readable envelope records fields observed from the source.

## Known quirks

- Official catalogue caveat: There are several nuances to bear in mind when using this data: 1. The data is derived based on births registerd with JPN. Accordingly, if a birth is not registered with JPN (for instance, if a foreigner chooses to register their child in their home country, or if a resident in a remote area does not register the birth of their child), it will not count in this dataset. 2. This dataset tabulate births for each day of birth, rather than the date of registration with JPN. Therefore, to ensure accuracy, the data is provided with a 1 month lag, since most people do not register their child on the exact day they are born. 3. Data for past dates may be revised in future updates; this represents people registering children outside a 1 month window from their date of birth. However, our update procedure should ensure that there is no significant change to the trend.

## Breaking changes

None observed.

## Reproducibility

    curl -sS --max-time 30 "https://api.data.gov.my/data-catalogue?id=births" | head

## Licence

Licensed under Open Government Licence (Malaysia).
Attribution: National Registration Department via data.gov.my.
