---
dataset_id: dgm_vaxreg_covid
last_checked: 2026-08-09T08:37:11Z
last_checked: 2026-08-09T08:37:11Z
status: stale
freshness_delta: 1629 days
next_expected_update: daily
record_count: 6205
schema_version: unknown
schema_drift: none
known_quirks: ["Official catalogue caveat: This data does not include individuals who registered via the website (vaksincovid.gov.my, now deprecated) or call centre. Although those registrations were used operationally during the program, they were intentionally excluded from this dataset due to the extremely high duplication of registrations via MySejahtera versus those two modalities. Furthermore, it should be noted that the individual's state was self-declared and unverified, and may therefore be different from the individual's state of residence, or even the state where they eventually received their vaccine. Therefore, appropriate caution should be applied when comparing registration data to actual vaccination throughput or population data."]
breaking_changes: []
licence: Open Government Licence (Malaysia)
attribution: Ministry of Health Malaysia via data.gov.my
---

# Daily COVID-19 Vaccine Registrations by State

## Status

**Status:** Stale

**Freshness:** 1629 days

HTTP 200

## Last checked

2026-08-09 at 08:37:11 UTC.

## File size

The checked resource is 424,651 bytes.

## Provenance

Ministry of Health Malaysia publishes this dataset through data.gov.my (OpenAPI).

- Source: https://api.data.gov.my/data-catalogue?id=vaxreg_covid
- [Official catalogue metadata](https://data.gov.my/data-catalogue/vaxreg_covid)

## Coverage

Malaysia.

## Schema

Refer to the [official catalogue field definitions](https://data.gov.my/data-catalogue/vaxreg_covid) before analysis. The machine-readable envelope records fields observed from the source.

## Known quirks

- Official catalogue caveat: This data does not include individuals who registered via the website (vaksincovid.gov.my, now deprecated) or call centre. Although those registrations were used operationally during the program, they were intentionally excluded from this dataset due to the extremely high duplication of registrations via MySejahtera versus those two modalities. Furthermore, it should be noted that the individual's state was self-declared and unverified, and may therefore be different from the individual's state of residence, or even the state where they eventually received their vaccine. Therefore, appropriate caution should be applied when comparing registration data to actual vaccination throughput or population data.

## Breaking changes

None observed.

## Reproducibility

    curl -sS --max-time 30 "https://api.data.gov.my/data-catalogue?id=vaxreg_covid" | head

## Licence

Licensed under Open Government Licence (Malaysia).
Attribution: Ministry of Health Malaysia via data.gov.my.
